from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from football.datasets import import_datasets
from models.football import FootballHistory, FootballSnapshot, FootballTeam

pytestmark = pytest.mark.postgres


@pytest.fixture
def football_client(postgres_app):
    database = postgres_app.extensions["goalstats_database"]
    with database.transaction() as session:
        session.execute(text("DELETE FROM football_snapshots"))
        session.execute(text("DELETE FROM football_history"))
        session.execute(text("DELETE FROM football_teams"))
        import_datasets(session)
        import_datasets(session)
        assert session.scalar(select(func.count()).select_from(FootballTeam)) == 32
        assert session.scalar(select(func.count()).select_from(FootballHistory)) == 16
    return postgres_app.test_client()


def test_predict_persist_backtest_and_insights(football_client):
    client = football_client
    assert len(client.get("/api/v1/teams").json) == 32
    body = {
        "team1": "Spain",
        "team2": "England",
        "minute": 65,
        "team1_stats": {"goals": 1, "shots_on_target": 4},
    }
    response = client.post("/api/v1/predictions", json=body)
    assert response.status_code == 200
    assert sum(response.json["probabilities"].values()) == pytest.approx(1)
    saved = client.post("/api/v1/snapshots", json=body)
    assert saved.status_code == 201
    assert client.get(saved.headers["Location"]).json == saved.json
    backtest = client.get("/api/v1/backtests").json
    assert backtest["evaluated"] == 13
    assert backtest["skipped_unlabeled"] == 3
    assert backtest["snapshots_evaluated"] == 0
    assert len(client.get("/api/v1/history?limit=2&offset=1").json) == 2
    insights = client.get("/api/v1/insights?team1=Spain&team2=England").json
    assert len(insights["head_to_head"]) == 1
    assert (
        client.post("/api/v1/predictions", json={"team1": "Spain", "team2": "Spain"}).status_code
        == 400
    )
    assert (
        client.post("/api/v1/predictions", json={"team1": "missing", "team2": "Spain"}).status_code
        == 404
    )
    assert client.get("/api/v1/history?limit=10000").status_code == 400


def test_live_fallback_is_shared_and_does_not_add_false_history(
    football_client, postgres_app, monkeypatch
):
    from main import create_app

    client = football_client
    body = {"team1": "Spain", "team2": "England"}
    monkeypatch.setattr("football.live.get_real_live_data", lambda *args: None)
    assert client.post("/api/v1/live/refresh", json=body).status_code == 503
    data = {
        "match_minute": 60,
        "match_extra_minute": 0,
        "match_status_short": "2H",
        "team1_possession": 60,
        "team1_goals": 1,
        "team2_goals": 0,
    }
    monkeypatch.setattr("football.live.get_real_live_data", lambda *args: data)
    fresh = client.post("/api/v1/live/refresh", json=body)
    assert fresh.status_code == 200
    assert fresh.json["source"] == "real"
    monkeypatch.setattr("football.live.get_real_live_data", lambda *args: None)
    second_app = create_app(postgres_app.extensions["goalstats_settings"])
    try:
        cached = second_app.test_client().post("/api/v1/live/refresh", json=body)
        assert cached.status_code == 200
        assert cached.json["source"] == "cached"
        assert cached.json["id"] == fresh.json["id"]
        with postgres_app.extensions["goalstats_database"].transaction() as session:
            assert session.scalar(select(func.count()).select_from(FootballSnapshot)) == 1
    finally:
        second_app.extensions["goalstats_database"].dispose()


def test_standalone_sql_seed_matches_python_import(football_client, postgres_app):
    path = Path(__file__).resolve().parents[3] / "sql" / "003_seed_football.sql"
    database = postgres_app.extensions["goalstats_database"]
    # Execute generated SQL using psycopg's simple query protocol on the owned TEST database.
    with database.engine.connect() as connection:
        connection.exec_driver_sql(path.read_text())
        connection.commit()
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(FootballTeam)) == 32
        assert session.scalar(select(func.count()).select_from(FootballHistory)) == 16


@pytest.mark.parametrize("upgrade_existing", [False, True])
def test_standalone_schema_paths(postgres_app, upgrade_existing):
    from uuid import uuid4

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from models.base import Base

    directory = Path(__file__).resolve().parents[3] / "sql"
    database = postgres_app.extensions["goalstats_database"]
    schema = "football_sql_test_" + uuid4().hex
    with database.engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
        connection.exec_driver_sql(f"SET search_path TO {schema}")
        connection.commit()
        try:
            sql = (directory / "001_fresh_database.sql").read_text()
            if upgrade_existing:
                baseline = sql.split("-- Running upgrade b7f42e9c1a60")[0] + "COMMIT;"
                connection.exec_driver_sql(baseline)
                connection.commit()
                sql = (directory / "002_upgrade_template.sql").read_text()
            connection.exec_driver_sql(sql)
            connection.commit()
            connection.exec_driver_sql((directory / "003_seed_football.sql").read_text())
            connection.commit()
            assert connection.scalar(text("SELECT count(*) FROM football_teams")) == 32
            assert connection.scalar(text("SELECT count(*) FROM football_history")) == 16
            context = MigrationContext.configure(connection)
            assert context.get_current_revision() == "d94f81ab2301"
            assert compare_metadata(context, Base.metadata) == []
        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
            connection.commit()
