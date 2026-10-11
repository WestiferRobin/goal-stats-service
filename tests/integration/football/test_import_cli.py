import json

import pytest
from flask import Flask
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from football.cli import register_commands
from models.catalog import Match
from models.football import FootballHistory, FootballTeam

pytestmark = pytest.mark.postgres


@pytest.fixture
def cli(import_database):
    app = Flask(__name__)
    register_commands(app, import_database)
    return app.test_cli_runner()


def arguments(fixture, target):
    return [
        "import-football",
        "--dataset",
        "womens-world-cup-2023",
        "--directory",
        str(fixture.directory),
        "--target",
        target.target,
        "--expect-host",
        target.expect_host,
        "--expect-database",
        target.expect_database,
    ]


def summary(result):
    return json.loads(next(line for line in result.output.splitlines() if line.startswith("{")))


@pytest.mark.parametrize("removed", ["--target", "--expect-host", "--expect-database"])
def test_missing_target_arguments(cli, pinned_fixture, import_target, removed):
    args = arguments(pinned_fixture, import_target)
    index = args.index(removed)
    del args[index : index + 2]
    result = cli.invoke(args=args)
    assert result.exit_code != 0
    assert not summary(result)["committed"]


@pytest.mark.parametrize(
    "option,value,message",
    [
        ("--expect-host", "wrong-host", "hostname"),
        ("--expect-database", "wrong-database", "name"),
        ("--target", "local", "Local target"),
        ("--target", "cloud", "confirm-production"),
    ],
)
def test_mismatched_target_rejected(cli, pinned_fixture, import_target, option, value, message):
    args = arguments(pinned_fixture, import_target)
    args[args.index(option) + 1] = value
    result = cli.invoke(args=args)
    assert result.exit_code != 0 and message in result.output
    assert not summary(result)["committed"]


def test_cloud_confirmation_does_not_bypass_tls(cli, pinned_fixture, import_target):
    args = arguments(pinned_fixture, import_target)
    args[args.index("--target") + 1] = "cloud"
    result = cli.invoke(args=args + ["--confirm-production"])
    assert result.exit_code != 0 and "verify-full" in result.output


@pytest.mark.parametrize(
    "schema_change",
    [
        "UPDATE alembic_version SET version_num = 'd94f81ab2301'",
        "ALTER TABLE matches RENAME COLUMN city TO missing_city",
    ],
)
def test_missing_schema_is_actionable(
    cli, import_database, pinned_fixture, import_target, schema_change
):
    with import_database.transaction() as session:
        session.execute(text(schema_change))
    result = cli.invoke(args=arguments(pinned_fixture, import_target))
    assert result.exit_code != 0
    assert "migration" in result.output or "alembic upgrade head" in result.output
    assert not summary(result)["committed"]


def test_dry_run_committed_and_repeat_summaries(cli, pinned_fixture, import_target):
    args = arguments(pinned_fixture, import_target)
    dry = cli.invoke(args=args + ["--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert summary(dry)["insert_counts"] == "proposed" and not summary(dry)["committed"]
    first = cli.invoke(args=args)
    assert first.exit_code == 0, first.output
    expected = {
        "dataset",
        "source",
        "source_version",
        "rows_read",
        "rows_selected",
        "rows_filtered_out",
        "teams_inserted",
        "competitions_inserted",
        "matches_inserted",
        "unchanged",
        "duplicate_input",
        "rejected",
        "conflicts",
        "committed",
    }
    assert expected <= summary(first).keys()
    assert summary(first)["committed"] and summary(first)["matches_inserted"] == 64
    repeat = cli.invoke(args=args)
    assert repeat.exit_code == 0
    assert summary(repeat)["matches_inserted"] == 0 and summary(repeat)["unchanged"] == 64


def test_database_failure_is_nonzero_and_redacted(
    cli, import_database, import_target, pinned_fixture, monkeypatch
):
    def fail(*args, **kwargs):
        raise OperationalError(
            "postgresql://goalstats:secret123@host/db", {}, Exception("secret123")
        )

    monkeypatch.setattr(import_database, "transaction", fail)
    result = cli.invoke(args=arguments(pinned_fixture, import_target))
    assert result.exit_code != 0
    assert "secret123" not in result.output and "postgresql://" not in result.output
    assert summary(result)["matches_inserted"] == 0
    assert not summary(result)["committed"]


def test_checksum_failure_is_nonzero(cli, import_target, pinned_fixture):
    (pinned_fixture.directory / "results.csv").write_text("not pinned")
    result = cli.invoke(args=arguments(pinned_fixture, import_target))
    assert result.exit_code != 0 and "checksum" in result.output


def test_existing_no_option_importer_remains_compatible(cli, import_database):
    for _ in range(2):
        result = cli.invoke(args=["import-football"])
        assert result.exit_code == 0, result.output
        assert "Import complete:" in result.output
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(FootballTeam)) == 32
        assert session.scalar(select(func.count()).select_from(FootballHistory)) == 16
        assert session.scalar(select(func.count()).select_from(Match)) == 0


def test_dry_run_requires_explicit_dataset(cli):
    result = cli.invoke(args=["import-football", "--dry-run"])
    assert result.exit_code != 0 and "require --dataset" in result.output
