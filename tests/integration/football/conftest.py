"""Isolated schemas exclusively within ownership-verified disposable PostgreSQL."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, text

from infra.resources.db import Database
from models.catalog import Match, Team
from settings.database import DatabaseSettings, ImportTarget, database_url


@pytest.fixture
def import_database(postgres_app, postgres_config):
    owner = postgres_app.extensions["goalstats_database"]
    schema = "historical_import_test_" + uuid4().hex
    with owner.engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    database = Database(DatabaseSettings(database_url(postgres_config["DATABASE_URL"])))

    @event.listens_for(database.engine, "connect")
    def set_schema(dbapi_connection, _):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        dbapi_connection.commit()

    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    try:
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield database
    finally:
        database.dispose()
        with owner.engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def import_target(import_database):
    url = import_database.engine.url
    return ImportTarget("test", url.host, url.database)


@pytest.fixture
def pinned_fixture(historical_csv, monkeypatch):
    manifest = historical_csv.write()
    monkeypatch.setattr(
        "football.historical_import.load_manifest",
        lambda dataset_id="womens-world-cup-2023": manifest,
    )
    return historical_csv


@pytest.fixture
def scenario_client(import_database, app_factory, postgres_config, monkeypatch):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=name, name_key=name.lower(), category="test")
                for i, name in [(1, "First"), (2, "Second"), (3, "Third")]
            ]
        )
        session.execute(
            text(
                "INSERT INTO competitions (competition_id,name,name_key,edition_label,category) "
                "VALUES (1,'Test','test','2023','test')"
            )
        )
        session.flush()
        session.add(
            Match(
                match_id=1,
                competition_id=1,
                home_team_id=1,
                away_team_id=2,
                match_date=datetime(2023, 8, 20).date(),
                home_score=1,
                away_score=0,
                score_basis="including_extra_time_no_shootout",
                source="test",
                source_record_key="a" * 64,
                source_file_sha256="b" * 64,
                source_row=1,
                source_version="test",
                source_url="https://example.com/test",
                source_home_team="First",
                source_away_team="Second",
                source_tournament="Test",
            )
        )
    monkeypatch.setattr("main.Database", lambda _: import_database)
    return app_factory(postgres_config).test_client()
