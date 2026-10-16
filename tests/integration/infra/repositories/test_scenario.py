from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from infra.repositories.match import MatchRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from models.base import Base
from models.match import Match
from models.scenario import Scenario
from models.team import Team
from tests.fixtures.historical_database import create, scenario


@pytest.mark.postgres
def test_schema_migration_preserves_existing_data(scenario_client, scenario_body, import_database):
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        before = {
            table: connection.execute(
                text(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY row_to_json(t)::text')
            ).all()
            for table in tables
        }
        command.upgrade(config, "head")
        for table in tables:
            assert (
                connection.execute(
                    text(
                        f'SELECT row_to_json(t)::text FROM "{table}" t '
                        "ORDER BY row_to_json(t)::text"
                    )
                ).all()
                == before[table]
            )
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == tables | {
            "alembic_version",
            "scenarios",
            "predictions",
        }
        assert inspector.get_pk_constraint("scenarios")["constrained_columns"] == ["scenario_id"]
        assert next(c for c in inspector.get_columns("scenarios") if c["name"] == "scenario_id")[
            "identity"
        ]
        keys = inspector.get_foreign_keys("scenarios")
        assert {tuple(k["constrained_columns"]) for k in keys} == {
            ("team1_id",),
            ("team2_id",),
            ("match_id",),
        }
        assert all(k["options"]["ondelete"] == "RESTRICT" for k in keys)
        assert {tuple(i["column_names"]) for i in inspector.get_indexes("scenarios")} == {
            ("team1_id",),
            ("team2_id",),
            ("match_id",),
            ("created_at", "scenario_id"),
        }
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []
    assert create(scenario_client, scenario_body).status_code == 201


@pytest.mark.postgres
@pytest.mark.parametrize(
    "changes",
    [
        {"team1_id": 2},
        {"team1_id": 999},
        {"match_id": 999},
        {"match_minute": -1},
        {"match_minute": 121},
        {"team1_goals": -1},
        {"team2_red_cards": 12},
        {"team1_possession": 101},
        {"team1_possession": 60},
        {"team1_possession": float("nan")},
        {"team1_offense": None},
        {"team1_offense": float("nan")},
        {"team1_offense": float("inf")},
        {"team1_defense": -1},
        {"team2_clutch": 101},
        {"team1_modifier_total": float("nan")},
        {"team1_modifier_total": float("inf")},
        {"team1_modifier_total": float("-inf")},
        {"team2_fifa_rank": 0},
    ],
)
def test_database_rejects_invalid_values(scenario_client, scenario_body, import_database, changes):
    saved = create(scenario_client, scenario_body).json
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Scenario.__table__.update()
                .where(Scenario.scenario_id == saved["scenario_id"])
                .values(**changes)
            )
    assert scenario_client.get(f"{URL}/{saved['scenario_id']}").json == saved


URL = "/api/v1/scenarios"


@pytest.mark.postgres
def test_restrictive_foreign_keys(scenario_client, scenario_body, import_database):
    create(scenario_client, {**scenario_body, "match_id": 1})
    for model, key in [(Team, Team.team_id), (Match, Match.match_id)]:
        with pytest.raises(IntegrityError):
            with import_database.transaction() as session:
                session.execute(model.__table__.delete().where(key == 1))


@pytest.mark.postgres
def test_scenario_insert_projection_update_and_missing(database, scenario_body):
    with database.transaction() as session:
        repo = ScenarioRepository(database)
        row = scenario(scenario_body, match_id=10)
        repo.add(session, row)
        identity = row.scenario_id
        assert identity is not None
        assert repo.exists(session, identity)
        assert repo.get_by_id(session, identity) is row
        projected = repo.get_projection(session, identity)
        assert projected.scenario is row
        assert (projected.team1_name, projected.team2_name) == ("Alpha", "Zulu")
        row.match_minute = 70  # Caller-validated state, repository only flushes.
        repo.flush(session)
        assert not repo.exists(session, 999)
        assert repo.get_by_id(session, 999) is None
        assert repo.get_projection(session, 999) is None
    with database.transaction() as session:
        assert ScenarioRepository(database).get_by_id(session, identity).match_minute == 70


@pytest.mark.postgres
def test_scenario_order_filter_and_shared_projection(database, scenario_body):
    with database.transaction() as session:
        repo = ScenarioRepository(database)
        rows = [
            scenario(scenario_body),
            scenario(scenario_body, team1_id=30),
            scenario(scenario_body, created_at=datetime(2025, 1, 1, tzinfo=UTC)),
        ]
        for row in rows:
            repo.add(session, row)
        ids = [r.scenario_id for r in rows]
    with database.transaction() as session:
        repo = ScenarioRepository(database)
        assert [r.scenario.scenario_id for r in repo.list(session)] == [ids[1], ids[0], ids[2]]
        assert [r.scenario.scenario_id for r in repo.list(session, team_id=30)] == [ids[1]]
        assert len(repo.list(session, team_id=20)) == 3  # Away participant also matches.
        assert repo.list(session, team_id=999) == []
        page = repo.list(session, limit=1, offset=1)
        assert page[0].scenario.scenario_id == ids[0]
    assert page[0].team1_name == "Alpha"
    assert page[0].scenario.match_minute == scenario_body["match_minute"]


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["scenario"])
def test_postgresql_locks_conflict_until_caller_releases(database, scenario_body, kind):
    with database.transaction() as session:
        row = scenario(scenario_body)
        ScenarioRepository(database).add(session, row)
        scenario_id = row.scenario_id
    table, key, identity = {
        "team": ("teams", "team_id", 10),
        "match": ("matches", "match_id", 10),
        "scenario": ("scenarios", "scenario_id", scenario_id),
    }[kind]
    with database.sessions() as holder:
        if kind == "team":
            TeamRepository(database).get_participants(holder, [10], for_key_share=True)
        elif kind == "match":
            MatchRepository(database).get_by_id(holder, 10, for_share=True)
        else:
            ScenarioRepository(database).get_by_id(holder, scenario_id, for_update=True)
        with database.sessions() as contender:
            with pytest.raises(OperationalError) as error:
                contender.execute(
                    text(f"SELECT * FROM {table} WHERE {key}=:id FOR UPDATE NOWAIT"),
                    {"id": identity},
                )
            assert error.value.orig.sqlstate == "55P03"
        if kind == "team":
            # KEY SHARE permits an ordinary non-key update; FOR SHARE would block it.
            with database.transaction() as updater:
                updater.execute(text("SET LOCAL lock_timeout = '100ms'"))
                updater.execute(
                    text("UPDATE teams SET offense=70, ratings_source='fixture' WHERE team_id=10")
                )
        holder.rollback()
    with database.transaction() as session:
        session.execute(
            text(f"SELECT * FROM {table} WHERE {key}=:id FOR UPDATE NOWAIT"), {"id": identity}
        )
