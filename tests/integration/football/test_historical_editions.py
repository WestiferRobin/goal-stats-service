"""All nine editions through the guarded CLI, using synthetic CSV and owned PostgreSQL."""

import csv
import hashlib
import io
import json
from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import func, select, text

from football.cli import register_commands
from football.historical_dataset import APPROVED_DATASETS, load_manifest
from football.historical_import import import_historical_dataset
from models.competition import Competition
from models.hold.football import FootballHistory, FootballSnapshot, FootballTeam
from models.match import Match
from models.team import Team

pytestmark = pytest.mark.postgres


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


def snapshot(database):
    with database.transaction() as session:
        return {
            model.__tablename__: session.execute(select(model.__table__)).all()
            for model in (Team, Competition, Match, FootballTeam, FootballHistory, FootballSnapshot)
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


def test_all_editions_cli_dry_run_import_repeat_and_shared_identities(
    import_database, import_target, edition_source, monkeypatch
):
    directory, manifests = edition_source

    def forbidden(*args, **kwargs):
        pytest.fail("Historical import must never read prototype CSVs")

    monkeypatch.setattr("football.cli.import_datasets", forbidden)
    before = snapshot(import_database)
    for dataset, manifest in manifests.items():
        result = invoke(import_database, import_target, directory, dataset, "--dry-run")
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["matches_inserted"] == manifest.expected_counts.matches
        assert not summary["committed"]
    assert snapshot(import_database) == before

    # Import 2023 first so later editions must reuse its team IDs without rewriting anything.
    datasets = [APPROVED_DATASETS[-1], *APPROVED_DATASETS[:-1]]
    original_2023 = None
    for dataset in datasets:
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["matches_inserted"] == manifests[dataset].expected_counts.matches
        if dataset.endswith("2023"):
            original_2023 = snapshot(import_database)
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Team)) == 44
        assert session.scalar(select(func.count()).select_from(Competition)) == 9
        assert session.scalar(select(func.count()).select_from(Match)) == 348
        for manifest in manifests.values():
            competition = session.scalar(
                select(Competition).where(
                    Competition.edition_label == manifest.competition.edition_label
                )
            )
            matches = session.scalars(
                select(Match).where(Match.competition_id == competition.competition_id)
            ).all()
            assert len(matches) == manifest.expected_counts.matches
            assert len({m.home_team_id for m in matches} | {m.away_team_id for m in matches}) == (
                manifest.expected_counts.teams
            )
            assert (
                sum(m.home_score + m.away_score for m in matches) == manifest.approval.total_goals
            )
    after = snapshot(import_database)
    assert original_2023 is not None
    for table in ("teams", "competitions", "matches"):
        assert all(row in after[table] for row in original_2023[table])
    for table in ("football_teams", "football_history", "football_snapshots"):
        assert after[table] == before[table] == []
    for dataset, manifest in manifests.items():
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["unchanged"] == manifest.expected_counts.matches
        assert summary["teams_inserted"] == summary["competitions_inserted"] == 0
        assert summary["matches_inserted"] == 0
        dry = invoke(import_database, import_target, directory, dataset, "--dry-run")
        assert dry.exit_code == 0, dry.output
    assert snapshot(import_database) == after


@pytest.mark.parametrize("failure", ["conflict", "wrong_target", "old_head", "missing_source"])
def test_earlier_edition_failure_preserves_records(
    import_database, import_target, edition_source, failure
):
    directory, _ = edition_source
    dataset = "womens-world-cup-1991"
    if failure == "conflict":
        import_historical_dataset(import_database, directory, import_target, dataset_id=dataset)
        with import_database.transaction() as session:
            session.execute(text("UPDATE matches SET home_score = 100 WHERE match_id = 1"))
    elif failure == "old_head":
        with import_database.transaction() as session:
            session.execute(text("UPDATE alembic_version SET version_num = 'd94f81ab2301'"))
    elif failure == "missing_source":
        (directory / "results.csv").unlink()
    before = snapshot(import_database)
    options = ("--expect-host", "wrong-host") if failure == "wrong_target" else ()
    result = invoke(import_database, import_target, directory, dataset, *options)
    assert result.exit_code != 0
    assert snapshot(import_database) == before
    assert not json.loads(next(s for s in result.output.splitlines() if s.startswith("{")))[
        "committed"
    ]


@pytest.mark.parametrize("dataset", ["womens-world-cup-2027", "../2023.json", "all-approved"])
def test_unknown_cli_dataset_never_imports(import_database, import_target, tmp_path, dataset):
    before = snapshot(import_database)
    result = invoke(import_database, import_target, tmp_path, dataset)
    assert result.exit_code != 0 and "Unknown historical dataset" in result.output
    assert snapshot(import_database) == before


def test_historical_cli_requires_explicit_directory(import_database):
    app = Flask(__name__)
    register_commands(app, import_database)
    result = app.test_cli_runner().invoke(
        args=["import-football", "--dataset", "womens-world-cup-1991"]
    )
    assert result.exit_code != 0 and "explicit --directory" in result.output


def test_later_transaction_failure_preserves_prior_commits_and_retry(
    import_database, import_target, edition_source
):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    directory, _ = edition_source
    for dataset in APPROVED_DATASETS[:2]:
        assert invoke(import_database, import_target, directory, dataset).exit_code == 0
    before = snapshot(import_database)

    def interrupt_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO matches"):
            raise OperationalError(statement, None, RuntimeError("disposable injected failure"))

    event.listen(import_database.engine, "before_cursor_execute", interrupt_insert)
    try:
        failure = invoke(import_database, import_target, directory, APPROVED_DATASETS[2])
        assert failure.exit_code != 0
        assert "not confirmed committed" in failure.output
    finally:
        event.remove(import_database.engine, "before_cursor_execute", interrupt_insert)
    assert snapshot(import_database) == before
    for dataset in APPROVED_DATASETS:
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        if dataset in APPROVED_DATASETS[:2]:
            assert json.loads(result.output)["matches_inserted"] == 0
    after = snapshot(import_database)
    assert [len(after[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]
    for table in ("teams", "competitions", "matches"):
        assert all(row in after[table] for row in before[table])
