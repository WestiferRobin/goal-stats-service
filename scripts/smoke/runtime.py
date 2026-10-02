"""Own disposable Gunicorn stacks and pytest execution, never HTTP assertions."""

import os
import secrets

from workflow import IMAGE, assert_absent, build_tooling, fresh, inventory, run


def run_smoke(stack, *, fault=False):
    if not stack.disposable or stack.env != "dev":
        raise RuntimeError("Smoke requires an owned disposable DEV Gunicorn stack")
    name = stack.project + "-smoke-" + secrets.token_hex(6)
    values = {
        "SMOKE_PROJECT": stack.project,
        "SMOKE_BASE_URL": "http://app:8000",
        "SMOKE_DATABASE_URL": "postgresql://goalstats:"
        + stack.settings["POSTGRES_PASSWORD"]
        + "@postgres:5432/goal_stats_service_dev",
        "SMOKE_REDIS_URL": "redis://redis:6379/0",
        "SMOKE_CACHE_PREFIX": "goal-stats-service:dev:v1",
        "SMOKE_FAULT": "1" if fault else "0",
    }
    args = [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--label",
        "com.docker.compose.project=" + stack.project,
        "--network",
        stack.project + "_default",
    ]
    for key in values:
        args += ["-e", key]
    args += [
        IMAGE,
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--smoke",
        "tests/smoke",
    ]
    try:
        run(args, env={**os.environ, **values})
    finally:
        run(["docker", "rm", "-f", name], capture=True, check=False)


def smoke(*, fault=False):
    baseline = inventory()
    stack = fresh("dev")
    try:
        build_tooling()
        stack.compose("build", "app")
        stack.migrate()
        stack.start()
        run_smoke(stack, fault=fault)
    finally:
        stack.stop(volumes=True)
        assert_absent(stack.project)
        after = inventory()
        for kind in baseline:
            assert baseline[kind] <= after[kind], f"Unrelated {kind} removed"
    print("Built DEV pytest smoke and cleanup: PASS")
