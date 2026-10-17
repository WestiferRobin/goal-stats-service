"""Isolated schemas exclusively within ownership-verified disposable PostgreSQL."""

import csv
import hashlib
import io
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from flask import Flask
from sqlalchemy import event, func, inspect, select, text

from football.cli import register_commands
from football.historical_dataset import APPROVED_DATASETS, load_manifest
from infra.resources.db import Database
from models.competition import Competition
from models.match import Match
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from settings.database import DatabaseSettings, ImportTarget, database_url

URL = "/api/v1/scenarios"

STAMP = datetime(2026, 1, 1, tzinfo=UTC)


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

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
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


def invoke(database, target, directory, dataset, *options):
    app = Flask(__name__)
    register_commands(app, database)
    return app.test_cli_runner().invoke(
        args=[
            "import-football",
            "--dataset",
            dataset,
            "--directory",
            str(directory),
            "--target",
            target.target,
            "--expect-host",
            target.expect_host,
            "--expect-database",
            target.expect_database,
            *options,
        ]
    )


@pytest.fixture
def edition_source(tmp_path, monkeypatch):
    manifests = {dataset: load_manifest(dataset) for dataset in APPROVED_DATASETS}
    rows = []
    for manifest in manifests.values():
        names = manifest.approval.participants
        count = manifest.expected_counts.matches
        goals, remainder = divmod(manifest.approval.total_goals, count)
        for i in range(count):
            # Distinct dated pairs, all approved participants, and the approved goal total.
            pair = i % (len(names) // 2)
            played = manifest.selection.date_from + timedelta(days=i // (len(names) // 2))
            rows.append(
                dict(
                    zip(
                        manifest.required_columns,
                        [
                            played.isoformat(),
                            names[2 * pair],
                            names[2 * pair + 1],
                            str(goals + (i < remainder)),
                            "0",
                            "FIFA World Cup",
                            "",
                            "",
                            "TRUE",
                        ],
                        strict=True,
                    )
                )
            )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=next(iter(manifests.values())).required_columns)
    writer.writeheader()
    writer.writerows(rows)
    payload = stream.getvalue().encode()
    (tmp_path / "results.csv").write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    # Only test source provenance differs. All edition facts and runtime parsing stay strict.
    synthetic = {key: m.model_copy(update={"sha256": checksum}) for key, m in manifests.items()}
    monkeypatch.setattr("football.historical_import.load_manifest", lambda key: synthetic[key])
    return tmp_path, synthetic


def generate(client, saved):
    response = client.post(history_url(saved))
    assert response.status_code == 201, response.json
    return response


def history_url(saved):
    return f"/api/v1/scenarios/{saved['scenario_id']}/predictions"


@pytest.fixture
def saved_scenario(scenario_client, scenario_body):
    scenario_body.update(team1_shots_on_target=4, team1_modifier_total=-7)
    response = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    assert response.status_code == 201
    return response.json


def count(database):
    with database.transaction() as session:
        return session.scalar(select(func.count()).select_from(Prediction))


def create(client, body):
    response = client.post(URL, json=body)
    assert response.status_code == 201, response.json
    return response


@pytest.fixture
def database(import_database):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=n, name_key=n.lower(), category=c)
                for i, n, c in [(30, "Alpha", "b"), (20, "Zulu", "a"), (10, "Alpha", "a")]
            ]
        )
        session.add_all(
            [
                Competition(
                    competition_id=i, name="Cup", name_key="cup", edition_label=y, category=c
                )
                for i, y, c in [(30, "2023", "b"), (20, "2023", "a"), (10, "2019", "a")]
            ]
        )
        session.flush()
        session.add_all(
            [
                Match(
                    match_id=i,
                    competition_id=c,
                    home_team_id=h,
                    away_team_id=a,
                    match_date=date(2023, 7, day),
                    home_score=1,
                    away_score=0,
                    score_basis="including_extra_time_no_shootout",
                    source="synthetic",
                    source_record_key=f"{i:064x}",
                    source_version="fixture",
                    source_file_sha256="a" * 64,
                    source_row=i,
                    source_url="fixture://test",
                    source_home_team="original home",
                    source_away_team="original away",
                    source_tournament="Cup",
                )
                for i, c, h, a, day in [
                    (30, 20, 20, 30, 21),
                    (20, 10, 30, 20, 20),
                    (10, 10, 10, 20, 20),
                ]
            ]
        )
    return import_database


def scenario(body, **changes):
    return Scenario(**{**body, "team1_id": 10, "team2_id": 20, "created_at": STAMP, **changes})


def prediction(scenario_id, **changes):
    return Prediction(
        **{
            "scenario_id": scenario_id,
            "generated_at": STAMP,
            "model_version": "fixture-v1",
            "team1_win_probability": 0.5,
            "draw_probability": 0.25,
            "team2_win_probability": 0.25,
            "input_snapshot": {"team1_name": "captured", "ratings": {"offense": 70}},
            "details": {"reasoning": ["synthetic"]},
            **changes,
        }
    )


@pytest.fixture
def catalog_client(import_database, app_factory, postgres_config, monkeypatch):
    monkeypatch.setattr("main.Database", lambda _: import_database)
    return app_factory(postgres_config).test_client()


@pytest.fixture
def small_catalog(catalog_client, import_database):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=3, name="Spain", name_key="spain", category="women_senior_national"),
                Team(
                    team_id=1, name="England", name_key="england", category="women_senior_national"
                ),
                Team(team_id=2, name="Japan", name_key="japan", category="women_senior_national"),
                Competition(
                    competition_id=1,
                    name="FIFA Women's World Cup",
                    name_key="world cup",
                    edition_label="2023",
                    category="women_senior_national",
                ),
                Competition(
                    competition_id=2,
                    name="Friendly",
                    name_key="friendly",
                    edition_label="2023",
                    category="women_senior_national",
                ),
            ]
        )
        session.flush()
        for match_id, home, away, competition, day in [
            (3, 3, 1, 1, 20),
            (1, 2, 3, 1, 1),
            (2, 1, 2, 2, 1),
        ]:
            session.add(
                Match(
                    match_id=match_id,
                    home_team_id=home,
                    away_team_id=away,
                    competition_id=competition,
                    match_date=date(2023, 8, day),
                    home_score=1,
                    away_score=0,
                    score_basis="including_extra_time_no_shootout",
                    neutral=None,
                    city=None,
                    country=None,
                    source="test",
                    source_row=match_id,
                    source_record_key=f"{match_id:064x}",
                    source_file_sha256="a" * 64,
                    source_version="test",
                    source_url="https://example.com/fixture",
                    source_home_team="test home",
                    source_away_team="test away",
                    source_tournament="test tournament",
                )
            )
    return catalog_client


@pytest.fixture
def pinned_source():
    value = os.environ.get("TEST_PINNED_SOURCE")
    assert value, "Set TEST_PINNED_SOURCE to the approved CSV on a read-only filesystem"
    source = Path(value)
    assert source.is_absolute() and source == source.resolve(), "Use a canonical source path"
    assert source.is_file() and source.name == "results.csv", "Approved source CSV unavailable"
    assert os.statvfs(source).f_flag & os.ST_RDONLY, "Source filesystem must be read-only"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == load_manifest().sha256
    from pinned_source import verify

    assert verify(source.parent.parent, os.environ.get("TEST_SESSION", "")) == source
    return source
