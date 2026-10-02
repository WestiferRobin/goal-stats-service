"""Fail-closed ownership verification before any host TEST provider connection."""

import fcntl
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from environment_config import schema

ROOT = Path(__file__).resolve().parents[1]
SESSION_LABEL = "dev.host-test-session"


def inspect_container(identity):
    result = subprocess.run(
        ["docker", "inspect", identity], capture_output=True, text=True, check=True, timeout=15
    )
    return json.loads(result.stdout)[0]


def private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("TEST session files must be private regular files owned by this user")
    return path.read_text()


def verify_host_session(environ=None):
    """Check both providers, including server-wide Redis ownership, before returning URLs."""
    env = os.environ if environ is None else environ
    try:
        path = Path(env["TEST_SESSION_MANIFEST"])
        parent = ROOT / ".host-sessions"
        if (
            not path.is_absolute()
            or path.resolve() != path
            or path.parent.parent != parent
            or path.name != "manifest.json"
            or path.parent.stat().st_mode & 0o077
            or path.parent.stat().st_uid != os.getuid()
        ):
            raise ValueError
        manifest = json.loads(private_file(path))
        project = manifest["project"]
        if (
            manifest["version"] != 1
            or manifest["state"] != "active"
            or manifest["root"] != str(ROOT)
            or not re.fullmatch(r"goal-stats-service-test-[a-f0-9]{24}", project)
            or path.parent.name != project
            or not re.fullmatch(r"[a-f0-9]{48}", manifest["token"])
        ):
            raise ValueError
        lock = path.with_name("owner.lock")
        private_file(lock)
        with lock.open() as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise ValueError("Session owner is no longer running")
        os.kill(manifest["pid"], 0)
        for service, key, internal, scheme in (
            ("postgres", "TEST_DATABASE_URL", "5432/tcp", "postgresql+psycopg"),
            ("redis", "TEST_REDIS_URL", "6379/tcp", "redis"),
        ):
            expected = manifest["urls"][key]
            if env.get(key) != expected:
                raise ValueError
            url = urlsplit(expected)
            if url.scheme != scheme or url.hostname != "127.0.0.1" or not url.port:
                raise ValueError
            container = inspect_container(manifest["containers"][service])
            labels = container["Config"]["Labels"]
            if (
                container["Id"] != manifest["containers"][service]
                or not container["State"]["Running"]
                or container["State"].get("Health", {}).get("Status") != "healthy"
                or labels.get("com.docker.compose.project") != project
                or labels.get("com.docker.compose.service") != service
                or labels.get(SESSION_LABEL) != manifest["token"]
                or labels.get("com.docker.compose.oneoff", "False").lower() != "false"
                or container["NetworkSettings"]["Ports"].get(internal)
                != [{"HostIp": "127.0.0.1", "HostPort": str(url.port)}]
            ):
                raise ValueError
            target = "/var/lib/postgresql/data" if service == "postgres" else "/data"
            if target not in container["HostConfig"].get("Tmpfs", {}):
                raise ValueError
            if any(m["Type"] in {"volume", "bind"} for m in container["Mounts"]):
                raise ValueError
            if set(container["NetworkSettings"]["Networks"]) != {project + "_default"}:
                raise ValueError
            if service == "postgres":
                settings = dict(v.split("=", 1) for v in container["Config"]["Env"] if "=" in v)
                if (
                    url.username != settings["POSTGRES_USER"]
                    or url.password != settings["POSTGRES_PASSWORD"]
                    or url.path != "/" + settings["POSTGRES_DB"]
                    or url.path != "/goalstats_test_runtime"
                ):
                    raise ValueError
            elif (
                container["Config"]["Cmd"]
                != [
                    "redis-server",
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--requirepass",
                    url.password,
                ]
                or url.path != "/0"
            ):
                raise ValueError
        return manifest
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        raise RuntimeError(
            "Unverified TEST providers: start make test-providers and use its "
            "owned session; stale or mismatched sessions are refused."
        ) from None


def verify_test_providers(environ=None):
    env = os.environ if environ is None else environ
    # The canonical runner has a private, read-only receipt mounted by its owner.
    # A host environment variable alone cannot select this path.
    receipt = Path("/run/owned-test.json")
    if Path("/.dockerenv").is_file() and receipt.is_file():
        try:
            data = json.loads(receipt.read_text())
            if (
                data["hostname"] != os.uname().nodename
                or env.get("TEST_DATABASE_URL") != data["TEST_DATABASE_URL"]
                or env.get("TEST_REDIS_URL") != data["TEST_REDIS_URL"]
                or urlsplit(data["TEST_DATABASE_URL"]).hostname != "postgres"
                or urlsplit(data["TEST_REDIS_URL"]).hostname != "redis"
            ):
                raise ValueError
            return
        except (OSError, ValueError, KeyError, TypeError):
            raise RuntimeError("Invalid owned Docker TEST runner receipt") from None
    verify_host_session(env)


def owned_test_config(environ=None):
    """Resolve only at fixture execution; manifests never authorize unchecked endpoints."""
    env = dict(os.environ if environ is None else environ)
    if any(key in env for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "TEST_SESSION_MANIFEST")):
        verify_test_providers(env)
        return env
    paths = list((ROOT / ".host-sessions").glob("*/manifest.json"))
    if len(paths) != 1:
        raise RuntimeError(
            "Start make test-providers in this repository; exactly one active session is required."
        )
    path = paths[0]
    try:
        data = json.loads(private_file(path))
        values = {**data["urls"], "TEST_SESSION_MANIFEST": str(path)}
        manifest = verify_host_session(values)
        preferences = schema.policy(manifest.get("policy", {}))
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError("Invalid owned TEST session; restart make test-providers.") from None
    return {
        **preferences,
        **values,
        "APP_ENV": "test",
        "TEST_DATABASE_DISPOSABLE": "1",
        "TEST_REDIS_DISPOSABLE": "1",
    }
