"""Fail-closed ownership verification for canonical disposable Docker tests."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate_receipt(data, env, hostname):
    """Validate the host-issued receipt without trusting TEST environment labels."""
    try:
        project = data["project"]
        database = urlsplit(data["TEST_DATABASE_URL"])
        if (
            data["version"] != 2
            or not re.fullmatch(r"goal-stats-service-test-[a-f0-9]{24}", project)
            or env.get("TEST_PROJECT") != project
            or data["hostname"] != project + "-runner"
            or hostname != data["hostname"]
            or set(data["providers"]) != {"postgres", "redis"}
            or any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in data["providers"].values())
            or len(set(data["providers"].values())) != 2
            or database.scheme != "postgresql+psycopg"
            or database.hostname != "postgres"
            or database.port != 5432
            or database.username != "goalstats"
            or not re.fullmatch(r"test-[a-f0-9]{48}", database.password or "")
            or database.path != "/goalstats_test_runtime"
            or database.query
            or database.fragment
            or data["TEST_REDIS_URL"] != "redis://redis:6379/0"
            or env.get("TEST_DATABASE_URL") != data["TEST_DATABASE_URL"]
            or env.get("TEST_REDIS_URL") != data["TEST_REDIS_URL"]
            or env.get("DATABASE_URL") != data["TEST_DATABASE_URL"]
            or env.get("REDIS_URL") != data["TEST_REDIS_URL"]
            or env.get("APP_ENV") != "test"
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Invalid owned Docker TEST runner receipt") from None


def verify_test_providers(environ=None):
    env = os.environ if environ is None else environ
    receipt = Path("/run/owned-test.json")
    if Path("/.dockerenv").is_file():
        try:
            data = json.loads(receipt.read_text())
            validate_receipt(data, env, os.uname().nodename)
            return
        except (OSError, ValueError, RuntimeError):
            raise RuntimeError(
                "Unverified TEST providers: invalid or missing Docker receipt"
            ) from None
    raise RuntimeError("Unverified TEST providers: use make test with its owned Docker runner")


def owned_test_config(environ=None):
    """Validate the runner receipt before exposing provider configuration to fixtures."""
    env = dict(os.environ if environ is None else environ)
    verify_test_providers(env)
    return env


if __name__ == "__main__":
    import sys

    try:
        verify_test_providers()
        if len(sys.argv) < 2:
            raise RuntimeError("An owned test command is required")
        os.execvp(sys.argv[1], sys.argv[1:])
    except (OSError, RuntimeError) as exc:
        sys.exit(str(exc))
