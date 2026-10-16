from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from infra.repositories.competition import CompetitionRepository
from infra.repositories.match import MatchRepository
from infra.repositories.prediction import PredictionRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from models.base import Base
from models.prediction import Prediction
from models.scenario import Scenario
from tests.fixtures.historical_database import generate, prediction, scenario


@pytest.mark.postgres
@pytest.mark.parametrize(
    "changes",
    [
        {"team1_win_probability": -1},
        {"team2_win_probability": 2},
        {"draw_probability": float("nan")},
        {"draw_probability": float("inf")},
        {"team1_win_probability": 1, "draw_probability": 1},
        {"team1_expected_remaining_goals": -1},
        {"team2_expected_remaining_goals": float("inf")},
        {"team1_expected_remaining_goals": float("nan")},
        {"most_likely_team1_score": -1},
        {"model_version": " "},
        {"model_version": ""},
        {"scenario_id": 2147483647},
        {"input_snapshot": []},
        {"details": []},
        {"generated_at": None},
    ],
)
def test_database_constraints(scenario_client, saved_scenario, import_database, changes):
    saved = generate(scenario_client, saved_scenario).json
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Prediction.__table__.update()
                .where(Prediction.prediction_id == saved["prediction_id"])
                .values(**changes)
            )
    assert scenario_client.get(f"/api/v1/predictions/{saved['prediction_id']}").json == saved


@pytest.mark.postgres
def test_repeated_upgrade_preserves_data_and_relationship(
    scenario_client, saved_scenario, import_database
):
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        before = {
            name: connection.execute(
                text(f'SELECT row_to_json(t)::text FROM "{name}" t ORDER BY row_to_json(t)::text')
            ).all()
            for name in tables
        }
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == tables | {
            "predictions",
            "alembic_version",
        }
        for name in tables:
            assert (
                connection.execute(
                    text(
                        f'SELECT row_to_json(t)::text FROM "{name}" t ORDER BY row_to_json(t)::text'
                    )
                ).all()
                == before[name]
            )
        inspector = inspect(connection)
        assert inspector.get_pk_constraint("predictions")["constrained_columns"] == [
            "prediction_id"
        ]
        fk = inspector.get_foreign_keys("predictions")
        assert (
            len(fk) == 1
            and fk[0]["referred_table"] == "scenarios"
            and fk[0]["options"]["ondelete"] == "RESTRICT"
        )
        assert inspector.get_unique_constraints("predictions") == []
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_server_default": True}),
                Base.metadata,
            )
            == []
        )
    for _ in range(2):
        generate(scenario_client, saved_scenario)
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Scenario.__table__.delete().where(
                    Scenario.scenario_id == saved_scenario["scenario_id"]
                )
            )


@pytest.mark.postgres
def test_prediction_append_history_and_snapshot_preservation(database, scenario_body):
    with database.transaction() as session:
        parent, other = scenario(scenario_body), scenario(scenario_body)
        ScenarioRepository(database).add(session, parent)
        ScenarioRepository(database).add(session, other)
        repo = PredictionRepository(database)
        rows = [
            prediction(parent.scenario_id),
            prediction(parent.scenario_id),
            prediction(parent.scenario_id, generated_at=datetime(2025, 1, 1, tzinfo=UTC)),
            prediction(other.scenario_id),
        ]
        for row in rows:
            repo.add(session, row)
        ids = [r.prediction_id for r in rows]
        parent_id = parent.scenario_id
        assert all(ids)
        parent.team1_offense = 99
    with database.transaction() as session:
        repo = PredictionRepository(database)
        history = repo.history(session, parent_id)
        assert [r.prediction_id for r in history] == [ids[1], ids[0], ids[2]]
        assert [r.prediction_id for r in repo.history(session, parent_id, limit=1, offset=1)] == [
            ids[0]
        ]
        assert repo.history(session, 999) == []
        assert repo.get_by_id(session, 999) is None
        saved = repo.get_by_id(session, ids[0])
        assert saved.input_snapshot == {"team1_name": "captured", "ratings": {"offense": 70}}
        assert saved.model_version == "fixture-v1"
        assert saved.details == {"reasoning": ["synthetic"]}
        assert not hasattr(repo, "update") and not hasattr(repo, "delete")
    assert saved.input_snapshot["team1_name"] == "captured"


@pytest.mark.postgres
def test_shared_session_caller_rollback_undoes_all_writes(database, scenario_body, monkeypatch):
    with database.sessions() as session:
        repositories = [
            cls(database)
            for cls in (
                TeamRepository,
                CompetitionRepository,
                MatchRepository,
                ScenarioRepository,
                PredictionRepository,
            )
        ]
        assert all(vars(repo) == {"database": database} for repo in repositories)

        def forbidden():
            pytest.fail("Repository attempted independent transaction control")

        with monkeypatch.context() as patch:
            patch.setattr(session, "commit", forbidden)
            patch.setattr(session, "rollback", forbidden)
            assert len(repositories[0].get_participants(session, [10, 20], for_key_share=True)) == 2
            assert repositories[1].get_by_id(session, 10) is not None
            assert repositories[2].get_by_id(session, 10, for_share=True) is not None
            row = scenario(scenario_body)
            repositories[3].add(session, row)
            result = prediction(row.scenario_id)
            repositories[4].add(session, result)
            identity, prediction_id = row.scenario_id, result.prediction_id
            with database.sessions() as observer:
                assert ScenarioRepository(database).get_by_id(observer, identity) is None
                assert PredictionRepository(database).get_by_id(observer, prediction_id) is None
        session.rollback()
    with database.transaction() as session:
        assert ScenarioRepository(database).get_by_id(session, identity) is None
        assert PredictionRepository(database).get_by_id(session, prediction_id) is None
