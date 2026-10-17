"""Fail-closed host receipt validation and invocation-owned process supervision."""

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from test_resources import (
    PASSWORD,
    ROOT,
    SESSION,
    USER,
    inspect_providers,
    private_receipt_path,
    validate_project,
)


def validate_receipt(data, env, session):
    """Validate target constraints before any live inspection or provider connection."""
    try:
        project = data["project"]
        validate_project(project)
        database = urlsplit(data["TEST_DATABASE_URL"])
        redis = urlsplit(data["TEST_REDIS_URL"])
        if (
            data["version"] != 3
            or env.get("TEST_PROJECT") != project
            or not SESSION.fullmatch(data["session"])
            or session != data["session"]
            or env.get("TEST_SESSION") != session
            or set(data["providers"]) != {"postgres", "redis"}
            or any(not re.fullmatch(r"[a-f0-9]{64}", v) for v in data["providers"].values())
            or len(set(data["providers"].values())) != 2
            or not re.fullmatch(r"[a-f0-9]{64}", data["network"])
            or database.scheme != "postgresql+psycopg"
            or database.hostname != "127.0.0.1"
            or not 1 <= (database.port or 0) <= 65535
            or not USER.fullmatch(database.username or "")
            or not PASSWORD.fullmatch(database.password or "")
            or database.path != "/goalstats_test_runtime"
            or database.query
            or database.fragment
            or redis.scheme != "redis"
            or redis.hostname != "127.0.0.1"
            or not 1 <= (redis.port or 0) <= 65535
            or redis.port == database.port
            or redis.username != ""
            or not PASSWORD.fullmatch(redis.password or "")
            or redis.password == database.password
            or redis.path != "/0"
            or redis.query
            or redis.fragment
            or any(
                env.get(key) != data[source]
                for key, source in (
                    ("TEST_DATABASE_URL", "TEST_DATABASE_URL"),
                    ("DATABASE_URL", "TEST_DATABASE_URL"),
                    ("TEST_REDIS_URL", "TEST_REDIS_URL"),
                    ("REDIS_URL", "TEST_REDIS_URL"),
                )
            )
            or env.get("APP_ENV") != "test"
            or env.get("TEST_DATABASE_DISPOSABLE") != "1"
            or env.get("TEST_REDIS_DISPOSABLE") != "1"
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError, RuntimeError):
        raise RuntimeError("Invalid owned host TEST receipt") from None


def receipt_environment(data, environ):
    env = dict(environ)
    env.update(
        APP_ENV="test",
        TEST_DATABASE_DISPOSABLE="1",
        TEST_REDIS_DISPOSABLE="1",
        DATABASE_URL=data["TEST_DATABASE_URL"],
        TEST_DATABASE_URL=data["TEST_DATABASE_URL"],
        REDIS_URL=data["TEST_REDIS_URL"],
        TEST_REDIS_URL=data["TEST_REDIS_URL"],
        CACHE_KEY_PREFIX="goal-stats-service:test:v1",
        OPENAPI_ENABLED="true",
        LOG_LEVEL="INFO",
        CACHE_TTL_SECONDS="300",
    )
    return env


def load_receipt(env):
    path = private_receipt_path(env["TEST_SESSION_MANIFEST"], env["TEST_PROJECT"])
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor) as stream:
        data = json.load(stream)
    if data["directory"] != str(path.parent):
        raise RuntimeError("Receipt directory mismatch")
    return data


def verify_test_providers(environ=None):
    env = os.environ if environ is None else environ
    try:
        if Path(sys.prefix) != ROOT / ".venv" or sys.version_info[:2] != (3, 12):
            raise RuntimeError("Repository Python 3.12 required")
        data = load_receipt(env)
        validate_receipt(data, env, env["TEST_SESSION"])
        database, redis = urlsplit(data["TEST_DATABASE_URL"]), urlsplit(data["TEST_REDIS_URL"])
        identities, ports, network = inspect_providers(
            data["project"], data["session"], database.username, database.password, redis.password
        )
        if (
            identities != data["providers"]
            or network != data["network"]
            or ports
            != {
                "postgres": database.port,
                "redis": redis.port,
            }
        ):
            raise RuntimeError("Live provider identity changed")
        return data
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        raise RuntimeError(
            "Unverified TEST providers: use make test with its owned host receipt"
        ) from None


def owned_test_config(environ=None):
    """Reinspect live providers before exposing configuration to shared fixtures."""
    env = dict(os.environ if environ is None else environ)
    verify_test_providers(env)
    return env


def authenticate(env):
    """Prove the verified endpoints accept this session's credentials before commands."""
    from redis import Redis
    from sqlalchemy import create_engine, text

    engine = create_engine(env["DATABASE_URL"], connect_args={"connect_timeout": 5})
    client = Redis.from_url(env["REDIS_URL"], socket_connect_timeout=5, socket_timeout=5)
    try:
        with engine.connect() as connection:
            identity = connection.execute(text("SELECT current_database(), current_user")).one()
            if tuple(identity) != (
                "goalstats_test_runtime",
                urlsplit(env["DATABASE_URL"]).username,
            ):
                raise RuntimeError("Database identity mismatch")
        if client.ping() is not True:
            raise RuntimeError("Redis authentication failed")
    except Exception:
        raise RuntimeError(
            "Disposable provider authentication failed (credentials omitted)"
        ) from None
    finally:
        client.close()
        engine.dispose()


def signal_group(pgid, signum):
    """Signal only the owned group; Darwin can report EPERM for an exiting group."""
    try:
        os.killpg(pgid, signum)
    except PermissionError:
        if sys.platform != "darwin":
            raise
        # XNU excludes zombies from group signalling and returns EPERM when no
        # eligible member remains. Do not mistake a live, inaccessible group for
        # this exit race, or suppress an unsuccessful process-table inspection.
        result = subprocess.run(
            ["/bin/ps", "-axo", "pgid=,stat="],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            group, state = line.split()
            if int(group) == pgid and not state.startswith("Z"):
                raise
        raise ProcessLookupError("Owned process group has exited") from None


def supervise(command, env=None):
    """Own one process group; relay interruption and reap before infrastructure cleanup."""
    interrupted = 0
    child = None
    code = None

    def record_signal(signum, _frame):
        nonlocal interrupted
        interrupted = interrupted or signum

    previous = {sig: signal.signal(sig, record_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        child = subprocess.Popen(command, env=env, start_new_session=True)
        deadline = None
        while True:
            if interrupted:
                try:
                    if deadline is None:
                        signal_group(child.pid, signal.SIGTERM)
                        deadline = time.monotonic() + 3
                    elif time.monotonic() >= deadline:
                        signal_group(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                code = child.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        try:
            if child is not None:
                # Also terminate descendants left behind by a command that already exited.
                try:
                    signal_group(child.pid, signal.SIGTERM)
                    # Nested supervisors need their three-second grace period to stop
                    # their own groups before we terminate the remaining descendants.
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        child.poll()
                        signal_group(child.pid, 0)
                        time.sleep(0.05)
                    signal_group(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        except (OSError, ValueError, subprocess.SubprocessError):
            # Report cleanup errors without replacing an original interruption or
            # child failure. Successful execution must still fail on cleanup error.
            print(
                "Owned process cleanup failed; configuration and credentials omitted.",
                file=sys.stderr,
            )
            if not interrupted and not code:
                raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 128 + interrupted if interrupted else (128 - code if code < 0 else code)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in {"execute", "owned"}:
        raise RuntimeError("An internal execution mode and command are required")
    env = dict(os.environ)
    if sys.argv[1] == "owned":
        data = load_receipt(env)
        # Never silently replace inherited URLs, even through the internal entry point.
        if any(
            key in env
            for key in ("DATABASE_URL", "REDIS_URL", "TEST_DATABASE_URL", "TEST_REDIS_URL")
        ):
            raise RuntimeError("Inherited provider URLs refused")
        env = receipt_environment(data, env)
        verify_test_providers(env)
        authenticate(env)
    return supervise(sys.argv[2:], env)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        sys.exit("Owned host execution failed; configuration and credentials omitted.")
