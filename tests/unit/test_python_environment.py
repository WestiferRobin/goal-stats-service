"""Maintained Python setup and diagnostic safety properties from legacy tooling."""

import sys
from types import SimpleNamespace

import pytest
import python_environment as host


def test_valid_environment_is_reused_without_install(monkeypatch, tmp_path):
    (tmp_path / ".venv").mkdir()
    calls = []
    monkeypatch.setattr(host, "verify", lambda *a, **k: {"missing": []})
    monkeypatch.setattr(host.subprocess, "run", lambda *a, **k: calls.append(a))
    host.bootstrap(tmp_path)
    assert calls == []


def test_missing_dependencies_install_only_inside_venv(monkeypatch, tmp_path):
    (tmp_path / ".venv").mkdir()
    calls = []
    monkeypatch.setattr(host, "verify", lambda *a, **k: {"missing": ["Flask"]})
    monkeypatch.setattr(host.subprocess, "run", lambda *a, **k: calls.append((a, k)))
    host.bootstrap(tmp_path)
    command = calls[0][0][0]
    assert command[0] == str(tmp_path / ".venv/bin/python")
    assert command[-1] == str(tmp_path / "requirements.txt")
    assert calls[0][1]["env"]["PIP_REQUIRE_VIRTUALENV"] == "true"


def test_wrong_existing_interpreter_is_not_replaced(monkeypatch, tmp_path):
    executable = tmp_path / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.write_text("existing interpreter")
    monkeypatch.setattr(host, "probe", lambda *a: {"version": [3, 13]})
    with pytest.raises(RuntimeError, match="Python 3.12"):
        host.bootstrap(tmp_path)
    assert executable.read_text() == "existing interpreter"


def test_symlink_venv_refused(tmp_path):
    (tmp_path / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        host.verify(tmp_path)


def test_missing_venv_has_setup_guidance(tmp_path):
    with pytest.raises(RuntimeError, match="make setup"):
        host.verify(tmp_path)


def test_direct_missing_dependencies_is_actionable():
    import subprocess
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "src/main.py")], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "make setup" in result.stderr
    assert "Traceback" not in result.stderr


def test_dependency_mismatch_does_not_print_values(monkeypatch, tmp_path):
    executable = tmp_path / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(
        host,
        "probe",
        lambda *a: {
            "version": [3, 12],
            "prefix": str(tmp_path / ".venv"),
            "base": "/base",
            "missing": ["Flask"],
        },
    )
    with pytest.raises(RuntimeError, match="Flask.*make setup"):
        host.verify(tmp_path)


def test_bootstrap_wrong_python_starts_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(host.sys, "version_info", (3, 13))
    monkeypatch.setattr(host.subprocess, "run", lambda *a, **k: pytest.fail("unexpected process"))
    with pytest.raises(RuntimeError, match="Python 3.12"):
        host.bootstrap(tmp_path)
    assert not (tmp_path / ".venv").exists()


def test_pip_check_failure_is_actionable(monkeypatch, tmp_path):
    executable = tmp_path / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(
        host,
        "probe",
        lambda *a: {
            "version": [3, 12],
            "prefix": str(tmp_path / ".venv"),
            "base": "/base",
            "missing": [],
        },
    )
    monkeypatch.setattr(host.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="dependency consistency"):
        host.verify(tmp_path)


def test_bootstrap_cli_dispatch(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(host.sys, "argv", ["python_environment.py", "bootstrap"])
    monkeypatch.setattr(host, "bootstrap", lambda root: calls.append(root))
    host.main()
    assert calls == [__import__("pathlib").Path(host.__file__).resolve().parents[2]]
