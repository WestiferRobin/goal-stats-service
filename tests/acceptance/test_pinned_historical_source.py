"""Explicit opt-in acceptance: mount the pinned source at /input/results.csv read-only.

Excluded from make test's unit/integration selection; never substitutes synthetic data.
Uses the same ownership-verified disposable PostgreSQL fixtures as ordinary tests.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import inspect

from football.historical_dataset import APPROVED_DATASETS, load_manifest
from tests.integration.football.test_empty_startup import snapshot
from tests.integration.football.test_historical_editions import invoke
from tests.integration.football.test_historical_sql import verify

pytestmark = pytest.mark.postgres


def test_pinned_source_import_repeat_and_application_restart(
    import_database, import_target, postgres_config, app_factory, monkeypatch, scenario_body
):
    source = Path("/input/results.csv")
    assert source.is_file(), "Mount the approved pinned CSV at /input/results.csv read-only"
    assert " ro," in next(
        line for line in Path("/proc/self/mountinfo").read_text().splitlines() if " /input " in line
    ), "Acceptance source mount must be read-only"
    before = snapshot(import_database)
    assert all(not rows for table, rows in before.items() if table != "alembic_version")
    monkeypatch.setattr("main.Database", lambda _: import_database)
    app = app_factory(postgres_config)
    client = app.test_client()
    spec = client.get("/swagger/v1/swagger.json").json
    for path in ("/health", "/ready", "/api/v1/teams"):
        assert client.get(path).status_code == 200
    for path in ("teams", "competitions", "matches"):
        assert client.get(f"/api/v1/catalog/{path}").json == []
    assert snapshot(import_database) == before

    def forbidden(*args, **kwargs):
        pytest.fail("Historical CLI must never invoke prototype loading")

    monkeypatch.setattr("football.cli.import_datasets", forbidden)
    for dataset in APPROVED_DATASETS:
        dry = invoke(import_database, import_target, source.parent, dataset, "--dry-run")
        assert dry.exit_code == 0, dry.output
        assert not json.loads(dry.output)["committed"]
    assert snapshot(import_database) == before
    preserved_user_records = None
    original_2023 = None
    reports = []
    for dataset in (APPROVED_DATASETS[-1], *APPROVED_DATASETS[:-1]):
        result = invoke(import_database, import_target, source.parent, dataset)
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["committed"]
        assert report["matches_inserted"] == load_manifest(dataset).expected_counts.matches
        reports.append(report)
        if dataset.endswith("2023"):
            original_2023 = snapshot(import_database)
            teams = client.get("/api/v1/catalog/teams").json
            scenario_body.update(team1_id=teams[0]["team_id"], team2_id=teams[1]["team_id"])
            created = client.post("/api/v1/scenarios", json=scenario_body)
            assert created.status_code == 201, created.json
            prediction = client.post(f"/api/v1/scenarios/{created.json['scenario_id']}/predictions")
            assert prediction.status_code == 201, prediction.json
            preserved_user_records = snapshot(import_database)
    after = snapshot(import_database)
    assert [len(after[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]
    assert original_2023 is not None
    for table in ("teams", "competitions", "matches"):
        assert set(original_2023[table]) <= set(after[table])
    for table in (
        "football_teams",
        "football_history",
        "football_snapshots",
    ):
        assert after[table] == before[table] == []
    assert preserved_user_records is not None
    for table in ("scenarios", "predictions"):
        assert after[table] == preserved_user_records[table]
        assert len(after[table]) == 1
    check = verify(import_database, complete=True, database_name=import_target.expect_database)
    assert check["acceptance_passed"] == 1
    for dataset in APPROVED_DATASETS:
        result = invoke(import_database, import_target, source.parent, dataset)
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["teams_inserted"] == report["competitions_inserted"] == 0
        assert report["matches_inserted"] == 0
        assert report["unchanged"] == load_manifest(dataset).expected_counts.matches
    assert snapshot(import_database) == after

    # Recreate the Flask application and connection pool against the same disposable schema.
    app.extensions["goalstats_cache"].close()
    import_database.dispose()
    restarted = app_factory(postgres_config).test_client()
    assert restarted.get("/ready").status_code == 200
    assert restarted.get("/swagger/v1/swagger.json").json == spec
    assert snapshot(import_database) == after
    assert (
        verify(import_database, complete=True, preservation=check["preservation"])[
            "acceptance_passed"
        ]
        == 1
    )
    with import_database.engine.connect() as connection:
        inspector = inspect(connection)
        prototype = {"football_teams", "football_history", "football_snapshots"}
        for table in inspector.get_table_names():
            for fk in inspector.get_foreign_keys(table):
                assert (table in prototype) == (fk["referred_table"] in prototype)
    print("Pinned-source acceptance: 44 teams, 9 competitions, 348 matches; repeat inserts=0")
    print(json.dumps(reports, sort_keys=True))
