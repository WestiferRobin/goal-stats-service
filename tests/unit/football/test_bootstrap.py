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
