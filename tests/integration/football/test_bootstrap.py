"""Bootstrap lifecycle on ownership-verified disposable PostgreSQL schemas only."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, inspect, text

from football import bootstrap as boot
from football import bootstrap_enrichment
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


@pytest.fixture(scope="module")
def approved_enrichment():
    source = (
        boot.ROOT
        / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv"
    )
    return bootstrap_enrichment.prepare(source)


@pytest.fixture
def prepared_source(edition_source, monkeypatch, approved_enrichment):
    directory, manifests = edition_source
    monkeypatch.setattr(boot, "load_manifest", lambda d: manifests[d])
    # Catalog tests use synthetic CSV contracts; enrichment retains the approved real inputs.
    monkeypatch.setattr(bootstrap_enrichment, "prepare", lambda source: approved_enrichment)
    return directory


def target(database):
    url = database.engine.url
    return ImportTarget("test", url.host, url.database)


@pytest.mark.parametrize("existing_user", [False, True])
def test_fresh_then_complete_skips_import(
    fresh_database, prepared_source, monkeypatch, existing_user
):
    database = fresh_database
    assert inspect(database.engine).get_table_names() == []
    assert boot.bootstrap(database, target(database), prepared_source) == "imported"
    with database.engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        if existing_user:
            connection.exec_driver_sql("INSERT INTO users DEFAULT VALUES")
    before = snapshot(database)
    assert [len(before[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]
    assert [
        len(before[t])
        for t in (
            "ranking_releases",
            "ranking_observations",
            "fifa_team_mappings",
            "rating_runs",
            "team_ratings",
        )
    ] == [96, 16525, 44, 1, 44]

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
    assert diagnostic.category(failure.value) == boot.FailureCategory.CONFIGURED_HOST
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


def test_concurrent_enrichment_is_refused(fresh_database, prepared_source):
    with fresh_database.engine.begin() as other:
        other.execute(text("SELECT pg_advisory_xact_lock(71839461)"))
        with pytest.raises(ConfigurationError, match="Another FIFA"):
            boot.bootstrap(fresh_database, target(fresh_database), prepared_source)
    assert inspect(fresh_database.engine).get_table_names() == []


@pytest.mark.parametrize("existing", [False, True])
def test_real_catalog_bootstrap_preserves_saved_records(fresh_database, existing):
    from alembic import command
    from alembic.config import Config

    from models.prediction import Prediction
    from models.scenario import Scenario

    database = fresh_database
    source = boot.ROOT / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c"
    if existing:
        config = Config(str(boot.ROOT / "alembic.ini"))
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        for dataset in APPROVED_DATASETS:
            import_historical_dataset(database, source, target(database), dataset_id=dataset)
        values = {
            c.name: 0
            for c in Scenario.__table__.columns
            if not c.nullable and c.server_default is None and c.identity is None
        }
        values.update(team1_id=1, team2_id=2, team1_possession=50, team2_possession=50)
        with database.transaction() as session:
            scenarios = [Scenario(**values) for _ in range(2)]
            session.add_all(scenarios)
            session.flush()
            for i in range(3):
                session.add(
                    Prediction(
                        scenario_id=scenarios[i % 2].scenario_id,
                        model_version="synthetic-bootstrap-preservation",
                        team1_win_probability=0.4,
                        draw_probability=0.2,
                        team2_win_probability=0.4,
                        input_snapshot={"synthetic": True},
                        details={"synthetic": True},
                    )
                )
        # Reproduce the old production schema with saved records and no enrichment.
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "d91e6a4b208f")
        before = snapshot(database)
    assert boot.bootstrap(database, target(database), source) == (
        "verified existing" if existing else "imported"
    )
    after = snapshot(database)
    assert [
        len(after[t])
        for t in (
            "teams",
            "competitions",
            "matches",
            "ranking_releases",
            "ranking_observations",
            "fifa_team_mappings",
            "rating_runs",
            "team_ratings",
        )
    ] == [44, 9, 348, 96, 16525, 44, 1, 44]
    if existing:
        for table in ("teams", "competitions", "matches", "predictions"):
            assert after[table] == before[table]
        # Ownership migration adds a nullable column; every pre-existing value is exact.
        old_scenarios = [json.loads(row) for row in before["scenarios"]]
        new_scenarios = [json.loads(row) for row in after["scenarios"]]
        assert all(row.pop("owner_user_id") is None for row in new_scenarios)
        assert new_scenarios == old_scenarios
        assert len(after["scenarios"]) == 2 and len(after["predictions"]) == 3
    assert boot.bootstrap(database, target(database), source) == "verified existing"
    assert snapshot(database) == after


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ranking_releases SET sha256=repeat('0',64)",
        "UPDATE ranking_observations SET rank=999 WHERE rank IS NOT NULL",
        "UPDATE fifa_team_mappings SET fifa_team_id='incorrect' WHERE team_id=1",
        "UPDATE rating_runs SET model_version='incorrect'",
        "UPDATE team_ratings SET offense=CASE WHEN offense=1 THEN 2 ELSE 1 END",
    ],
)
def test_enrichment_conflicts_preserve_every_record(fresh_database, prepared_source, sql):
    database = fresh_database
    boot.bootstrap(database, target(database), prepared_source)
    with database.engine.begin() as connection:
        connection.execute(text(sql))
    before = snapshot(database)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(ValueError):
        boot.bootstrap(database, target(database), prepared_source, diagnostic)
    assert diagnostic.stage == boot.FailureCategory.ENRICHMENT
    assert snapshot(database) == before


def test_enrichment_failure_rolls_back_entire_bootstrap(
    fresh_database, prepared_source, monkeypatch
):
    original = boot.enrichment.import_package

    def fail_after_insert(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("injected enrichment failure")

    monkeypatch.setattr(boot.enrichment, "import_package", fail_after_insert)
    with pytest.raises(ValueError, match="injected"):
        boot.bootstrap(fresh_database, target(fresh_database), prepared_source)
    assert inspect(fresh_database.engine).get_table_names() == []


def test_missing_enrichment_never_migrates(fresh_database, prepared_source, monkeypatch, tmp_path):
    def missing(source):
        bootstrap_enrichment.verify_evidence(tmp_path)

    monkeypatch.setattr(bootstrap_enrichment, "prepare", missing)
    diagnostic = boot.BootstrapDiagnostic()
    with pytest.raises(FileNotFoundError):
        boot.bootstrap(fresh_database, target(fresh_database), prepared_source, diagnostic)
    assert diagnostic.stage == boot.FailureCategory.ENRICHMENT_SOURCE
    assert inspect(fresh_database.engine).get_table_names() == []
