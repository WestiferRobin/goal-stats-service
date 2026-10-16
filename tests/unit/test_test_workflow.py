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
    "TEST_PINNED_SOURCE",
    "APP_ENV",
    "POSTGRES_PASSWORD",
    "TEST_PROJECT",
    "TEST_RUNNER_HOSTNAME",
    "TEST_TOOLING_IMAGE",
    "TEST_SESSION",
    "POSTGRES_USER",
    "REDIS_PASSWORD",
    "TEST_DATABASE_DISPOSABLE",
    "TEST_REDIS_DISPOSABLE",
}

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def test_runner(tmp_path):
    scripts = tmp_path / "scripts/testing"
    scripts.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/testing/test.sh", scripts / "test.sh")
    shutil.copy(ROOT / "Makefile", tmp_path / "Makefile")
    (scripts / "test_resources.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "if sys.argv[1] == 'snapshot': Path(sys.argv[2]).write_text('{}')\n"
        "if os.environ.get('FAIL_RESOURCE') == sys.argv[1]: sys.exit(9)\n"
    )
    (scripts / "test_ownership.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts/testing')!r})\n"
        "from test_ownership import supervise\n"
        "if sys.argv[1] == 'owned':\n"
        "    counter = Path('receipts')\n"
        "    count = int(counter.read_text()) + 1 if counter.exists() else 1\n"
        "    counter.write_text(str(count))\n"
        "    if count == 2 and os.environ.get('FAIL_SUITE_RECEIPT'): sys.exit(9)\n"
        "sys.exit(supervise(sys.argv[2:]))\n"
    )
    (scripts / "pinned_source.py").write_text(
        "import json, os, sys\nfrom pathlib import Path\n"
        "with open(os.environ['RECORD'], 'a') as stream:\n"
        "    stream.write(json.dumps(['source', sys.argv[1]]) + '\\n')\n"
        "if os.environ.get('FAIL_SOURCE') == sys.argv[1]: sys.exit(8)\n"
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    venv = tmp_path / ".venv/bin"
    venv.mkdir(parents=True)
    recorder = (
        "#!"
        + sys.executable
        + "\n"
        + r"""
import json, os, sys, signal, time
from pathlib import Path
args = sys.argv[1:]
if os.environ.get('ENV_RECORD'):
    with open(os.environ['ENV_RECORD'], 'a') as stream:
        stream.write(json.dumps({'executable': sys.argv[0], 'args': args,
                                 'env': dict(os.environ)}) + '\n')
if Path(sys.argv[0]).name == 'python':
    if 'scripts/development/python_environment.py' in args:
        sys.exit(2 if os.environ.get('INVALID_VENV') else 0)
    if '-c' in args or any(
        'scripts/testing/test_' in a or 'scripts/testing/pinned_source.py' in a for a in args
    ):
        os.execv(sys.executable, [sys.executable, *args])
with open(os.environ['RECORD'], 'a') as stream:
    stream.write(json.dumps(args) + '\n')
joined = ' '.join(args)
if os.environ.get('SIGNAL_NAME') and 'pytest -q' in joined:
    # Interrupt the shell while this process and its supervisor are alive.
    os.kill(int(os.environ['RUNNER_SHELL_PID']), getattr(signal, os.environ['SIGNAL_NAME']))
    time.sleep(10)
if '--rcfile=.coveragerc' in args:
    report_dir = Path(os.environ['COVERAGE_FILE']).parent
    (report_dir / '.coverage').write_text('owned raw data')
    (report_dir / '.coverage.unrelated').write_text('keep this diagnostic')
if 'scripts/testing/coverage_report.py' in args:
    if os.environ.get('FAIL_REPORT_GENERATION'): sys.exit(7)
    report_dir = Path(args[-1])
    if not os.environ.get('MISSING_REPORT'):
        (report_dir / 'coverage.json').write_text('{"recorded": true}')
        (report_dir / 'coverage.xml').write_text('<coverage/>')
    sys.exit(int(os.environ.get('REPORT_STATUS', '0')))
if os.environ.get('FAIL_STAGE') and os.environ['FAIL_STAGE'] in joined:
    sys.exit(7)
"""
    )
    for executable in (binary / "docker", venv / "python", venv / "ruff"):
        executable.write_text(recorder)
        executable.chmod(0o755)
    remover = binary / "rm"
    remover.write_text(
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "with open(os.environ['RECORD'], 'a') as stream:\n"
        "    stream.write(json.dumps(['rm', *sys.argv[1:]]) + '\\n')\n"
        "if os.environ.get('FAIL_RAW_CLEANUP') and sys.argv[-1].endswith('/.coverage'):\n"
        "    sys.exit(13)\n"
        "os.execv('/bin/rm', ['/bin/rm', *sys.argv[1:]])\n"
    )
    remover.chmod(0o755)

    def run(mode=None, *arguments, **extra):
        record = tmp_path / "record"
        record.write_text("")
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in CONFLICT_KEYS and not k.startswith(("COMPOSE_", "COVERAGE_", "PYTEST_"))
        }
        env.update(PATH=str(binary) + os.pathsep + os.environ["PATH"], RECORD=str(record))
        if extra.pop("REMOVE_VENV", False):
            (venv / "python").unlink()
        via_make = extra.pop("VIA_MAKE", False)
        env.update(extra)
        if env.get("VIRTUAL_ENV"):
            env["PATH"] = str(Path(env["VIRTUAL_ENV"]) / "bin") + os.pathsep + env["PATH"]
        result = subprocess.run(
            [
                "bash",
                "-c",
                'export RUNNER_SHELL_PID=$$; exec bash scripts/testing/test.sh "$@"',
                "test-runner",
                *([mode] if mode else []),
                *arguments,
            ]
            if not via_make
            else ["make", mode or "test"],
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
    assert not any("run" in c or "build" in c for c in compose)
    runners = [c for c in calls if "pytest" in c]
    assert len(runners) == 1
    assert any("tests/unit" in c and "tests/integration" in c for c in runners)
    assert not any("--cov=src" in c for c in calls)


@pytest.mark.parametrize("failure", ["up -d --wait", "alembic upgrade", "pytest -q"])
def test_failure_cleans_only_owned_project(test_runner, failure):
    result, calls = test_runner(FAIL_STAGE=failure)
    assert result.returncode != 0
    assert any("down" in c for c in calls)
    assert not any("--volumes" in c or "prune" in c for c in calls)


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "TEST_DATABASE_URL",
        "REDIS_URL",
        "TEST_REDIS_URL",
        "TEST_SESSION_MANIFEST",
        "POSTGRES_PASSWORD",
        "APP_ENV",
        "COMPOSE_FILE",
    ],
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


@pytest.mark.parametrize("mode", ["--unknown", "--coverage", "--certify", "--exercise"])
def test_removed_modes_refused_before_docker(test_runner, mode):
    result, calls = test_runner(mode)
    assert result.returncode == 2
    assert calls == []


def test_exactly_nine_make_targets():
    content = (ROOT / "Makefile").read_text()
    targets = set()
    for line in content.splitlines():
        if line and not line.startswith(("#", "\t", ".")) and ":" in line and ":=" not in line:
            targets.update(line.split(":", 1)[0].split())
    assert targets == {"setup", "infra", "run", "deploy", "seed", "test", "certify", "stop", "help"}


@pytest.mark.parametrize("arguments", [("unknown",), ("certify", "extra"), ("test",)])
def test_invalid_invocation_has_no_docker_effects(test_runner, arguments):
    result, calls = test_runner(*arguments)
    assert result.returncode == 2
    assert calls == []


@pytest.mark.parametrize("report_status", ["0", "2"])
def test_certification_reports_survive_cleanup(test_runner, report_status):
    result, calls = test_runner("certify", REPORT_STATUS=report_status)
    assert result.returncode == int(report_status), result.stderr
    full = next(i for i, c in enumerate(calls) if "--rcfile=.coveragerc" in c)
    report = next(i for i, c in enumerate(calls) if "scripts/testing/coverage_report.py" in c)
    assert full < report
    assert sum("pytest" in c for c in calls) == 1
    assert "tests/unit" in calls[full] and "tests/integration" in calls[full]
    assert "not pinned_source" not in calls[full]
    directory = Path(calls[report][-1])
    assert (directory / "coverage.json").is_file()
    assert (directory / "coverage.xml").is_file()
    assert not (directory / ".coverage").exists()
    removed = next(i for i, c in enumerate(calls) if c[0] == "rm" and c[-1].endswith("/.coverage"))
    assert removed < next(i for i, c in enumerate(calls) if "down" in c)
    assert (directory / ".coverage.unrelated").read_text() == "keep this diagnostic"
    assert any("down" in c for c in calls)
    assert not any("--volumes" in c or "prune" in c for c in calls)
    assert ("Certification: PASS" in result.stdout) == (report_status == "0")
    if report_status == "2":
        assert "Tests passed; coverage gate or reporting failed" in result.stderr


@pytest.mark.parametrize("stage", ["alembic upgrade", "--rcfile=.coveragerc"])
def test_certification_test_failures_never_pass(test_runner, stage):
    result, calls = test_runner("certify", FAIL_STAGE=stage)
    assert result.returncode != 0
    assert "Certification: PASS" not in result.stdout
    assert any("down" in c for c in calls)
    if stage.startswith("alembic"):
        assert not any("--rcfile=.coveragerc" in c for c in calls)
    else:
        assert "Unit/Integration execution failed" in result.stderr


@pytest.mark.parametrize(
    "extra", [{"MISSING_REPORT": "1"}, {"FAIL_STAGE": "down --remove-orphans"}]
)
def test_certification_requires_reports_and_successful_cleanup(test_runner, extra):
    result, calls = test_runner("certify", **extra)
    assert result.returncode != 0
    assert "Certification: PASS" not in result.stdout
    assert any("down" in c for c in calls)


def test_missing_coverage_dependency_stops_before_providers(test_runner):
    result, calls = test_runner("certify", INVALID_VENV="1")
    assert result.returncode != 0
    assert not any("up" in c for c in calls)
    assert "Certification: PASS" not in result.stdout


def test_suite_ownership_failure_never_executes_unverified_command(test_runner):
    result, calls = test_runner("certify", FAIL_SUITE_RECEIPT="1")
    assert result.returncode != 0
    assert not any("pytest" in c for c in calls)
    assert not any("--rcfile=.coveragerc" in c for c in calls)
    assert any("down" in c for c in calls)
    assert "Certification: PASS" not in result.stdout


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({"FAIL_REPORT_GENERATION": "1"}, 7),
        ({"MISSING_REPORT": "1"}, 1),
        ({"FAIL_RAW_CLEANUP": "1"}, 1),
        ({"FAIL_RAW_CLEANUP": "1", "REPORT_STATUS": "2"}, 2),
    ],
)
def test_raw_cleanup_failure_paths_preserve_reports_and_resource_cleanup(
    test_runner, extra, expected
):
    result, calls = test_runner("certify", **extra)
    assert result.returncode == expected
    assert "Certification: PASS" not in result.stdout
    assert any("down" in c for c in calls)
    report = next(c for c in calls if "scripts/testing/coverage_report.py" in c)
    directory = Path(report[-1])
    assert (directory / ".coverage.unrelated").read_text() == "keep this diagnostic"
    assert (directory / ".coverage").exists() == bool(extra.get("FAIL_RAW_CLEANUP"))
    if extra.get("FAIL_RAW_CLEANUP"):
        assert "raw coverage cleanup failed" in result.stderr
        assert (directory / "coverage.json").is_file()
        assert (directory / "coverage.xml").is_file()


@pytest.mark.parametrize(
    "failure", ["check --no-cache", "format --check", "mypy --config-file", "info"]
)
def test_prerequisite_failures_never_start_providers(test_runner, failure):
    result, calls = test_runner(FAIL_STAGE=failure)
    assert result.returncode != 0
    assert not any("up" in c for c in calls)


@pytest.mark.parametrize(
    "key",
    [
        "REDIS_PASSWORD",
        "POSTGRES_USER",
        "TEST_SESSION",
        "PYTEST_ADDOPTS",
        "COVERAGE_FILE",
        "COVERAGE_PROCESS_START",
    ],
)
def test_host_configuration_overrides_fail_closed(test_runner, key):
    result, calls = test_runner(**{key: "secret-override"})
    assert result.returncode == 2
    assert calls == []
    assert "secret-override" not in result.stderr


def test_cleanup_failure_preserves_original_exit(test_runner):
    result, calls = test_runner("certify", REPORT_STATUS="2", FAIL_STAGE="down --remove-orphans")
    assert result.returncode == 2
    assert "Cleanup failed" in result.stderr
    assert "Certification: PASS" not in result.stdout
    assert any("down" in c for c in calls)


@pytest.mark.parametrize("operation", ["receipt", "absent", "preserved"])
def test_resource_verification_failure_never_passes(test_runner, operation):
    result, calls = test_runner("certify", FAIL_RESOURCE=operation)
    assert result.returncode != 0
    assert "Certification: PASS" not in result.stdout
    assert any("down" in c for c in calls)
    if operation == "receipt":
        assert not any("alembic" in c or "pytest" in c for c in calls)


def test_missing_venv_never_falls_back_to_system_python(test_runner):
    result, calls = test_runner(REMOVE_VENV=True, PYTHON=sys.executable)
    assert result.returncode == 2
    assert "make setup" in result.stderr
    assert calls == []


def test_inherited_python_does_not_select_test_interpreter(test_runner):
    result, calls = test_runner(PYTHON="/nonexistent/system-python")
    assert result.returncode == 0, result.stderr
    assert sum("pytest" in c for c in calls) == 1


@pytest.mark.parametrize("mode", ["test", "certify"])
@pytest.mark.parametrize("startup", ["", "missing", "sentinel"])
def test_make_sanitizes_startup_without_changing_parent(
    test_runner, tmp_path, monkeypatch, mode, startup
):
    marker = tmp_path / "startup-executed"
    source = tmp_path / "startup.py"
    source.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    value = str(source) if startup == "sentinel" else startup
    monkeypatch.setenv("PYTHONSTARTUP", value)
    result, calls = test_runner(mode, VIA_MAKE=True)
    assert result.returncode == 0, result.stderr
    assert os.environ["PYTHONSTARTUP"] == value
    assert not marker.exists()
    suites = [c for c in calls if "pytest" in c]
    assert len(suites) == 1
    assert suites[0][-2:] == ["tests/unit", "tests/integration"]
    assert ("not pinned_source" in suites[0]) == (mode == "test")
    assert not any("smoke" in arg.lower() for c in calls for arg in c)
    assert any("down" in c for c in calls)


@pytest.mark.parametrize("mode", ["test", "certify"])
@pytest.mark.parametrize("activation", ["none", "repository", "unrelated"])
def test_python_environment_normalized_before_verifier_and_for_children(
    test_runner, tmp_path, mode, activation
):
    keys = (
        "PYTHONSTARTUP",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "PYTHONINSPECT",
        "PYTHONOPTIMIZE",
        "PYTHONBREAKPOINT",
        "PYTHONWARNINGS",
        "PYTHONPYCACHEPREFIX",
        "PYTHONSAFEPATH",
    )
    poison = tmp_path / "untrusted"
    poison.mkdir()
    (poison / "sitecustomize.py").write_text(
        "raise RuntimeError('untrusted import path executed')\n"
    )
    record = tmp_path / "environments.jsonl"
    extra = {key: str(poison) for key in keys}
    extra.update(
        ENV_RECORD=str(record),
        PYTHONNOUSERSITE="0",
        PYTHONDONTWRITEBYTECODE="0",
        PYTHON="/nonexistent/python",
        HOST_ENV_SENTINEL="preserved",
    )
    if activation != "none":
        extra["VIRTUAL_ENV"] = str(
            tmp_path / (".venv" if activation == "repository" else "other-venv")
        )
    else:
        extra["VIRTUAL_ENV"] = ""
    result, calls = test_runner(mode, VIA_MAKE=True, **extra)
    assert result.returncode == 0, result.stderr
    entries = [json.loads(line) for line in record.read_text().splitlines()]
    first = entries[0]
    assert "scripts/development/python_environment.py" in first["args"]
    assert first["executable"] == str(tmp_path / ".venv/bin/python")
    assert all(key not in first["env"] for key in keys)
    expected_path = ":".join(
        str(tmp_path / p)
        for p in ("src", "scripts/development", "scripts/database", "scripts/testing")
    )
    for entry in entries:
        env = entry["env"]
        assert env["PYTHONNOUSERSITE"] == env["PYTHONDONTWRITEBYTECODE"] == "1"
        assert env["HOST_ENV_SENTINEL"] == "preserved"
        assert all(key not in env for key in keys if key != "PYTHONPATH")
        if entry is not first:
            assert env["PYTHONPATH"] == expected_path
    assert sum("pytest" in c for c in calls) == 1


@pytest.mark.parametrize("mode", ["test", "certify"])
def test_incompatible_venv_with_startup_still_fails_before_docker(test_runner, mode):
    result, calls = test_runner(mode, VIA_MAKE=True, PYTHONSTARTUP="", INVALID_VENV="1")
    assert result.returncode == 2
    assert "make setup" in result.stderr
    assert calls == []


@pytest.mark.parametrize("operation", ["prepare", "cleanup"])
def test_source_lifecycle_failure_never_passes(test_runner, operation):
    result, calls = test_runner("certify", FAIL_SOURCE=operation)
    assert result.returncode == 8 if operation == "prepare" else result.returncode == 1
    assert "Certification: PASS" not in result.stdout
    assert ["source", "cleanup"] in calls
    if operation == "prepare":
        assert not any("pytest" in c or "up" in c for c in calls)
    else:
        assert any("down" in c for c in calls)
        assert not any(c[0] == "rm" and "-rf" in c for c in calls)


@pytest.mark.parametrize("signal,code", [("SIGINT", 130), ("SIGTERM", 143)])
def test_interrupted_certification_detaches_source_and_preserves_failure(test_runner, signal, code):
    result, calls = test_runner("certify", SIGNAL_NAME=signal)
    assert result.returncode == code
    assert ["source", "prepare"] in calls and ["source", "cleanup"] in calls
    assert any("down" in c for c in calls)
    assert "Certification: PASS" not in result.stdout


def test_source_cleanup_preserves_test_failure_code(test_runner):
    result, calls = test_runner("certify", FAIL_STAGE="pytest -q", FAIL_SOURCE="cleanup")
    assert result.returncode == 7
    assert ["source", "cleanup"] in calls
    assert any("down" in c for c in calls)


def test_no_global_pinned_source_deselection():
    config = (ROOT / "pytest.ini").read_text()
    assert "not pinned_source" not in config


def test_source_path_override_is_rejected(test_runner):
    result, calls = test_runner("certify", TEST_PINNED_SOURCE="/unowned/source.csv")
    assert result.returncode == 2 and not calls


def test_source_lifecycle_runs_only_for_certification(test_runner):
    ordinary, calls = test_runner()
    assert ordinary.returncode == 0
    assert not any(c[0] == "source" for c in calls)
    certified, calls = test_runner("certify")
    assert certified.returncode == 0
    start = calls.index(["source", "prepare"])
    suite = next(i for i, c in enumerate(calls) if "pytest" in c)
    end = calls.index(["source", "cleanup"])
    assert start < suite < end
