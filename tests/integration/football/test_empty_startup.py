"""Canonical Flask factory and host startup on an owned, freshly migrated empty schema."""

import pytest
from sqlalchemy import event, inspect, text

import main
from settings.environment import load_application

pytestmark = pytest.mark.postgres


def snapshot(database):
    with database.engine.connect() as connection:
        tables = sorted(inspect(connection).get_table_names())
        return {
            table: connection.execute(
                text(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY row_to_json(t)::text')
            )
            .scalars()
            .all()
            for table in tables
        }


@pytest.mark.parametrize("mode", ["factory", "host"])
def test_empty_database_startup_never_imports(
    import_database, postgres_config, app_factory, monkeypatch, mode
):
    before = snapshot(import_database)
    expected = {
        "football_teams",
        "football_history",
        "football_snapshots",
        "teams",
        "competitions",
        "matches",
        "scenarios",
        "predictions",
    }
    assert expected <= before.keys()
    assert all(before[table] == [] for table in expected)
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def forbidden(*args, **kwargs):
        pytest.fail("Startup must never select a dataset or invoke an importer")

    for module, name in [
        ("football.cli", "import_datasets"),
        ("football.cli", "import_historical_dataset"),
        ("football.historical_import", "load_manifest"),
    ]:
        monkeypatch.setattr(f"{module}.{name}", forbidden)
    monkeypatch.setattr(main, "Database", lambda _: import_database)
    event.listen(import_database.engine, "before_cursor_execute", track)
    apps = []

    def check(app):
        apps.append(app)
        client = app.test_client()
        for path in ("/health", "/ready", "/swagger", "/swagger/v1/swagger.json"):
            assert client.get(path).status_code == 200, path
        spec = client.get("/swagger/v1/swagger.json").json
        assert len(spec["paths"]) == 20
        for path in (
            "/api/v1/catalog/teams",
            "/api/v1/catalog/matches",
            "/api/v1/catalog/competitions",
            "/api/v1/teams",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json == [], path

    try:
        if mode == "factory":
            check(app_factory(postgres_config))
        else:
            monkeypatch.setenv("API_FOOTBALL_KEY", "")
            monkeypatch.setattr(main, "load_local", lambda: load_application(postgres_config))
            monkeypatch.setattr(main, "local_runtime", lambda: {"API_FOOTBALL_KEY": ""})
            monkeypatch.setattr(main, "_check_app_port", lambda _: None)
            # Run the actual host entrypoint, replacing only its blocking HTTP loop.
            monkeypatch.setattr(main.Flask, "run", lambda app, **kwargs: check(app))
            main.development_main()
        assert snapshot(import_database) == before
        assert not any(
            s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"))
            for s in statements
        )
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)
        for app in apps:
            app.extensions["goalstats_cache"].close()
