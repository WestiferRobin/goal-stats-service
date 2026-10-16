"""Inspect only an explicitly named disposable TEST project and issue its receipt."""

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

PROJECT = re.compile(r"goal-stats-service-test-[a-f0-9]{24}")
SESSION = re.compile(r"[a-f0-9]{48}")
PASSWORD = re.compile(r"test-[a-f0-9]{48}")
USER = re.compile(r"test_[a-f0-9]{24}")
SESSION_LABEL = "org.goalstats.test-session"
ROOT = Path(__file__).resolve().parents[2]
REDIS_COMMAND = [
    "/bin/sh",
    "-ec",
    'exec redis-server --save "" --appendonly no --requirepass "$REDIS_PASSWORD"',
]


def docker(*args):
    return subprocess.check_output(
        ["docker", *args], text=True, timeout=30, stderr=subprocess.DEVNULL
    ).strip()


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


def private_receipt_path(path, project, *, existing=True):
    """Reject substituted files/directories before reading or issuing credentials."""
    validate_project(project)
    path = Path(path)
    base = ROOT / ".host-sessions"
    directory = path.parent
    if (
        not path.is_absolute()
        or path != path.resolve()
        or directory.parent != base
        or base.is_symlink()
        or not directory.name.startswith(project + ".")
        or path.name != "owned-test.json"
    ):
        raise RuntimeError("Unsafe test receipt path")
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("Unsafe test session directory")
    if existing:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise RuntimeError("Unsafe test receipt file")
    return path


def validate_provider(container, project, service, password, session, user=None):
    validate_project(project)
    target = "/var/lib/postgresql/data" if service == "postgres" else "/data"
    port = "5432/tcp" if service == "postgres" else "6379/tcp"
    try:
        labels = container["Config"]["Labels"]
        mappings = container["NetworkSettings"]["Ports"]
        if (
            service not in {"postgres", "redis"}
            or not SESSION.fullmatch(session)
            or not PASSWORD.fullmatch(password)
            or labels.get("com.docker.compose.project") != project
            or labels.get("com.docker.compose.service") != service
            or labels.get(SESSION_LABEL) != session
            or labels.get("com.docker.compose.oneoff", "False").lower() != "false"
            or not re.fullmatch(r"[a-f0-9]{64}", container["Id"])
            or not container["State"]["Running"]
            or container["State"].get("Health", {}).get("Status") != "healthy"
            or target not in container["HostConfig"].get("Tmpfs", {})
            or any(m["Type"] in {"volume", "bind"} for m in container["Mounts"])
            or set(mappings) != {port}
            or len(mappings[port]) != 1
            or mappings[port][0]["HostIp"] != "127.0.0.1"
            or not str(mappings[port][0]["HostPort"]).isdigit()
            or not 1 <= int(mappings[port][0]["HostPort"]) <= 65535
            or set(container["NetworkSettings"]["Networks"]) != {project + "_default"}
        ):
            raise ValueError
        values = dict(v.split("=", 1) for v in container["Config"]["Env"] if "=" in v)
        if service == "postgres":
            if not USER.fullmatch(user or "") or any(
                values.get(k) != v
                for k, v in {
                    "POSTGRES_USER": user,
                    "POSTGRES_DB": "goalstats_test_runtime",
                    "POSTGRES_PASSWORD": password,
                }.items()
            ):
                raise ValueError
        elif (
            values.get("REDIS_PASSWORD") != password or container["Config"]["Cmd"] != REDIS_COMMAND
        ):
            raise ValueError
        return int(mappings[port][0]["HostPort"])
    except (ValueError, KeyError, TypeError, IndexError):
        raise RuntimeError(
            "Disposable provider ownership/storage/network/credentials mismatch"
        ) from None


def inspect_providers(project, session, user, password, redis_password):
    identities, ports = {}, {}
    for service, secret in (("postgres", password), ("redis", redis_password)):
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
        if container["Id"] != ids[0]:
            raise RuntimeError("Provider identity changed")
        ports[service] = validate_provider(container, project, service, secret, session, user)
        identities[service] = container["Id"]
    network = json.loads(docker("network", "inspect", project + "_default"))[0]
    if (
        network["Labels"].get("com.docker.compose.project") != project
        or network["Labels"].get(SESSION_LABEL) != session
        or set(network.get("Containers", {})) != set(identities.values())
        or ports["postgres"] == ports["redis"]
    ):
        raise RuntimeError("Disposable network membership mismatch")
    return identities, ports, network["Id"]


def issue_receipt(project, session, path):
    validate_project(project)
    user, password, redis_password = (
        os.environ[k] for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "REDIS_PASSWORD")
    )
    identities, ports, network = inspect_providers(project, session, user, password, redis_password)
    path = private_receipt_path(path, project, existing=False)
    receipt = {
        "version": 3,
        "project": project,
        "session": session,
        "directory": str(path.parent),
        "providers": identities,
        "network": network,
        "TEST_DATABASE_URL": f"postgresql+psycopg://{user}:{password}@127.0.0.1:{ports['postgres']}/goalstats_test_runtime",
        "TEST_REDIS_URL": f"redis://:{redis_password}@127.0.0.1:{ports['redis']}/0",
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(receipt, stream)


if __name__ == "__main__":
    try:
        if sys.argv[1] == "receipt":
            issue_receipt(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
        elif sys.argv[1] == "snapshot":
            Path(sys.argv[2]).write_text(json.dumps({k: sorted(v) for k, v in inventory().items()}))
        elif sys.argv[1] == "preserved":
            assert_preserved(json.loads(Path(sys.argv[2]).read_text()))
        elif sys.argv[1] in {"available", "absent"}:
            assert_absent(sys.argv[2])
        else:
            raise RuntimeError("Unknown ownership operation")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError):
        sys.exit("Test resource ownership verification failed; refusing unsafe operation.")
