"""Offline SQL export reproducibility and responsibility boundaries."""

import json
from pathlib import Path

import export_football_sql as exporter
import pytest
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://offline:offline@127.0.0.1/goalstats_test_export"
    )

    def forbidden(*args, **kwargs):
        pytest.fail("SQL export must not open a database connection")

    monkeypatch.setattr(Engine, "connect", forbidden)


def test_schema_exports_match_without_reading_prototype(tmp_path, monkeypatch, offline):
    def forbidden():
        pytest.fail("Schema export must not read prototype CSVs")

    assert not hasattr(exporter, "read_datasets")
    exporter.export(tmp_path, mode="schema")
    paths = sorted(tmp_path.glob("*.sql"))
    assert len(paths) == 1
    for path in paths:
        assert path.read_bytes() == (ROOT / "sql" / path.name).read_bytes()
    assert not (tmp_path / "prototype").exists()


def test_legacy_export_all_keeps_both_outputs(tmp_path, offline):
    exporter.export(tmp_path)
    assert len(list(tmp_path.rglob("*.sql"))) == 1


def test_sql_approved_facts_match_checked_in_coverage():
    sql = (ROOT / "sql/verify_historical_import.sql").read_text()
    expected = json.loads(sql.split("$approved$")[1])
    coverage = json.loads((ROOT / "data/verification/womens-world-cup-coverage.json").read_text())
    assert expected == [
        {
            "edition": e["dataset_id"][-4:],
            "start": e["date_from"],
            "finish": e["date_to"],
            "matches": e["matches"],
            "participants": [p.casefold() for p in e["participants"]],
            "goals": e["total_goals"],
        }
        for e in coverage["editions"]
    ]
    for forbidden in (
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "TRUNCATE ",
        "DROP ",
        "ALTER ",
        "CREATE ",
        "nextval(",
    ):
        assert forbidden.lower() not in sql.lower()
    assert "REPEATABLE READ READ ONLY" in sql
