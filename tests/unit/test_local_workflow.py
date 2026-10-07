"""Run the real public shell against recording executables, never real providers."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workflow(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/local.sh", tmp_path / "scripts/local.sh")
    shutil.copy(ROOT / "Makefile", tmp_path / "Makefile")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.example")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.local")
    (tmp_path / ".venv/bin").mkdir(parents=True)
    binary = tmp_path / "bin"
    binary.mkdir()
    # These stubs only record invocations; the lifecycle under test is unmodified.
    stub = (
        "#!"
        + sys.executable
        + """
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['RECORD'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if os.environ.get('FAIL') and os.environ['FAIL'] in ' '.join(args):
    sys.exit(7)
if name == 'make':
    print('GNU Make 4.0')
    if os.environ.get('LARGE_MAKE_VERSION'): print('version details' * 20000)
if args == ['scripts/python_environment.py', 'config']: print('5100')
if 'ps' in args and os.environ.get('APP_RUNNING'): print('owned-app')
if 'port' in args and name == 'docker': print('127.0.0.1:5100')
"""
    )
    for path in [
        binary / "docker",
        binary / "make",
        binary / "python3.12",
        tmp_path / ".venv/bin/python",
    ]:
        path.write_text(stub)
        path.chmod(0o755)

    def execute(action, **extra):
        record = tmp_path / "record"
        record.write_text("")
        env = {
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "PYTHON": "python3.12",
            "RECORD": str(record),
            **extra,
        }
        result = subprocess.run(
            ["bash", "scripts/local.sh", action],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
        )
        calls = [json.loads(line) for line in record.read_text().splitlines()]
        return result, calls

    return execute, tmp_path


def commands(calls):
    return [" ".join(call) for call in calls]


def test_help_has_exact_public_contract(workflow):
    run, _ = workflow
    result, calls = run("help")
    assert result.returncode == 0
    for name in ("setup", "infra", "run", "deploy", "test", "stop", "help"):
        assert "make " + name in result.stdout
    assert "No cloud deployment" in result.stdout
    assert calls == []
    assert "make providers" not in result.stdout


def test_setup_preserves_file_and_starts_nothing(workflow):
    run, root = workflow
    before = (root / ".env.local").read_bytes()
    result, calls = run("setup")
    assert result.returncode == 0, result.stderr
    assert (root / ".env.local").read_bytes() == before
    events = commands(calls)
    assert "python3.12 scripts/python_environment.py bootstrap" in events
    assert any("build --target tooling" in call for call in events)
    assert not any(" up " in call or " run " in call or " stop " in call for call in events)


def test_setup_creates_missing_file(workflow):
    run, root = workflow
    (root / ".env.local").unlink()
    result, _ = run("setup")
    assert result.returncode == 0
    assert (root / ".env.local").read_bytes() == (root / ".env.example").read_bytes()
    assert (root / ".env.local").stat().st_mode & 0o777 == 0o600


def test_infra_stops_only_owned_app_and_starts_only_providers(workflow):
    run, _ = workflow
    result, calls = run("infra")
    assert result.returncode == 0
    docker = [c for c in calls if c[0] == "docker" and c[1:3] == ["compose", "--env-file"]]
    assert all(
        c[2:8]
        == [
            "--env-file",
            ".env.local",
            "-p",
            "goalstats-service-local",
            "-f",
            "docker/compose.local.yml",
        ]
        for c in docker
    )
    assert [c[8:] for c in docker] == [
        ["config", "--quiet"],
        ["stop", "app"],
        ["up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis"],
    ]


@pytest.mark.parametrize("action", ["run", "deploy"])
def test_preparation_precedes_flask(workflow, action):
    run, _ = workflow
    result, calls = run(action)
    assert result.returncode == 0, result.stderr
    events = commands(calls)
    migration = next(i for i, c in enumerate(events) if c.endswith("alembic upgrade head"))
    importer = next(i for i, c in enumerate(events) if c.endswith("import-football"))
    providers = next(i for i, c in enumerate(events) if c.endswith("90 postgres redis"))
    assert providers < migration < importer < len(events) - 1
    if action == "run":
        assert calls[-1] == ["python", "src/main.py"]
        assert events.index("python3.12 scripts/python_environment.py verify") < next(
            i for i, c in enumerate(events) if c.endswith("stop app")
        )
    else:
        assert events[-1].endswith("up -d --wait --wait-timeout 90 app")
        assert not any(c.endswith("stop app") for c in events)


def test_repeated_deploy_allows_owned_listener(workflow):
    run, _ = workflow
    result, calls = run("deploy", APP_RUNNING="1")
    assert result.returncode == 0
    assert ["python3.12", "scripts/python_environment.py", "port"] not in calls


@pytest.mark.parametrize("action", ["run", "deploy", "infra"])
def test_port_failure_prevents_build_and_start(workflow, action):
    run, _ = workflow
    result, calls = run(action, FAIL="python_environment.py port")
    assert result.returncode != 0
    assert not any(" up " in c or " build " in c for c in commands(calls))


@pytest.mark.parametrize(
    "failure",
    [
        "python_environment.py config",
        "python_environment.py verify",
        "alembic upgrade head",
        "import-football",
    ],
)
def test_run_failure_never_launches_host(workflow, failure):
    run, _ = workflow
    result, calls = run("run", FAIL=failure)
    assert result.returncode != 0
    assert ["python", "src/main.py"] not in calls
    if "python_environment.py" in failure:
        assert not any(c.endswith("stop app") for c in commands(calls))
    if "alembic" in failure:
        assert not any(c.endswith("import-football") for c in commands(calls))


def test_stop_preserves_volume_and_does_not_kill_host(workflow):
    run, _ = workflow
    result, calls = run("stop")
    assert result.returncode == 0
    assert "Ctrl-C or IDE Stop" in result.stdout
    assert commands(calls)[-1].endswith("down --remove-orphans")
    assert not any("--volumes" in c or "kill" in c for c in commands(calls))


def test_make_dispatch_keeps_test_independent():
    content = (ROOT / "Makefile").read_text()
    assert "setup infra run deploy stop:" in content
    assert "scripts/local.sh $@" in content
    assert "test:\n\t@$(BASH) scripts/test.sh" in content
    assert "help:\n\t@$(BASH) scripts/local.sh help" in content
    assert ".PHONY: setup infra run deploy test stop help" in content


def test_gnu_make_version_check_does_not_close_pipe_early(workflow):
    run, _ = workflow
    result, _ = run("infra", LARGE_MAKE_VERSION="1")
    assert result.returncode == 0, result.stderr
