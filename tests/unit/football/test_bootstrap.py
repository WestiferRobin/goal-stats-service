"""The deployment CLI cannot select a local target or reveal failure details."""

import pytest

from football import bootstrap as boot


def test_production_confirmation_required(monkeypatch):
    monkeypatch.setattr("sys.argv", ["bootstrap"])
    with pytest.raises(SystemExit) as error:
        boot.main()
    assert error.value.code == 2


@pytest.mark.parametrize("mode", ["local", "dev", "test"])
def test_bootstrap_refuses_nonproduction(monkeypatch, explicit_config, mode, capsys):
    from settings.environment import load_application

    settings = load_application({**explicit_config, "APP_ENV": mode})
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-production"])
    monkeypatch.setattr(boot, "load_application", lambda: settings)
    monkeypatch.setattr(boot, "Database", lambda _: pytest.fail("No database should be created"))
    with pytest.raises(SystemExit) as error:
        boot.main()
    assert error.value.code == 1
    assert "no startup authorized" in capsys.readouterr().err


def test_raw_errors_are_redacted(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-production"])

    def fail():
        raise RuntimeError("private-credential-value")

    monkeypatch.setattr(boot, "load_application", fail)
    with pytest.raises(SystemExit) as error:
        boot.main()
    assert error.value.code == 1
    assert "private-credential-value" not in capsys.readouterr().err


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ('could not translate host name "private-host" to address', "CONNECTION"),
        ("connection refused: private-host", "CONNECTION"),
        ('password authentication failed for user "private-user"', "AUTHENTICATION"),
        ("fe_sendauth: no password supplied", "AUTHENTICATION"),
        ("SSL error: certificate verify failed", "TLS"),
        ('server certificate for "private-host" does not match host name', "TLS"),
        ('root certificate file "/private/path" does not exist', "TLS"),
    ],
)
def test_driver_diagnostics_are_redacted(monkeypatch, capsys, message, category):
    from psycopg import OperationalError
    from sqlalchemy.exc import OperationalError as WrappedError

    def fail():
        try:
            raise WrappedError("private-sql", {}, OperationalError(message))
        except WrappedError:
            raise RuntimeError("private-credential-value") from None

    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-production"])
    monkeypatch.setattr(boot, "load_application", fail)
    with pytest.raises(SystemExit) as error:
        boot.main()
    assert error.value.code == 1
    assert capsys.readouterr().err == (
        "Production bootstrap failed; no startup authorized. "
        f"Category: {boot.FailureCategory[category].value}.\n"
    )


def test_authentication_sqlstate_and_identity():
    from psycopg.errors import InvalidPassword

    from settings.base import ConfigurationError

    diagnostic = boot.BootstrapDiagnostic(boot.FailureCategory.MIGRATION)
    assert diagnostic.category(InvalidPassword("secret")) == boot.FailureCategory.AUTHENTICATION
    assert (
        diagnostic.category(ConfigurationError("Database hostname does not match --expect-host."))
        == boot.FailureCategory.IDENTITY
    )
    # Arbitrary application text must not masquerade as a driver failure.
    assert diagnostic.category(RuntimeError("certificate verify failed")) == diagnostic.stage


@pytest.mark.parametrize("stage", list(boot.FailureCategory))
def test_cli_reports_only_fixed_stage_labels(monkeypatch, capsys, stage):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from settings.base import Environment

    database = Mock()
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-production"])
    monkeypatch.setattr(
        boot,
        "load_application",
        lambda: SimpleNamespace(
            core=SimpleNamespace(app_env=Environment.PRODUCTION),
            database=None,
        ),
    )
    monkeypatch.setattr(boot, "Database", lambda _: database)

    def fail(database, target, directory, diagnostic):
        diagnostic.stage = stage
        raise RuntimeError(
            "postgresql://private-user:private-password@private-host/db?token=secret"
        )

    monkeypatch.setattr(boot, "bootstrap", fail)
    with pytest.raises(SystemExit) as error:
        boot.main()
    assert error.value.code == 1
    assert capsys.readouterr().err == (
        f"Production bootstrap failed; no startup authorized. Category: {stage.value}.\n"
    )
    database.dispose.assert_called_once()
