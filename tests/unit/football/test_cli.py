"""CLI parsing and dispatch with import/database boundaries replaced."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from football import cli
from settings.base import ConfigurationError


@pytest.fixture
def isolated_cli(monkeypatch):
    events = []
    session = object()

    @contextmanager
    def transaction():
        events.append("begin")
        try:
            yield session
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")

    database = SimpleNamespace(engine=SimpleNamespace(url="test-url"), transaction=transaction)
    prototype = Mock(return_value={"teams": 2})
    historical = Mock(return_value=SimpleNamespace(as_dict=lambda: {"z": 2, "a": 1}))
    validate = Mock()
    monkeypatch.setattr(cli, "import_historical_dataset", historical)
    app = Flask(__name__)
    cli.register_commands(app, database)
    return SimpleNamespace(
        runner=app.test_cli_runner(),
        database=database,
        session=session,
        events=events,
        prototype=prototype,
        historical=historical,
        validate=validate,
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--unknown"],
        ["--target", "invalid"],
        ["--dry-run"],
        ["--dataset", "unknown"],
        ["--dataset", "womens-world-cup-2023"],
    ],
)
def test_invalid_arguments_never_dispatch(isolated_cli, arguments):
    c = isolated_cli
    result = c.runner.invoke(args=["import-football", *arguments])
    assert result.exit_code == 2
    assert "Error:" in result.output
    c.prototype.assert_not_called()
    c.historical.assert_not_called()
    assert c.events == []


def test_historical_options_are_forwarded_without_prototype_transaction(isolated_cli, tmp_path):
    c = isolated_cli
    result = c.runner.invoke(
        args=[
            "import-football",
            "--dataset",
            "womens-world-cup-2023",
            "--directory",
            str(tmp_path),
            "--target",
            "test",
            "--expect-host",
            "postgres",
            "--expect-database",
            "goalstats_test_unit",
            "--dry-run",
        ]
    )
    assert result.exit_code == 0
    args, kwargs = c.historical.call_args
    assert args[:2] == (c.database, tmp_path)
    assert (
        args[2].target,
        args[2].expect_host,
        args[2].expect_database,
        args[2].confirm_production,
    ) == (
        "test",
        "postgres",
        "goalstats_test_unit",
        False,
    )
    assert kwargs == {"dry_run": True, "dataset_id": "womens-world-cup-2023"}
    assert result.output == json.dumps({"a": 1, "z": 2}, sort_keys=True) + "\n"
    c.prototype.assert_not_called()
    assert c.events == []


def test_historical_configuration_failure_is_nonzero_and_redacted(isolated_cli, tmp_path):
    c = isolated_cli
    c.historical.side_effect = ConfigurationError("private connection string")
    result = c.runner.invoke(
        args=[
            "import-football",
            "--dataset",
            "womens-world-cup-2023",
            "--directory",
            str(tmp_path),
        ]
    )
    assert result.exit_code == 1
    assert "Invalid import target configuration." in result.output
    assert "private" not in result.output
    assert c.events == []
