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
def test_previous_schema_seeded_history_survives_ownership_upgrade(
    import_database, scenario_body, monkeypatch
):
    import json
    from datetime import date

    from sqlalchemy import MetaData, Table

    from services.prediction import PredictionService
    from tests.fixtures.historical_database import snapshot
    from tests.unit.services.test_prediction import frozen_v1_row

    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d91e6a4b208f")
        metadata = MetaData()
        metadata.reflect(connection)
        tables = metadata.tables
        connection.execute(
            tables["teams"].insert(),
            [
                {"team_id": 1, "name": "First", "name_key": "first", "category": "test"},
                {"team_id": 2, "name": "Second", "name_key": "second", "category": "test"},
            ],
        )
        connection.execute(
            tables["competitions"].insert(),
            {
                "competition_id": 1,
                "name": "Cup",
                "name_key": "cup",
                "edition_label": "2023",
                "category": "test",
            },
        )
        connection.execute(
            tables["matches"].insert(),
            {
                "match_id": 1,
                "competition_id": 1,
                "home_team_id": 1,
                "away_team_id": 2,
                "match_date": date(2023, 8, 20),
                "home_score": 1,
                "away_score": 0,
                "score_basis": "including_extra_time_no_shootout",
                "source": "fixture",
                "source_record_key": "a" * 64,
                "source_file_sha256": "b" * 64,
                "source_row": 1,
                "source_version": "fixture",
                "source_url": "fixture://test",
                "source_home_team": "First",
                "source_away_team": "Second",
                "source_tournament": "Cup",
            },
        )
        connection.execute(
            tables["scenarios"].insert(),
            {
                **scenario_body,
                "scenario_id": 1,
                "match_id": 1,
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )
        _, frozen = frozen_v1_row(1)
        values = {
            c.name: getattr(frozen, c.name)
            for c in Prediction.__table__.columns
            if c.name != "prediction_id"
        }
        connection.execute(tables["predictions"].insert(), values)
    before = snapshot(import_database)
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        assert (
            connection.scalar(text("SELECT owner_user_id FROM scenarios WHERE scenario_id=1"))
            is None
        )
        old_scenario = connection.scalar(
            text("SELECT to_jsonb(s) - 'owner_user_id' FROM scenarios s WHERE scenario_id=1")
        )
        assert old_scenario == json.loads(before["scenarios"][0])
        assert Table("users", MetaData(), autoload_with=connection).c.user_id.primary_key
    after = snapshot(import_database)
    for table in ("teams", "competitions", "matches", "predictions"):
        assert after[table] == before[table]

    def forbidden(*args, **kwargs):
        pytest.fail("Reading preserved history must not recalculate")

    monkeypatch.setattr("services.prediction.predict_inputs", forbidden)
    with import_database.transaction() as session:
        saved = session.get(Prediction, 1)
        assert (
            PredictionService._response(saved)["model_version"] == "road-to-the-final-heuristic-v1"
        )


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


@pytest.mark.postgres
@pytest.mark.parametrize(
    "starting_revision", ["a7c93e25d104", "c8d42f19e630", "d91e6a4b208f", "e42b7c19a603"]
)
def test_supported_upgrade_preserves_catalog_scenario_and_saved_output(
    scenario_client, saved_scenario, import_database, starting_revision
):
    from alembic.script import ScriptDirectory

    from tests.fixtures.historical_database import snapshot

    saved = generate(scenario_client, saved_scenario).json
    before = snapshot(import_database)
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_bases() == ["a7c93e25d104"]
    assert scripts.get_heads() == ["e42b7c19a603"]
    assert [r.revision for r in scripts.walk_revisions()] == [
        "e42b7c19a603",
        "d91e6a4b208f",
        "c8d42f19e630",
        "a7c93e25d104",
    ]
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        # The fixture is an isolated schema inside ownership-verified test PostgreSQL.
        # Downgrade only recreates empty legacy tables; normalized records remain intact.
        command.downgrade(config, starting_revision)
        assert MigrationContext.configure(connection).get_current_revision() == starting_revision
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert MigrationContext.configure(connection).get_current_revision() == "e42b7c19a603"
        assert set(inspect(connection).get_table_names()) == {
            "alembic_version",
            "teams",
            "competitions",
            "matches",
            "scenarios",
            "predictions",
            "users",
        }
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_server_default": True}),
                Base.metadata,
            )
            == []
        )
    assert snapshot(import_database) == before
    assert scenario_client.get(f"/api/v1/predictions/{saved['prediction_id']}").json == saved
