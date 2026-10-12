"""Guarded retirement acceptance on ownership-verified disposable PostgreSQL only."""

import io
from datetime import date
from uuid import uuid4

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from models.base import Base
from models.competition import Competition
from models.hold.football import FootballSnapshot
from models.match import Match
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from tests.integration.migrations.test_catalog import isolated_schema as isolated_schema
from tests.integration.migrations.test_catalog import (
    run_sql,
    signature,
)

pytestmark = pytest.mark.postgres
PARENT = "a7c93e25d104"
HEAD = "c8d42f19e630"
RETAINED = {
    "teams",
    "competitions",
    "matches",
    "scenarios",
    "predictions",
    "football_teams",
    "football_history",
    "football_snapshots",
}


def snapshot(connection, tables):
    return {
        name: (
            signature(connection, name),
            connection.execute(
                text(f'SELECT to_jsonb(t) FROM "{name}" t ORDER BY to_jsonb(t)::text')
            )
            .scalars()
            .all(),
        )
        for name in tables
    }


def upgrade(connection, config, offline):
    if offline:
        stream = io.StringIO()
        config.output_buffer = stream
        command.upgrade(config, f"{PARENT}:{HEAD}", sql=True)
        sql = stream.getvalue().replace("BEGIN;", "").replace("COMMIT;", "")
        connection.exec_driver_sql(sql)
    else:
        command.upgrade(config, "head")


@pytest.mark.parametrize("offline", [False, True])
def test_empty_upgrade_preserves_all_retained_records(isolated_schema, scenario_body, offline):
    connection, config = isolated_schema
    assert ScriptDirectory.from_config(config).get_heads() == [HEAD]
    command.upgrade(config, PARENT)
    assert set(inspect(connection).get_table_names()) == RETAINED | {
        "items",
        "actions",
        "alembic_version",
    }
    run_sql(connection, "prototype/003_seed_football.sql")
    connection.execute(
        FootballSnapshot.__table__.insert().values(
            team1="Spain", team2="England", state={"minute": 65}, prediction={"saved": True}
        )
    )
    for identity, name in [(1, "Home"), (2, "Away")]:
        connection.execute(
            Team.__table__.insert().values(
                team_id=identity, name=name, name_key=name.lower(), category="fixture"
            )
        )
    connection.execute(
        Competition.__table__.insert().values(
            competition_id=1, name="Cup", name_key="cup", edition_label="2023", category="fixture"
        )
    )
    connection.execute(
        Match.__table__.insert().values(
            match_id=1,
            competition_id=1,
            home_team_id=1,
            away_team_id=2,
            match_date=date(2023, 8, 20),
            home_score=1,
            away_score=0,
            score_basis="including_extra_time_no_shootout",
            source="fixture",
            source_record_key="a" * 64,
            source_version="fixture",
            source_file_sha256="b" * 64,
            source_row=1,
            source_url="fixture://test",
            source_home_team="Home",
            source_away_team="Away",
            source_tournament="Cup",
        )
    )
    identity = connection.execute(
        Scenario.__table__.insert()
        .values(**{**scenario_body, "match_id": 1})
        .returning(Scenario.scenario_id)
    ).scalar_one()
    connection.execute(
        Prediction.__table__.insert().values(
            scenario_id=identity,
            model_version="preservation-fixture",
            team1_win_probability=0.5,
            draw_probability=0.25,
            team2_win_probability=0.25,
            input_snapshot={"captured": [1, 2]},
            details={"preserve": True},
        )
    )
    before = snapshot(connection, RETAINED)
    assert all(rows for _, rows in before.values())
    upgrade(connection, config, offline)
    assert set(inspect(connection).get_table_names()) == RETAINED | {"alembic_version"}
    assert set(Base.metadata.tables) == RETAINED
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    assert snapshot(connection, RETAINED) == before


@pytest.mark.parametrize("offline", [False, True])
@pytest.mark.parametrize("with_action", [False, True])
def test_nonempty_refusal_preserves_schema_revision_and_records(
    isolated_schema, offline, with_action
):
    connection, config = isolated_schema
    command.upgrade(config, PARENT)
    identity = uuid4()
    connection.execute(
        text(
            "INSERT INTO items (id, name, status, created_at, updated_at) "
            "VALUES (:id, 'preserve item', 'active', now(), now())"
        ),
        {"id": identity},
    )
    if with_action:
        connection.execute(
            text(
                "INSERT INTO actions (id, item_id, name, action_type, created_at, updated_at) "
                "VALUES (:id, :parent, 'preserve action', 'create', now(), now())"
            ),
            {"id": uuid4(), "parent": identity},
        )
    tables = set(inspect(connection).get_table_names())
    before = snapshot(connection, tables)
    with pytest.raises(IntegrityError, match="Item/Action retirement refused"):
        with connection.begin_nested():
            upgrade(connection, config, offline)
    assert set(inspect(connection).get_table_names()) == tables
    assert snapshot(connection, tables) == before
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT


def test_downgrade_recreates_exact_empty_legacy_schema(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, PARENT)
    original = {name: signature(connection, name) for name in ("items", "actions")}
    retained = snapshot(connection, RETAINED)
    command.upgrade(config, HEAD)
    command.downgrade(config, PARENT)
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT
    for name in original:
        assert signature(connection, name) == original[name]
        assert connection.scalar(text(f'SELECT count(*) FROM "{name}"')) == 0
    assert snapshot(connection, RETAINED) == retained
    command.upgrade(config, HEAD)


def test_unexpected_dependency_rolls_back_even_the_first_drop(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, PARENT)
    connection.execute(
        text("CREATE TABLE retirement_dependency (item_id uuid REFERENCES items(id))")
    )
    tables = set(inspect(connection).get_table_names())
    before = snapshot(connection, tables)
    with pytest.raises(DBAPIError) as failure:
        with connection.begin_nested():
            command.upgrade(config, HEAD)
    assert failure.value.orig.sqlstate == "2BP01"  # DROP RESTRICT, not broad CASCADE.
    assert set(inspect(connection).get_table_names()) == tables
    assert snapshot(connection, tables) == before
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT


def test_upgrade_holds_both_exclusive_locks_before_guard(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, PARENT)
    observed = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("DO $guard$"):
            rows = (
                conn.execute(
                    text("""
                SELECT c.relname FROM pg_locks l JOIN pg_class c ON c.oid=l.relation
                WHERE l.pid=pg_backend_pid() AND l.granted AND l.mode='AccessExclusiveLock'
                  AND c.relnamespace=current_schema()::regnamespace
                  AND c.relname IN ('items', 'actions')
            """)
                )
                .scalars()
                .all()
            )
            observed.append(set(rows))

    event.listen(connection, "before_cursor_execute", capture)
    try:
        command.upgrade(config, HEAD)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert observed == [{"items", "actions"}]
