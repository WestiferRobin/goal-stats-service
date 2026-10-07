"""Bootstrap must never replace an existing interpreter or reinstall valid pins."""

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


def test_certification_configuration_never_queries_developer_docker(monkeypatch, tmp_path):
    import workflow
    from validation.certify_workflows import certify_configuration

    monkeypatch.setattr(workflow, "run", lambda *a, **k: pytest.fail("developer Docker queried"))
    certify_configuration(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == {".env.local", ".env.test"}


def test_direct_missing_dependencies_is_actionable():
    import subprocess

    from workflow import ROOT

    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "src/main.py")], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "make setup" in result.stderr
    assert "Traceback" not in result.stderr


def test_doctor_authentication_failure_is_read_only_and_redacted(monkeypatch):
    import diagnostics

    commands = []

    def compose(*args, **kwargs):
        commands.append(args)
        return SimpleNamespace(stdout="container" if args[0] == "ps" else "", returncode=1)

    stack = SimpleNamespace(
        compose=compose,
        project="owned",
        env="local",
        settings={"POSTGRES_PASSWORD": "private-password"},
    )
    monkeypatch.setattr(
        diagnostics,
        "inspect_container",
        lambda identity: {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "owned",
                    "com.docker.compose.service": "postgres",
                }
            },
        },
    )
    with pytest.raises(RuntimeError, match="Restore original") as error:
        diagnostics.check_database(stack)
    assert "private-password" not in str(error.value)
    assert commands[-1][-1] == "SELECT 1"
    assert all(command[0] in {"ps", "exec"} for command in commands)


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


def test_doctor_checks_test_policy_before_port_diagnosis(monkeypatch, tmp_path):
    import diagnostics
    import workflow

    monkeypatch.setattr(workflow, "ROOT", tmp_path)
    monkeypatch.setattr(host, "verify", lambda root: None)
    monkeypatch.setattr(workflow.shutil, "which", lambda name: name)
    monkeypatch.setattr(workflow, "run", lambda *a, **k: SimpleNamespace(stdout=""))
    monkeypatch.setattr(workflow, "read_settings", lambda *a: {})
    monkeypatch.setattr(
        diagnostics, "check_ports", lambda root: pytest.fail("invalid policy accepted")
    )
    for name in (
        "requirements.txt",
        "Dockerfile",
        "Makefile",
        "alembic.ini",
        "alembic/env.py",
        "docker/compose.local.yml",
        "docker/compose.dev.yml",
        "docker/compose.test.yml",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    path = tmp_path / ".env.test"
    path.write_text("DATABASE_URL=private-value\n")
    path.chmod(0o600)
    with pytest.raises(workflow.schema.ConfigurationError, match=r"\.env.test:1") as error:
        workflow.doctor()
    assert "private-value" not in str(error.value)


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
    assert calls == [__import__("pathlib").Path(host.__file__).resolve().parents[1]]
