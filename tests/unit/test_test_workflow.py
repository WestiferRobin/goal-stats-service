"""Execute canonical test dispatch and cleanup against recording Docker commands."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CONFLICT_KEYS = {
    "DATABASE_URL",
    "REDIS_URL",
    "TEST_DATABASE_URL",
    "TEST_REDIS_URL",
    "TEST_SESSION_MANIFEST",
    "APP_ENV",
    "POSTGRES_PASSWORD",
    "TEST_PROJECT",
    "TEST_RUNNER_HOSTNAME",
}

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def test_runner(tmp_path):
    scripts = tmp_path / "scripts/testing"
    scripts.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/testing/test.sh", scripts / "test.sh")
    (scripts / "test_resources.py").write_text("# Docker attestation is separately tested\n")
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(
        "#!"
        + sys.executable
        + """
import json, os, sys, signal, time
with open(os.environ['RECORD'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
args = ' '.join(sys.argv[1:])
if os.environ.get('SIGNAL_NAME') and 'pytest -q' in args:
    os.kill(os.getppid(), getattr(signal, os.environ['SIGNAL_NAME']))
    time.sleep(10)
if os.environ.get('FAIL_STAGE') and os.environ['FAIL_STAGE'] in args:
    sys.exit(7)
"""
    )
    docker.chmod(0o755)

    def run(mode=None, **extra):
        record = tmp_path / "record"
        record.write_text("")
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in CONFLICT_KEYS and not k.startswith("COMPOSE_")
        }
        env.update(
            PATH=str(binary) + os.pathsep + os.environ["PATH"],
            PYTHON=sys.executable,
            RECORD=str(record),
        )
        env.update(extra)
        result = subprocess.run(
            ["bash", "scripts/testing/test.sh", *([mode] if mode else [])],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
        )
        return result, [json.loads(line) for line in record.read_text().splitlines()]

    return run


def test_runner_uses_owned_project_and_cleanup(test_runner):
    result, calls = test_runner()
    assert result.returncode == 0, result.stderr
    compose = [c for c in calls if c[0] == "compose"]
    projects = {c[c.index("-p") + 1] for c in compose}
    assert len(projects) == 1
    assert projects.pop().startswith("goal-stats-service-test-")
    assert all("docker/compose.test.yml" in c for c in compose)
    assert not any("--volumes" in c or "prune" in c for c in calls)
    assert any("down" in c for c in compose)
    runners = [c for c in compose if "run" in c]
    assert all("scripts/testing/test_ownership.py" in c for c in runners)
    assert any("tests/unit" in c and "tests/integration" in c for c in runners)
    assert not any("tests/smoke" in c or "--cov=src" in c for c in calls)


@pytest.mark.parametrize("failure", ["up -d --wait", "alembic upgrade", "pytest -q"])
def test_failure_cleans_only_owned_project(test_runner, failure):
    result, calls = test_runner(FAIL_STAGE=failure)
    assert result.returncode != 0
    assert any("down" in c for c in calls)
    assert not any("--volumes" in c or "prune" in c for c in calls)


@pytest.mark.parametrize(
    "key", ["DATABASE_URL", "TEST_DATABASE_URL", "POSTGRES_PASSWORD", "APP_ENV", "COMPOSE_FILE"]
)
def test_conflicting_targets_fail_before_docker(test_runner, key):
    result, calls = test_runner(**{key: "private-value"})
    assert result.returncode != 0
    assert calls == []
    assert "private-value" not in result.stderr


@pytest.mark.parametrize("name,code", [("SIGINT", 130), ("SIGTERM", 143)])
def test_signals_cleanup_owned_project(test_runner, name, code):
    result, calls = test_runner(SIGNAL_NAME=name)
    assert result.returncode == code
    assert any("down" in c for c in calls)
    assert not any("--volumes" in c or "prune" in c for c in calls)


@pytest.mark.parametrize("mode", ["--smoke", "--coverage", "--certify", "--exercise"])
def test_removed_modes_refused_before_docker(test_runner, mode):
    result, calls = test_runner(mode)
    assert result.returncode == 2
    assert calls == []


def test_exactly_eight_make_targets():
    content = (ROOT / "Makefile").read_text()
    targets = set()
    for line in content.splitlines():
        if line and not line.startswith(("#", "\t", ".")) and ":" in line and ":=" not in line:
            targets.update(line.split(":", 1)[0].split())
    assert targets == {"setup", "infra", "run", "deploy", "seed", "test", "stop", "help"}
