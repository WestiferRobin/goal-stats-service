"""Certify real disposable LOCAL/DEV stacks and workflow cleanup; never developer volumes."""

import json
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from http_client import request
from smoke.runtime import run_smoke, smoke
from workflow import (
    ROOT,
    Stack,
    assert_absent,
    check,
    fresh,
    install_signals,
    inventory,
    run,
    tests,
    wait_ready,
)


def redis(stack, *args):
    return stack.compose(
        "exec", "-T", "redis", "redis-cli", "--raw", *args, capture=True
    ).stdout.strip()


def sql(stack, query):
    database = "goal_stats_service_" + stack.env
    return stack.compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "goalstats",
        "-d",
        database,
        "-At",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        query,
        capture=True,
    ).stdout.strip()


def runtime_failures(stack):
    # Redis outage: liveness, degradation, read/write fallback, strict startup wait.
    stack.compose("stop", "redis")
    try:
        assert request(stack.url, "/health")[0] == "Healthy"
        assert request(stack.url, "/ready")[0] == "Degraded"
        try:
            wait_ready(stack.url, timeout=1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Degraded incorrectly accepted by startup wait")
        item, _ = request(stack.url, "/items", "POST", {"name": "redis outage"}, 201)
        path = "/items/" + item["id"]
        assert request(stack.url, path)[0] == item
        request(stack.url, path, "PUT", {"name": "fallback", "status": "active"})
        request(stack.url, path, "DELETE", expected=204)
    finally:
        stack.compose("start", "redis")
    wait_ready(stack.url)
    # Bad revision exercises readiness while PostgreSQL remains reachable.
    revision = sql(stack, "SELECT version_num FROM alembic_version")
    sql(stack, "UPDATE alembic_version SET version_num='invalid'")
    try:
        assert request(stack.url, "/ready", expected=503)[0] == "Unhealthy"
    finally:
        sql(stack, f"UPDATE alembic_version SET version_num='{revision}'")
    stack.compose("stop", "postgres")
    try:
        assert request(stack.url, "/health")[0] == "Healthy"
        assert request(stack.url, "/ready", expected=503)[0] == "Unhealthy"
    finally:
        stack.compose("start", "postgres")
    wait_ready(stack.url)
    print(f"{stack.env.upper()} outages and strict readiness: PASS", flush=True)


def signal_cleanup(signum):
    project = "goal-stats-service-test-" + secrets.token_hex(6)
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "signal.log"
        code = (
            "from workflow import install_signals, tests; install_signals(); "
            f"tests('test', fault='signal', project='{project}')"
        )
        with log.open("w") as output:
            child = subprocess.Popen(
                [sys.executable, "-u", "-c", code],
                cwd=ROOT / "scripts",
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 120
                while "SIGNAL_TEST_RUNNING" not in log.read_text():
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError(
                            "Signal test did not reach running stage: " + log.read_text()
                        )
                    time.sleep(0.25)
                # Wait for the actual one-off runner to exist before interrupting the owner.
                while True:
                    output_ids = run(
                        [
                            "docker",
                            "ps",
                            "-q",
                            "--filter",
                            "label=com.docker.compose.project=" + project,
                            "--filter",
                            "label=com.docker.compose.service=runner",
                        ],
                        capture=True,
                    )
                    if output_ids.stdout.strip():
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError("Signal runner never started")
                    time.sleep(0.1)
                child.send_signal(signum)
                assert child.wait(timeout=60) == 128 + signum
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=45)
                # Verify owner's cleanup before any emergency cleanup is attempted.
                try:
                    assert_absent(project)
                finally:
                    Stack("test", project=project, settings={"POSTGRES_PASSWORD": "unused"}).stop(
                        volumes=True
                    )
    print(f"Signal {signum} cleanup: PASS", flush=True)


def certify_configuration(config_dir):
    """No provider namespace exists for this empty temporary config directory."""
    from environment_setup import setup_files

    for _ in range(2):
        before = {p.name: p.read_bytes() for p in config_dir.iterdir()}
        setup_files(config_dir, has_volume=lambda mode: False, verify=lambda mode, values: None)
        if before:
            assert before == {p.name: p.read_bytes() for p in config_dir.iterdir()}


def certify():
    check()
    tests("tooling")
    baseline = inventory()
    print("Docker baseline:", json.dumps({k: len(v) for k, v in baseline.items()}), flush=True)
    stacks = [fresh("local"), fresh("dev")]
    sentinel = "goalstats-workflow-unrelated-" + secrets.token_hex(6)
    try:
        # A deliberately unrelated resource must survive every TEST failure and cleanup.
        run(["docker", "volume", "create", sentinel], capture=True)
        run(["docker", "network", "create", sentinel], capture=True)
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                sentinel,
                "--network",
                sentinel,
                "-v",
                sentinel + ":/data",
                "redis:7.4-alpine",
                "redis-server",
                "--save",
                "",
            ],
            capture=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            certify_configuration(config_dir)
        markers = []
        for stack in stacks:
            stack.compose("build", "app")
            stack.migrate()
            stack.migrate()
            stack.command("alembic", "check")
            stack.command("alembic", "downgrade", "base")
            stack.command("alembic", "upgrade", "head")
            stack.command("alembic", "check")
            stack.start()
            if stack.env == "dev":
                run_smoke(stack)
            runtime_failures(stack)
            uid = stack.compose("exec", "-T", "app", "id", "-u", capture=True).stdout.strip()
            assert uid == "10001"
            if stack.env == "dev":
                result = stack.compose(
                    "exec",
                    "-T",
                    "app",
                    "python",
                    "-c",
                    "from main import create_app; assert not create_app().debug",
                    capture=True,
                )
                assert result.returncode == 0
                container = stack.compose("ps", "-q", "app", capture=True).stdout.strip()
                inspected = json.loads(run(["docker", "inspect", container], capture=True).stdout)[
                    0
                ]
                assert not inspected["Mounts"]
                assert "gunicorn" in inspected["Config"]["Cmd"][0]
                stack.compose("stop", "app")
                state = json.loads(run(["docker", "inspect", container], capture=True).stdout)[0][
                    "State"
                ]
                assert state["ExitCode"] == 0 and not state["OOMKilled"]
                stack.start()
            item, _ = request(
                stack.url, "/items", "POST", {"name": "persistence " + stack.env}, 201
            )
            markers.append(item)
            redis(stack, "SET", "certification-sentinel", stack.project)
            stack.stop()
            stack.start()
            assert request(stack.url, "/items/" + item["id"])[0] == item
            # Redis deliberately has no persistence; recreate a marker for TEST isolation.
            redis(stack, "SET", "certification-sentinel", stack.project)
            stack.compose("logs", "--tail", "5", capture=True)
            print(f"{stack.env.upper()} persistence and runtime ownership: PASS", flush=True)
        tests("coverage")
        for fault in ("unit", "integration", "migration", "provider"):
            project = "goal-stats-service-test-" + secrets.token_hex(6)
            try:
                tests("test", fault=fault, project=project)
            except subprocess.CalledProcessError:
                pass
            else:
                raise AssertionError(f"Expected {fault} failure")
            assert_absent(project)
            print(f"{fault} failure cleanup: PASS", flush=True)
        try:
            smoke(fault=True)
        except subprocess.CalledProcessError as error:
            assert error.returncode == 1, "Expected a real pytest assertion failure"
        else:
            raise AssertionError("Expected smoke failure")
        print("Smoke assertion failure cleanup: PASS", flush=True)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal_cleanup(sig)
        for stack, item in zip(stacks, markers, strict=True):
            assert request(stack.url, "/items/" + item["id"])[0] == item
            assert redis(stack, "GET", "certification-sentinel") == stack.project
        assert (
            run(
                ["docker", "inspect", "-f", "{{.State.Running}}", sentinel], capture=True
            ).stdout.strip()
            == "true"
        )
        run(["docker", "volume", "inspect", sentinel], capture=True)
        run(["docker", "network", "inspect", sentinel], capture=True)
    finally:
        for stack in stacks:
            stack.stop(volumes=True)
            assert_absent(stack.project)
        run(["docker", "rm", "-f", sentinel], capture=True, check=False)
        run(["docker", "volume", "rm", sentinel], capture=True, check=False)
        run(["docker", "network", "rm", sentinel], capture=True, check=False)
    after = inventory()
    for kind in baseline:
        assert baseline[kind] <= after[kind], f"Unrelated {kind} removed"
        if kind != "images":
            assert baseline[kind] == after[kind], f"Leaked {kind}"
    print("Workflow certification: PASS (persistence, isolation, failures, signals, ownership)")


if __name__ == "__main__":
    install_signals()
    certify()
