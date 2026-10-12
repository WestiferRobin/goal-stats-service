"""Inspect only an explicitly named disposable TEST project and issue its receipt."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT = re.compile(r"goal-stats-service-test-[a-f0-9]{24}")


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, timeout=30).strip()


def validate_project(project):
    if not PROJECT.fullmatch(project):
        raise RuntimeError("Refusing a non-disposable test project")


def resource_ids(project, kind):
    validate_project(project)
    label = "label=com.docker.compose.project=" + project
    args = ["ps", "-aq", "--no-trunc"] if kind == "containers" else [kind, "ls", "-q"]
    return docker(*args, "--filter", label).split()


def inventory():
    return {
        "containers": set(docker("ps", "-aq", "--no-trunc").split()),
        "running": set(docker("ps", "-q", "--no-trunc").split()),
        "networks": set(docker("network", "ls", "-q", "--no-trunc").split()),
        "volumes": set(docker("volume", "ls", "-q").split()),
    }


def assert_preserved(before):
    after = inventory()
    for kind, identities in before.items():
        if not set(identities) <= after[kind]:
            raise RuntimeError(f"Unrelated {kind} changed during certification")


def assert_absent(project):
    for kind in ("containers", "network", "volume"):
        if resource_ids(project, kind):
            raise RuntimeError(f"Owned test {kind} leaked: {project}")


def validate_provider(container, project, service, password):
    validate_project(project)
    labels = container["Config"]["Labels"]
    target = "/var/lib/postgresql/data" if service == "postgres" else "/data"
    if (
        labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.service") != service
        or labels.get("com.docker.compose.oneoff", "False").lower() != "false"
        or not re.fullmatch(r"[a-f0-9]{64}", container["Id"])
        or not container["State"]["Running"]
        or container["State"].get("Health", {}).get("Status") != "healthy"
        or target not in container["HostConfig"].get("Tmpfs", {})
        or any(m["Type"] in {"volume", "bind"} for m in container["Mounts"])
        or any(container["NetworkSettings"]["Ports"].values())
        or set(container["NetworkSettings"]["Networks"]) != {project + "_default"}
    ):
        raise RuntimeError("Disposable provider ownership/storage/network mismatch")
    if service == "postgres":
        values = dict(v.split("=", 1) for v in container["Config"]["Env"] if "=" in v)
        if any(
            values.get(k) != v
            for k, v in {
                "POSTGRES_USER": "goalstats",
                "POSTGRES_DB": "goalstats_test_runtime",
                "POSTGRES_PASSWORD": password,
            }.items()
        ):
            raise RuntimeError("Disposable PostgreSQL identity mismatch")
    elif container["Config"]["Cmd"] != ["redis-server", "--save", "", "--appendonly", "no"]:
        raise RuntimeError("Unexpected disposable Redis configuration")


def issue_receipt(project, runner, path):
    validate_project(project)
    if runner != project + "-runner":
        raise RuntimeError("Unexpected test runner identity")
    password = os.environ["POSTGRES_PASSWORD"]
    if not re.fullmatch(r"test-[a-f0-9]{48}", password):
        raise RuntimeError("Generated test credentials required")
    identities = {}
    for service in ("postgres", "redis"):
        ids = docker(
            "ps",
            "-aq",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=" + project,
            "--filter",
            "label=com.docker.compose.service=" + service,
        ).split()
        if len(ids) != 1:
            raise RuntimeError("Expected exactly one owned provider")
        container = json.loads(docker("inspect", ids[0]))[0]
        validate_provider(container, project, service, password)
        identities[service] = container["Id"]
    receipt = {
        "version": 2,
        "project": project,
        "hostname": runner,
        "providers": identities,
        "TEST_DATABASE_URL": f"postgresql+psycopg://goalstats:{password}@postgres:5432/goalstats_test_runtime",
        "TEST_REDIS_URL": "redis://redis:6379/0",
    }
    if path.exists():
        path.chmod(0o600)
    path.write_text(json.dumps(receipt))
    path.chmod(0o444)


if __name__ == "__main__":
    try:
        if sys.argv[1] == "receipt":
            issue_receipt(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
        elif sys.argv[1] == "snapshot":
            Path(sys.argv[2]).write_text(json.dumps({k: sorted(v) for k, v in inventory().items()}))
        elif sys.argv[1] == "preserved":
            assert_preserved(json.loads(Path(sys.argv[2]).read_text()))
        elif sys.argv[1] == "absent":
            assert_absent(sys.argv[2])
        else:
            raise RuntimeError("Unknown ownership operation")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        sys.exit("Test resource ownership verification failed; refusing unsafe operation.")
