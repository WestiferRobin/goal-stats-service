from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import text
from test_ownership import owned_test_config

from infra.resources.db import Database
from models.base import Base
from settings.database import database_url
from settings.environment import load_application


@pytest.fixture(scope="session")
def postgres_config() -> dict[str, str]:
    try:
        owned = owned_test_config()
    except RuntimeError as exc:
        pytest.fail(str(exc), pytrace=False)
    value = owned.get("TEST_DATABASE_URL")
    if not value or owned.get("TEST_DATABASE_DISPOSABLE") != "1":
        pytest.fail("Verified disposable TEST configuration is required.", pytrace=False)
    try:
        url = database_url(value)
    except ValueError:
        pytest.fail("TEST_DATABASE_URL is invalid; its value is intentionally omitted.")
    if not url.database or not url.database.startswith("goalstats_test_"):
        pytest.fail("Provider tests require a dedicated goalstats_test_* database.")
    config = {
        "APP_ENV": "test",
        "DATABASE_URL": value,
        **{
            key: owned.get(key, default)
            for key, default in {
                "OPENAPI_ENABLED": "true",
                "LOG_LEVEL": "INFO",
                "CACHE_TTL_SECONDS": "300",
            }.items()
        },
    }
    db = Database(load_application(config).database)
    try:
        with db.engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
        migration = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        with db.engine.begin() as connection:
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")
    except Exception:
        pytest.fail(
            "Explicit TEST PostgreSQL is unavailable; refusing to fall back or skip.", pytrace=False
        )
    finally:
        db.dispose()
    return config


@pytest.fixture
def postgres_app(app_factory, postgres_config) -> Iterator[Flask]:
    app = app_factory(postgres_config)
    db = app.extensions["goalstats_database"]
    # Explicitly disposable database only; no shared developer rows.
    with db.engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    try:
        yield app
    finally:
        with db.engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())


@pytest.fixture
def probe_table(postgres_app) -> Iterator[str]:
    # A test-only table with no application model or migration. No existing tables are touched.
    name = "foundation_probe_" + uuid4().hex
    database = postgres_app.extensions["goalstats_database"]
    with database.engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE {name} (value integer NOT NULL)"))
    try:
        yield name
    finally:
        with database.engine.begin() as connection:
            connection.execute(text(f"DROP TABLE {name}"))
