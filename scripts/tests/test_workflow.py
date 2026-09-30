"""Provider-free tests for destructive-workflow guards and configuration parsing."""

import pytest
from workflow import Stack, read_settings


@pytest.mark.parametrize("environment", ["production", "locla", "", "LOCAL"])
def test_unknown_environment_refused_before_configuration_or_docker(environment):
    with pytest.raises(RuntimeError, match="ENV must"):
        Stack(environment)


def test_persistent_stack_refuses_volume_deletion():
    stack = Stack("local", settings={"POSTGRES_PASSWORD": "not-used", "APP_PORT": "5100"})
    with pytest.raises(RuntimeError, match="persistent"):
        stack.stop(volumes=True)


@pytest.mark.parametrize("project", ["other-project", "goalstats-template-py-local", ""])
def test_disposable_stack_requires_owned_identity(project):
    with pytest.raises(RuntimeError, match="Disposable project"):
        Stack("test", project=project, settings={})


def test_environment_parser_preserves_values_without_shell_execution(tmp_path):
    config = tmp_path / ".env.local"
    config.write_text(
        "# comment\nPOSTGRES_PASSWORD=abcdefghijklmnop\n"
        "DEV_POSTGRES_PASSWORD=ponmlkjihgfedcba\nLOCAL_APP_PORT=5101\n"
    )
    config.chmod(0o600)
    assert read_settings(config)["POSTGRES_PASSWORD"] == "abcdefghijklmnop"
    assert read_settings(config)["APP_PORT"] == "5101"
    config.write_text(
        "POSTGRES_PASSWORD=$(touch unexpected)\nDEV_POSTGRES_PASSWORD=ponmlkjihgfedcba\n"
    )
    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        read_settings(config)
    assert not (tmp_path / "unexpected").exists()


def test_ambient_database_and_compose_settings_do_not_choose_test_resources(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "developer-database")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "unrelated")
    stack = Stack(
        "test",
        project="goalstats-template-py-test-a123",
        settings={"POSTGRES_PASSWORD": "test-only"},
    )
    assert "unrelated" not in stack.args
    assert "COMPOSE_PROJECT_NAME" not in stack.process_env
    assert stack.service == "runner"
    assert stack.settings == {"POSTGRES_PASSWORD": "test-only"}


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("unit", ["tests/unit"]),
        ("tooling", ["scripts/tests"]),
        ("integration", ["tests/integration"]),
        ("test", ["tests/unit", "tests/integration"]),
        ("coverage", ["tests/unit", "tests/integration"]),
    ],
)
def test_suite_selection_and_cleanup(monkeypatch, mode, expected):
    import workflow

    commands, stops = [], []
    monkeypatch.setattr(workflow, "build_tooling", lambda: None)
    monkeypatch.setattr(workflow, "tool_command", lambda *args: commands.append(args))

    class TestStack:
        def __init__(self, *args, **kwargs):
            pass

        def providers(self):
            pass

        def command(self, *args):
            commands.append(args)

        def stop(self, *, volumes):
            stops.append(volumes)

    monkeypatch.setattr(workflow, "Stack", TestStack)
    workflow.tests(mode)
    pytest_commands = [cmd for cmd in commands if cmd[0] == "pytest"]
    assert len(pytest_commands) == 1
    assert [
        arg for arg in pytest_commands[0] if arg.startswith(("tests/", "scripts/tests"))
    ] == expected
    assert stops == ([] if mode in {"unit", "tooling"} else [True])


def test_setup_preserves_existing_private_configuration(monkeypatch, tmp_path):
    import python_environment
    import workflow

    monkeypatch.setattr(python_environment, "bootstrap", lambda root: None)

    monkeypatch.setattr(workflow.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(
        workflow, "run", lambda *args, **kwargs: __import__("types").SimpleNamespace(stdout="")
    )
    workflow.setup(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    workflow.setup(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in tmp_path.iterdir())


def test_smoke_failure_preserves_exit_and_cleans_stack(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    from smoke import runtime

    events = []
    stack = SimpleNamespace(
        project="goalstats-template-py-cert-a123",
        compose=lambda *args: events.append("build"),
        migrate=lambda: events.append("migrate"),
        start=lambda: events.append("start"),
        stop=lambda **kwargs: events.append(("stop", kwargs)),
    )
    monkeypatch.setattr(runtime, "inventory", lambda: {"containers": {"unrelated"}})
    monkeypatch.setattr(runtime, "fresh", lambda env: stack)
    monkeypatch.setattr(runtime, "build_tooling", lambda: None)
    monkeypatch.setattr(runtime, "assert_absent", lambda project: events.append("absent"))

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "pytest")

    monkeypatch.setattr(runtime, "run_smoke", fail)
    with pytest.raises(subprocess.CalledProcessError) as error:
        runtime.smoke()
    assert error.value.returncode == 1
    assert events[-2:] == [("stop", {"volumes": True}), "absent"]


def test_smoke_refuses_developer_stack():
    from smoke.runtime import run_smoke

    with pytest.raises(RuntimeError, match="owned disposable"):
        run_smoke(Stack("dev", settings={"POSTGRES_PASSWORD": "not-used", "APP_PORT": "5200"}))


def test_default_collection_excludes_smoke():
    import os
    import subprocess
    import sys

    from workflow import ROOT

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "tests/smoke/" not in result.stdout
    assert "tests/unit/" in result.stdout and "tests/integration/" in result.stdout


@pytest.mark.parametrize("mode", ["dev", "init", "seed", "quick-test"])
def test_simple_local_workflow(monkeypatch, mode):
    import host_development
    import python_environment
    import workflow

    events = []
    monkeypatch.setattr(workflow, "setup", lambda: events.append("setup"))
    monkeypatch.setattr(python_environment, "verify", lambda root: events.append("verify"))
    monkeypatch.setattr(workflow, "Stack", lambda mode: type("Stack", (), {"settings": {}})())
    monkeypatch.setattr(
        host_development, "local_providers", lambda stack: events.append("providers")
    )
    monkeypatch.setattr(
        workflow.schema,
        "application",
        lambda *a, **k: {
            "HOST_APP_PORT": "5300",
            "DATABASE_URL": "canonical-local",
            "APP_ENV": "local",
        },
    )
    monkeypatch.setenv("DATABASE_URL", "wrong-database")

    def run(args, **kwargs):
        events.append([str(arg) for arg in args])
        if "env" in kwargs:
            assert kwargs["env"]["DATABASE_URL"] == "canonical-local"
            assert kwargs["env"]["PYTHONPATH"] == str(workflow.ROOT / "src")

    monkeypatch.setattr(workflow, "run", run)
    workflow.local_workflow(mode)
    commands = [event for event in events if isinstance(event, list)]
    if mode in {"dev", "init"}:
        assert events[:2] == ["setup", "providers"]
        assert commands[0][-1].endswith("scripts/prepare_local_database.py")
        assert len(commands) == (2 if mode == "dev" else 1)
        if mode == "dev":
            assert commands[1][-1].endswith("src/main.py")
    else:
        assert events[0] == "verify"
        assert "providers" not in events
        assert len(commands) == 1
        assert ("football.import_data" if mode == "seed" else "pytest") in commands[0]


def test_dev_does_not_start_app_when_preparation_fails(monkeypatch):
    import host_development
    import workflow

    commands = []
    monkeypatch.setattr(workflow, "setup", lambda: None)
    monkeypatch.setattr(workflow, "Stack", lambda mode: type("Stack", (), {"settings": {}})())
    monkeypatch.setattr(host_development, "local_providers", lambda stack: None)
    monkeypatch.setattr(workflow.schema, "application", lambda *a, **k: {"HOST_APP_PORT": "5300"})

    def fail(args, **kwargs):
        commands.append(args)
        raise RuntimeError("migration failed")

    monkeypatch.setattr(workflow, "run", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        workflow.local_workflow("dev")
    assert len(commands) == 1
    assert str(commands[0][-1]).endswith("prepare_local_database.py")
