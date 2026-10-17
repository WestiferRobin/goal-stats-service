import json

import pytest
from flask import Flask
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from football.cli import register_commands
from models.competition import Competition
from models.match import Match
from models.team import Team
from tests.fixtures.historical_database import invoke


@pytest.mark.postgres
@pytest.mark.parametrize("dataset", ["womens-world-cup-2027", "../2023.json", "all-approved"])
def test_unknown_cli_dataset_never_imports(import_database, import_target, tmp_path, dataset):
    before = edition_snapshot(import_database)
    result = invoke(import_database, import_target, tmp_path, dataset)
    assert result.exit_code != 0 and "Unknown historical dataset" in result.output
    assert edition_snapshot(import_database) == before


def edition_snapshot(database):
    with database.transaction() as session:
        return {
            model.__tablename__: session.execute(select(model.__table__)).all()
            for model in (Team, Competition, Match)
        }


@pytest.mark.postgres
def test_historical_cli_requires_explicit_directory(import_database):
    app = Flask(__name__)
    register_commands(app, import_database)
    result = app.test_cli_runner().invoke(
        args=["import-football", "--dataset", "womens-world-cup-1991"]
    )
    assert result.exit_code != 0 and "--directory" in result.output


@pytest.mark.postgres
@pytest.mark.parametrize("removed", ["--target", "--expect-host", "--expect-database"])
def test_missing_target_arguments(cli, pinned_fixture, import_target, removed):
    args = arguments(pinned_fixture, import_target)
    index = args.index(removed)
    del args[index : index + 2]
    result = cli.invoke(args=args)
    assert result.exit_code != 0
    assert not summary(result)["committed"]


def summary(result):
    return json.loads(next(line for line in result.output.splitlines() if line.startswith("{")))


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


@pytest.fixture
def cli(import_database):
    app = Flask(__name__)
    register_commands(app, import_database)
    return app.test_cli_runner()


@pytest.mark.postgres
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


@pytest.mark.postgres
def test_cloud_confirmation_does_not_bypass_tls(cli, pinned_fixture, import_target):
    args = arguments(pinned_fixture, import_target)
    args[args.index("--target") + 1] = "cloud"
    result = cli.invoke(args=args + ["--confirm-production"])
    assert result.exit_code != 0 and "verify-full" in result.output


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
def test_checksum_failure_is_nonzero(cli, import_target, pinned_fixture):
    (pinned_fixture.directory / "results.csv").write_text("not pinned")
    result = cli.invoke(args=arguments(pinned_fixture, import_target))
    assert result.exit_code != 0 and "checksum" in result.output


@pytest.mark.postgres
def test_no_option_importer_is_rejected_without_writes(cli, import_database):
    before = edition_snapshot(import_database)
    result = cli.invoke(args=["import-football"])
    assert result.exit_code == 2
    assert edition_snapshot(import_database) == before


@pytest.mark.postgres
def test_dry_run_requires_explicit_dataset(cli):
    result = cli.invoke(args=["import-football", "--dry-run"])
    assert result.exit_code != 0 and "--dataset" in result.output
