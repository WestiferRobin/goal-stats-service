"""Isolated schemas exclusively within ownership-verified disposable PostgreSQL."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from infra.resources.db import Database
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
    monkeypatch.setattr("football.historical_import.load_manifest", lambda: manifest)
    return historical_csv
