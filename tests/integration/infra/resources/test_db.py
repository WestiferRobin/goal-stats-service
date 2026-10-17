from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InvalidRequestError

pytestmark = pytest.mark.postgres


def test_ready_uses_real_postgresql_and_releases_connection(postgres_app):
    response = postgres_app.test_client().get("/ready")
    assert (response.status_code, response.text) == (200, "Degraded")
    assert postgres_app.extensions["goalstats_database"].engine.pool.checkedout() == 0


def test_real_postgresql_authentication_failure_is_safe(app_factory, postgres_config):
    from settings.database import database_url

    url = database_url(postgres_config["DATABASE_URL"]).set(
        password="intentionally_invalid_password"
    )
    app = app_factory(
        {**postgres_config, "DATABASE_URL": url.render_as_string(hide_password=False)}
    )
    assert app.test_client().get("/health").status_code == 200
    response = app.test_client().get("/ready")
    assert (response.status_code, response.text) == (503, "Unhealthy")


def test_explicit_application_transactions_commit_or_roll_back(postgres_app, probe_table):
    database = postgres_app.extensions["goalstats_database"]
    with database.transaction() as session:
        session.execute(text(f"INSERT INTO {probe_table} VALUES (1)"))
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            session.execute(text(f"INSERT INTO {probe_table} VALUES (2)"))
            raise RuntimeError("abort operation")
    with pytest.raises(InvalidRequestError):
        session.execute(text("SELECT 1"))
    with database.engine.connect() as connection:
        assert connection.scalars(text(f"SELECT value FROM {probe_table}")).all() == [1]
    assert database.engine.pool.checkedout() == 0


def test_standalone_schema_path(postgres_app):
    from uuid import uuid4

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from models.base import Base

    directory = Path(__file__).resolve().parents[4] / "sql"
    database = postgres_app.extensions["goalstats_database"]
    schema = "football_sql_test_" + uuid4().hex
    with database.engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
        connection.exec_driver_sql(f"SET search_path TO {schema}")
        connection.commit()
        try:
            sql = (directory / "001_fresh_database.sql").read_text()
            connection.exec_driver_sql(sql)
            connection.commit()
            context = MigrationContext.configure(connection)
            assert context.get_current_revision() == "d91e6a4b208f"
            assert compare_metadata(context, Base.metadata) == []
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
            connection.commit()


@pytest.mark.parametrize("blocker", ["none", "populated", "dependent_view", "different_owner"])
def test_forward_retirement_preserves_normalized_records_and_guards_loss(
    scenario_client, scenario_body, import_database, blocker
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from sqlalchemy.exc import DBAPIError

    from tests.fixtures.historical_database import snapshot

    saved = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    assert saved.status_code == 201
    assert scenario_client.post(saved.headers["Location"] + "/predictions").status_code == 201
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "c8d42f19e630")
    before = snapshot(import_database)
    with import_database.engine.begin() as connection:
        if blocker == "populated":
            connection.exec_driver_sql(
                "INSERT INTO football_teams(name,ratings) VALUES ('Archived', '{}')"
            )
        if blocker == "different_owner":
            connection.exec_driver_sql("ALTER TABLE football_teams OWNER TO pg_database_owner")
        if blocker == "dependent_view":
            connection.exec_driver_sql(
                "CREATE VIEW external_dependency AS SELECT name FROM football_teams"
            )
    if blocker != "none":
        with pytest.raises(DBAPIError):
            with import_database.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        with import_database.engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version")) == "c8d42f19e630"
            )
            assert {"football_teams", "football_history", "football_snapshots"} <= set(
                inspect(connection).get_table_names()
            )
            if blocker == "populated":
                assert connection.scalar(text("SELECT count(*) FROM football_teams")) == 1
                # Explicitly disposable fixture only; production migration never clears records.
                connection.exec_driver_sql("DELETE FROM football_teams")
            elif blocker == "different_owner":
                connection.exec_driver_sql("ALTER TABLE football_teams OWNER TO CURRENT_USER")
            else:
                connection.exec_driver_sql("DROP VIEW external_dependency")
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == {
            "alembic_version",
            "teams",
            "competitions",
            "matches",
            "scenarios",
            "predictions",
        }
    after = snapshot(import_database)
    for table in ["teams", "competitions", "matches", "scenarios", "predictions"]:
        assert after[table] == before[table]
    assert scenario_client.get("/ready").status_code == 200
