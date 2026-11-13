from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InvalidRequestError

pytestmark = pytest.mark.postgres


def schema_contract(connection):
    """Compare reflected DDL, including checks not covered by autogeneration."""
    from sqlalchemy import inspect

    inspector = inspect(connection)
    result = {}
    for table in sorted(inspector.get_table_names()):
        columns = inspector.get_columns(table)
        for column in columns:
            column["type"] = str(column["type"])
        result[table] = {"columns": columns, "pk": inspector.get_pk_constraint(table)}
        for kind, method in (
            ("fk", inspector.get_foreign_keys),
            ("unique", inspector.get_unique_constraints),
            ("checks", inspector.get_check_constraints),
            ("indexes", inspector.get_indexes),
        ):
            values = method(table)
            for value in values:
                value.pop("referred_schema", None)
            result[table][kind] = sorted(values, key=lambda value: value["name"])
    return result


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


@pytest.mark.parametrize("owned", [False, True])
def test_ownership_downgrade_refuses_populated_users(
    scenario_client, saved_scenario, import_database, owned
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    from tests.fixtures.historical_database import snapshot

    with import_database.engine.begin() as connection:
        user = connection.scalar(text("INSERT INTO users DEFAULT VALUES RETURNING user_id"))
        if owned:
            connection.execute(text("UPDATE scenarios SET owner_user_id=:owner"), {"owner": user})
    before = snapshot(import_database)
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with pytest.raises(DBAPIError) as error:
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "d91e6a4b208f")
    assert error.value.orig.sqlstate == "23514"
    assert snapshot(import_database) == before


def test_ownership_upgrade_preserves_old_columns_and_failed_ddl(
    scenario_client, saved_scenario, import_database
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from sqlalchemy.exc import DBAPIError

    from tests.fixtures.historical_database import snapshot

    saved = scenario_client.post(
        f"/api/v1/scenarios/{saved_scenario['scenario_id']}/predictions"
    ).json
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "d91e6a4b208f")
    before = snapshot(import_database)
    assert "users" not in before
    # Force a late index-creation failure in the owned schema, after new DDL began.
    with import_database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE ix_scenarios_owner_user_id (probe integer)")
    blocked = snapshot(import_database)
    with pytest.raises(DBAPIError) as error:
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    assert error.value.orig.sqlstate == "42P07"
    assert snapshot(import_database) == blocked
    with import_database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE ix_scenarios_owner_user_id")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == set(before) | {"users"}
        assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        assert (
            connection.scalar(
                text("SELECT count(*) FROM scenarios WHERE owner_user_id IS NOT NULL")
            )
            == 0
        )
        owner = next(c for c in inspector.get_columns("scenarios") if c["name"] == "owner_user_id")
        assert owner["nullable"] and owner["default"] is None
        old_rows = (
            connection.execute(
                text("SELECT to_jsonb(t) - 'owner_user_id' FROM scenarios t ORDER BY scenario_id")
            )
            .scalars()
            .all()
        )
    import json

    assert old_rows == sorted(
        [json.loads(row) for row in before["scenarios"]], key=lambda row: row["scenario_id"]
    )
    after = snapshot(import_database)
    for table in ("teams", "competitions", "matches", "predictions"):
        assert after[table] == before[table]
    assert scenario_client.get(f"/api/v1/predictions/{saved['prediction_id']}").json == saved
    assert scenario_client.get("/ready").status_code == 200


def test_standalone_schema_path(postgres_app):
    from uuid import uuid4

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from models.base import Base

    directory = Path(__file__).resolve().parents[4] / "sql"
    database = postgres_app.extensions["goalstats_database"]
    schema = "football_sql_test_" + uuid4().hex
    with database.engine.connect() as connection:
        expected = schema_contract(connection)
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
        connection.exec_driver_sql(f"SET search_path TO {schema}")
        connection.commit()
        try:
            sql = (directory / "001_fresh_database.sql").read_text()
            connection.exec_driver_sql(sql)
            connection.commit()
            context = MigrationContext.configure(connection)
            assert context.get_current_revision() == "e42b7c19a603"
            assert compare_metadata(context, Base.metadata) == []
            assert schema_contract(connection) == expected
            assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
            connection.commit()


@pytest.mark.parametrize("with_action", [False, True])
def test_populated_item_action_retirement_preserves_all_records(
    scenario_client, saved_scenario, import_database, with_action
):
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    from tests.fixtures.historical_database import snapshot

    assert (
        scenario_client.post(
            f"/api/v1/scenarios/{saved_scenario['scenario_id']}/predictions"
        ).status_code
        == 201
    )
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "a7c93e25d104")
        identity = uuid4()
        connection.execute(
            text(
                "INSERT INTO items(id,name,status,created_at,updated_at) "
                "VALUES (:id,'preserve','active',now(),now())"
            ),
            {"id": identity},
        )
        if with_action:
            connection.execute(
                text(
                    "INSERT INTO actions(id,item_id,name,action_type,created_at,updated_at) "
                    "VALUES (:id,:item,'preserve','create',now(),now())"
                ),
                {"id": uuid4(), "item": identity},
            )
    before = snapshot(import_database)
    with pytest.raises(DBAPIError) as error:
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    assert error.value.orig.sqlstate == "23514"
    assert "Item/Action retirement refused" in str(error.value.orig)
    assert snapshot(import_database) == before
    # Recoverable at the original revision: normal reads and transactions still work.
    with import_database.engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a7c93e25d104"
        assert connection.scalar(text("SELECT count(*) FROM predictions")) == 1


@pytest.mark.parametrize("operation", ["upgrade", "downgrade"])
def test_ownership_migration_lock_timeout_preserves_state(import_database, operation):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    from tests.fixtures.historical_database import snapshot

    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    if operation == "upgrade":
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "d91e6a4b208f")
    before = snapshot(import_database)
    with import_database.engine.begin() as holder:
        holder.exec_driver_sql("LOCK TABLE scenarios IN ACCESS SHARE MODE")
        with pytest.raises(DBAPIError) as error:
            with import_database.engine.begin() as contender:
                contender.exec_driver_sql("SET LOCAL lock_timeout = '100ms'")
                config.attributes["connection"] = contender
                if operation == "upgrade":
                    command.upgrade(config, "head")
                else:
                    command.downgrade(config, "d91e6a4b208f")
        assert error.value.orig.sqlstate == "55P03"
    assert snapshot(import_database) == before


def test_ownership_downgrade_dependency_failure_is_atomic(import_database):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    with import_database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE VIEW owner_dependency AS SELECT owner_user_id FROM scenarios"
        )
        before = schema_contract(connection)
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with pytest.raises(DBAPIError) as error:
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "d91e6a4b208f")
    assert error.value.orig.sqlstate == "2BP01"
    with import_database.engine.connect() as connection:
        assert schema_contract(connection) == before
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "e42b7c19a603"
        connection.exec_driver_sql("SELECT * FROM owner_dependency")


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
    before = snapshot(import_database)
    config = Config(str(Path(__file__).resolve().parents[4] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "c8d42f19e630")
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
            "users",
        }
    after = snapshot(import_database)
    for table in ["teams", "competitions", "matches", "scenarios", "predictions"]:
        assert after[table] == before[table]
    assert scenario_client.get("/ready").status_code == 200
