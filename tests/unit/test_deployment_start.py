"""Verify migration ordering/failure and server arguments with recording executables."""

import os
import subprocess
from pathlib import Path

import pytest

START = Path(__file__).resolve().parents[2] / "scripts/deployment/start.sh"


@pytest.mark.parametrize(
    "arguments,migration_status,port,expected_status,expected_commands",
    [
        ([], "0", None, 0, ["gunicorn"]),
        (["--migrate"], "0", "10000", 0, ["alembic", "gunicorn"]),
        (["--migrate"], "7", "10000", 7, ["alembic"]),
        (["unknown"], "0", None, 2, []),
    ],
)
def test_deployment_start(
    tmp_path, arguments, migration_status, port, expected_status, expected_commands
):
    record = tmp_path / "record"
    for command in ("alembic", "gunicorn"):
        executable = tmp_path / command
        executable.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$(basename "$0") $*" >> "$RECORD"\n'
            + ('exit "$MIGRATION_STATUS"\n' if command == "alembic" else "exit 0\n")
        )
        executable.chmod(0o700)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "RECORD": str(record),
        "MIGRATION_STATUS": migration_status,
    }
    env.pop("PORT", None)
    if port:
        env["PORT"] = port
    result = subprocess.run(["/bin/sh", str(START), *arguments], env=env, capture_output=True)
    assert result.returncode == expected_status
    calls = record.read_text().splitlines() if record.exists() else []
    assert [line.split()[0] for line in calls] == expected_commands
    if "alembic" in expected_commands:
        assert calls[0] == "alembic upgrade head"
    if "gunicorn" in expected_commands:
        assert f"--bind 0.0.0.0:{port or '8000'}" in calls[-1]
        assert "main:create_app()" in calls[-1]
