"""Additive host development orchestration. No implicit application dotenv loading."""

import fcntl
import json
import os
import secrets
import socket
import time

from environment_config import schema
from test_ownership import SESSION_LABEL, inspect_container, verify_host_session
from workflow import ROOT, Stack, assert_absent


def private_write(path, content):
    """Create only: existing files and symlinks are never overwritten."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def env_text(values):
    return "".join(f"{key}={value}\n" for key, value in values.items())


def provider_identity(stack, service):
    ids = stack.compose("ps", "-a", "-q", service, capture=True).stdout.split()
    if not ids:
        return None
    if len(ids) != 1:
        raise RuntimeError("Expected exactly one provider container")
    container = inspect_container(ids[0])
    labels = container["Config"]["Labels"]
    if (
        labels.get("com.docker.compose.project") != stack.project
        or labels.get("com.docker.compose.service") != service
    ):
        raise RuntimeError("Provider container identity mismatch")
    return container


def refuse_active_app(stack):
    if stack.compose("ps", "--status", "running", "-q", "app", capture=True).stdout.strip():
        raise RuntimeError("Full LOCAL app is active; stop it before changing host providers")


def local_environment(stack):
    return schema.application({**schema.PORT_DEFAULTS, **stack.settings}, "local", host=True)


def check_local_bindings(stack, *, before=False):
    for service, key, default, internal in (
        ("postgres", "LOCAL_POSTGRES_PORT", "55432", "5432/tcp"),
        ("redis", "LOCAL_REDIS_PORT", "56379", "6379/tcp"),
    ):
        port = stack.settings.get(key, default)
        container = provider_identity(stack, service)
        if container:
            if service == "postgres":
                config = dict(v.split("=", 1) for v in container["Config"]["Env"] if "=" in v)
                if (
                    config.get("POSTGRES_PASSWORD") != stack.settings["POSTGRES_PASSWORD"]
                    or config.get("POSTGRES_DB") != "goal_stats_service_local"
                    or config.get("POSTGRES_USER") != "goalstats"
                ):
                    raise RuntimeError(
                        "LOCAL PostgreSQL identity/configuration mismatch; configuration changes "
                        "do not rotate existing volume credentials"
                    )
            bindings = container["HostConfig"].get("PortBindings", {}).get(internal)
            expected = [{"HostIp": "127.0.0.1", "HostPort": port}]
            if bindings and bindings != expected:
                raise RuntimeError(
                    "Stale LOCAL provider ports; stop the full stack before changing ports"
                )
            if container["State"]["Running"] and bindings == expected:
                continue
        if before:
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", int(port)))
                except OSError:
                    raise RuntimeError(
                        f"LOCAL {service} loopback port {port} is occupied"
                    ) from None
        else:
            raise RuntimeError("LOCAL provider binding verification failed")


def local_providers(stack, *, stop=False):
    if stack.env != "local":
        raise RuntimeError("Host providers require LOCAL")
    refuse_active_app(stack)
    if stop:
        stack.compose("stop", "postgres", "redis")
        return
    ports = [
        stack.settings.get(key, default)
        for key, default in (
            ("HOST_APP_PORT", "5300"),
            ("LOCAL_POSTGRES_PORT", "55432"),
            ("LOCAL_REDIS_PORT", "56379"),
        )
    ]
    if len(set(map(int, ports))) != len(ports):
        raise RuntimeError("Host app and provider ports must be distinct")
    check_local_bindings(stack, before=True)
    stack.providers()
    check_local_bindings(stack)
    # Use the container's network address, not localhost (initdb may trust loopback).
    # This proves the password matches credentials already stored in the volume.
    result = stack.compose(
        "exec",
        "-T",
        "-e",
        "PGPASSWORD=" + stack.settings["POSTGRES_PASSWORD"],
        "postgres",
        "psql",
        "-h",
        "postgres",
        "-U",
        "goalstats",
        "-d",
        "goal_stats_service_local",
        "-At",
        "-c",
        "SELECT 1",
        capture=True,
        check=False,
    )
    if result.returncode or result.stdout.strip() != "1":
        raise RuntimeError(
            "LOCAL database authentication failed. Configuration does not rotate existing "
            "volume credentials; restore the correct password before starting providers."
        )
    print("LOCAL providers healthy; canonical configuration ready. No app or migration started.")
    print(
        "Existing PostgreSQL volume credentials are unchanged; readiness verifies authentication."
    )


def test_providers():
    """Foreground ownership lease; crashes leave durable evidence but cannot authorize tests."""
    project = "goal-stats-service-test-" + secrets.token_hex(12)
    token = secrets.token_hex(24)
    stack = Stack("test", project=project, settings={"POSTGRES_PASSWORD": secrets.token_hex(24)})
    root = ROOT / ".host-sessions"
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise RuntimeError("Host session directory must be private and owned by this user")
    directory = root / project
    directory.mkdir(mode=0o700)
    lock = directory / "owner.lock"
    private_write(lock, "")
    with lock.open() as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        redis_password = secrets.token_hex(24)
        override = directory / "compose.json"
        private_write(
            override,
            json.dumps(
                {
                    "services": {
                        "postgres": {
                            "ports": ["127.0.0.1::5432"],
                            "labels": {SESSION_LABEL: token},
                        },
                        "redis": {
                            "ports": ["127.0.0.1::6379"],
                            "labels": {SESSION_LABEL: token},
                            "command": [
                                "redis-server",
                                "--save",
                                "",
                                "--appendonly",
                                "no",
                                "--requirepass",
                                redis_password,
                            ],
                            "healthcheck": {
                                "test": ["CMD", "redis-cli", "-a", redis_password, "ping"]
                            },
                        },
                    }
                }
            ),
        )
        stack.args += ["-f", override]
        manifest_path = directory / "manifest.json"
        # Starting evidence survives a provider failure or an uncatchable owner crash.
        evidence = directory / "ownership.json"
        private_write(
            evidence, json.dumps({"project": project, "token": token, "pid": os.getpid()})
        )
        try:
            stack.providers()
            containers = {s: provider_identity(stack, s) for s in ("postgres", "redis")}
            ports = {
                s: containers[s]["NetworkSettings"]["Ports"][p][0]["HostPort"]
                for s, p in (("postgres", "5432/tcp"), ("redis", "6379/tcp"))
            }
            urls = {
                "TEST_DATABASE_URL": "postgresql+psycopg://goalstats:"
                + stack.settings["POSTGRES_PASSWORD"]
                + "@127.0.0.1:"
                + ports["postgres"]
                + "/goalstats_test_runtime",
                "TEST_REDIS_URL": "redis://:"
                + redis_password
                + "@127.0.0.1:"
                + ports["redis"]
                + "/0",
            }
            private_write(
                manifest_path,
                json.dumps(
                    {
                        "version": 1,
                        "state": "active",
                        "root": str(ROOT),
                        "project": project,
                        "token": token,
                        "pid": os.getpid(),
                        "urls": urls,
                        "policy": schema.test_policy(ROOT),
                        "containers": {s: c["Id"] for s, c in containers.items()},
                    }
                ),
            )
            env = {
                "APP_ENV": "test",
                **urls,
                "DATABASE_URL": urls["TEST_DATABASE_URL"],
                "REDIS_URL": urls["TEST_REDIS_URL"],
                "TEST_DATABASE_DISPOSABLE": "1",
                "TEST_REDIS_DISPOSABLE": "1",
                "TEST_SESSION_MANIFEST": str(manifest_path),
                "FLASK_DEBUG": "0",
            }
            verify_host_session(env)
            print(
                "Owned TEST session ready. Run an integration test here; no env profile needed.",
                flush=True,
            )
            print(
                "Keep this owner running. Ctrl-C/SIGTERM removes only this disposable session.",
                flush=True,
            )
            while True:
                time.sleep(1)
        finally:
            # Revoke the lease before cleanup; retain evidence on cleanup failure.
            if manifest_path.exists():
                manifest_path.unlink()
            stack.stop(volumes=True)
            assert_absent(project)
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()
