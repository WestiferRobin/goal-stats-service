"""Bootstrap lifecycle on ownership-verified disposable PostgreSQL schemas only."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, inspect, text

from football import bootstrap as boot
from football.datasets import HistoricalImportError
from football.historical_dataset import APPROVED_DATASETS
from football.historical_import import import_historical_dataset
from infra.resources.db import Database
from settings.base import ConfigurationError
from settings.database import DatabaseSettings, ImportTarget, database_url
from tests.fixtures.historical_database import snapshot

pytestmark = pytest.mark.postgres


@pytest.fixture
def fresh_database(postgres_app, postgres_config):
    owner = postgres_app.extensions["goalstats_database"]
    schema = "bootstrap_test_" + uuid4().hex
    with owner.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    database = Database(DatabaseSettings(database_url(postgres_config["DATABASE_URL"])))

    @event.listens_for(database.engine, "connect")
    def set_schema(dbapi_connection, _):
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        dbapi_connection.commit()

    try:
        yield database
    finally:
        database.dispose()
        with owner.engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def prepared_source(edition_source, monkeypatch):
    directory, manifests = edition_source
    monkeypatch.setattr(boot, "load_manifest", lambda d: manifests[d])
    return directory


def target(database):
    url = database.engine.url
    return ImportTarget("test", url.host, url.database)


def test_fresh_then_complete_skips_import(fresh_database, prepared_source, monkeypatch):
    database = fresh_database
    assert inspect(database.engine).get_table_names() == []
    assert boot.bootstrap(database, target(database), prepared_source) == "imported"
    before = snapshot(database)
    assert [len(before[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]

    def forbidden(*args, **kwargs):
        pytest.fail("Complete database must never invoke the importer")

    monkeypatch.setattr(boot, "import_historical_dataset", forbidden)
    assert boot.bootstrap(database, target(database), prepared_source) == "verified existing"
    assert snapshot(database) == before


@pytest.mark.parametrize("damage", ["partial", "conflict", "provenance", "extra_team"])
def test_existing_invalid_catalog_is_preserved(
    fresh_database, prepared_source, monkeypatch, damage
):
    database = fresh_database
    boot.bootstrap(database, target(database), prepared_source)
    changes = {
        "partial": "DELETE FROM matches WHERE match_id = (SELECT min(match_id) FROM matches)",
        "conflict": "UPDATE matches SET home_score=home_score+1 "
        "WHERE match_id=(SELECT min(match_id) FROM matches)",
        "provenance": "UPDATE matches SET source_version='incorrect' "
        "WHERE match_id=(SELECT min(match_id) FROM matches)",
        "extra_team": "INSERT INTO teams(name,name_key,category) VALUES ('Extra','extra','test')",
    }
    with database.engine.begin() as connection:
        connection.execute(text(changes[damage]))
    before = snapshot(database)

    def forbidden(*args, **kwargs):
        pytest.fail("Partial/conflicting database must never invoke the importer")

    monkeypatch.setattr(boot, "import_historical_dataset", forbidden)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(ConfigurationError) as failure:
        boot.bootstrap(database, target(database), prepared_source, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.CATALOG
    assert snapshot(database) == before


def test_import_failure_rolls_back_migrations_and_all_editions(
    fresh_database, prepared_source, monkeypatch
):
    calls = []

    def fail_later(*args, **kwargs):
        calls.append(kwargs["dataset_id"])
        if kwargs["dataset_id"] == APPROVED_DATASETS[2]:
            raise RuntimeError("injected import failure")
        return import_historical_dataset(*args, **kwargs)

    monkeypatch.setattr(boot, "import_historical_dataset", fail_later)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(RuntimeError, match="injected") as failure:
        boot.bootstrap(fresh_database, target(fresh_database), prepared_source, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.IMPORT
    assert calls == list(APPROVED_DATASETS[:3])
    assert inspect(fresh_database.engine).get_table_names() == []


def test_final_verification_failure_rolls_back(fresh_database, prepared_source, monkeypatch):
    def fail(*args):
        raise ConfigurationError("injected verification failure")

    monkeypatch.setattr(boot, "verify_catalog", fail)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(ConfigurationError) as failure:
        boot.bootstrap(fresh_database, target(fresh_database), prepared_source, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.CATALOG
    assert inspect(fresh_database.engine).get_table_names() == []


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_corrupt_source_never_migrates(fresh_database, tmp_path, corrupt):
    directory = tmp_path / "absent"
    if corrupt:
        directory.mkdir()
        (directory / "results.csv").write_text("not the pinned source")
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(HistoricalImportError) as failure:
        boot.bootstrap(fresh_database, target(fresh_database), directory, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.SOURCE
    assert inspect(fresh_database.engine).get_table_names() == []


def test_wrong_identity_never_migrates(fresh_database, prepared_source):
    bad = ImportTarget("test", "wrong-host", fresh_database.engine.url.database)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(ConfigurationError) as failure:
        boot.bootstrap(fresh_database, bad, prepared_source, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.IDENTITY
    assert inspect(fresh_database.engine).get_table_names() == []


def test_guarded_migration_failure_preserves_legacy_data(fresh_database, prepared_source):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import SQLAlchemyError

    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    with fresh_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "c8d42f19e630")
        connection.execute(text("INSERT INTO football_teams(name,ratings) VALUES ('Keep', '{}')"))
    before = snapshot(fresh_database)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(SQLAlchemyError) as failure:
        boot.bootstrap(fresh_database, target(fresh_database), prepared_source, diagnostic)
    assert diagnostic.category(failure.value) == boot.FailureCategory.MIGRATION
    assert snapshot(fresh_database) == before


def test_concurrent_import_is_refused(fresh_database, prepared_source):
    with fresh_database.engine.begin() as other:
        other.execute(text("SELECT pg_advisory_xact_lock(718235940215)"))
        with pytest.raises(ConfigurationError, match="Another"):
            boot.bootstrap(fresh_database, target(fresh_database), prepared_source)
    assert inspect(fresh_database.engine).get_table_names() == []
