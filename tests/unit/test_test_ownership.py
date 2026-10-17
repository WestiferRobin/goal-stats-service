"""Host attestations and private session receipts fail closed before provider access."""

from copy import deepcopy

import pytest
from test_ownership import validate_receipt
from test_resources import validate_project, validate_provider


@pytest.fixture
def receipt():
    project = "goal-stats-service-test-" + "a" * 24
    database = (
        "postgresql+psycopg://test_aaaaaaaaaaaaaaaaaaaaaaaa:test-"
        + "b" * 48
        + "@127.0.0.1:49151/goalstats_test_runtime"
    )
    data = {
        "version": 3,
        "project": project,
        "session": "e" * 48,
        "network": "f" * 64,
        "providers": {"postgres": "c" * 64, "redis": "d" * 64},
        "TEST_DATABASE_URL": database,
        "TEST_REDIS_URL": "redis://:test-" + "d" * 48 + "@127.0.0.1:49152/0",
    }
    env = {
        "TEST_PROJECT": project,
        "APP_ENV": "test",
        "TEST_SESSION": data["session"],
        "TEST_DATABASE_DISPOSABLE": "1",
        "TEST_REDIS_DISPOSABLE": "1",
        "DATABASE_URL": database,
        "REDIS_URL": data["TEST_REDIS_URL"],
        "TEST_DATABASE_URL": database,
        "TEST_REDIS_URL": data["TEST_REDIS_URL"],
    }
    return data, env


def test_valid_receipt(receipt):
    data, env = receipt
    validate_receipt(data, env, data["session"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("project", "goalstats-service-local"),
        ("session", "another-session"),
        ("version", 1),
        ("providers", {}),
        (
            "TEST_DATABASE_URL",
            "postgresql+psycopg://goalstats:private@postgres:5432/goal_stats_service_local",
        ),
        ("TEST_REDIS_URL", "redis://prizm-redis:6379/0"),
    ],
)
def test_invalid_receipt(receipt, key, value):
    data, env = receipt
    data[key] = value
    with pytest.raises(RuntimeError, match="Invalid owned") as error:
        validate_receipt(data, env, env["TEST_SESSION"])
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "field",
    ["TEST_PROJECT", "APP_ENV", "DATABASE_URL", "REDIS_URL", "TEST_DATABASE_URL", "TEST_REDIS_URL"],
)
def test_conflicting_environment(receipt, field):
    data, env = receipt
    env[field] = "conflicting-secret"
    with pytest.raises(RuntimeError, match="Invalid owned"):
        validate_receipt(data, env, data["session"])


@pytest.mark.parametrize("data", [{}, None, {"version": 3}])
def test_missing_or_malformed_receipt(data):
    with pytest.raises(RuntimeError):
        validate_receipt(data, {}, "unowned")


def test_wrong_session(receipt):
    data, env = receipt
    with pytest.raises(RuntimeError):
        validate_receipt(data, env, "other-container")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://test_aaaaaaaaaaaaaaaaaaaaaaaa:test-"
        + "b" * 48
        + "@localhost:5432/goalstats_test_runtime",
        "postgresql+psycopg://test_aaaaaaaaaaaaaaaaaaaaaaaa:test-"
        + "b" * 48
        + "@postgres:5432/goal_stats_service_local",
        "postgresql+psycopg://goalstats:development-password@127.0.0.1:49151/goalstats_test_runtime",
    ],
)
def test_matching_environment_cannot_authorize_arbitrary_targets(receipt, url):
    data, env = receipt
    data["TEST_DATABASE_URL"] = env["TEST_DATABASE_URL"] = env["DATABASE_URL"] = url
    with pytest.raises(RuntimeError):
        validate_receipt(data, env, data["session"])


@pytest.fixture
def provider(receipt):
    data, _ = receipt
    project = data["project"]
    return {
        "Id": "c" * 64,
        "Config": {
            "Labels": {
                "com.docker.compose.project": project,
                "com.docker.compose.service": "postgres",
                "org.goalstats.test-session": data["session"],
            },
            "Env": [
                "POSTGRES_USER=test_" + "a" * 24,
                "POSTGRES_DB=goalstats_test_runtime",
                "POSTGRES_PASSWORD=test-" + "b" * 48,
            ],
        },
        "State": {"Running": True, "Health": {"Status": "healthy"}},
        "HostConfig": {"Tmpfs": {"/var/lib/postgresql/data": ""}},
        "Mounts": [],
        "NetworkSettings": {
            "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49151"}]},
            "Networks": {project + "_default": {}},
        },
    }


def test_provider_verified_before_receipt(provider, receipt):
    validate_provider(
        provider,
        receipt[0]["project"],
        "postgres",
        "test-" + "b" * 48,
        receipt[0]["session"],
        "test_" + "a" * 24,
    )


@pytest.mark.parametrize(
    "change",
    ["project", "service", "port", "volume", "network", "health", "database", "password", "id"],
)
def test_provider_attestation_rejects_wrong_resources(provider, receipt, change):
    c = deepcopy(provider)
    if change in {"project", "service"}:
        c["Config"]["Labels"]["com.docker.compose." + change] = "unrelated"
    elif change == "port":
        c["NetworkSettings"]["Ports"]["5432/tcp"] = [{"HostPort": "55432"}]
    elif change == "volume":
        c["Mounts"] = [{"Type": "volume"}]
    elif change == "network":
        c["NetworkSettings"]["Networks"] = {"prizm": {}}
    elif change == "health":
        c["State"]["Health"]["Status"] = "unhealthy"
    elif change in {"database", "password"}:
        c["Config"]["Env"] = []
    else:
        c["Id"] = "unverified"
    with pytest.raises(RuntimeError):
        validate_provider(
            c,
            receipt[0]["project"],
            "postgres",
            "test-" + "b" * 48,
            receipt[0]["session"],
            "test_" + "a" * 24,
        )


@pytest.mark.parametrize(
    "project",
    [
        "goalstats-service-local",
        "prizm-infra",
        "goal-stats-service-dev",
        "goal-stats-service-test-",
    ],
)
def test_only_unique_test_projects_allowed(project):
    with pytest.raises(RuntimeError):
        validate_project(project)


@pytest.mark.parametrize("content", [None, "not-json", "{}"])
def test_requires_readable_valid_receipt(tmp_path, monkeypatch, content):
    import test_ownership as ownership

    receipt_path = tmp_path / "owned-test.json"
    if content is not None:
        receipt_path.write_text(content)
    monkeypatch.setattr(ownership, "private_receipt_path", lambda *args: receipt_path)
    with pytest.raises(RuntimeError, match="Unverified TEST"):
        ownership.verify_test_providers(
            {"TEST_SESSION_MANIFEST": str(receipt_path), "TEST_PROJECT": "invalid"}
        )


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"TEST_SESSION_MANIFEST": "/old/manifest.json"},
        {"TEST_DATABASE_URL": "postgresql://private@localhost/dev"},
    ],
)
def test_unowned_host_provider_configuration_is_refused(env):
    import test_ownership as ownership

    with pytest.raises(RuntimeError, match="use make test") as error:
        ownership.owned_test_config(env)
    assert "private@" not in str(error.value)


@pytest.mark.parametrize(
    "mapping",
    [
        None,
        [],
        [{"HostIp": "0.0.0.0", "HostPort": "49151"}],
        [{"HostIp": "127.0.0.1", "HostPort": "0"}],
        [{"HostIp": "127.0.0.1", "HostPort": "65536"}],
        [{"HostIp": "127.0.0.1", "HostPort": "invalid"}],
        [{"HostIp": "127.0.0.1", "HostPort": "49151"}] * 2,
    ],
)
def test_invalid_host_port_mappings(provider, receipt, mapping):
    provider["NetworkSettings"]["Ports"]["5432/tcp"] = mapping
    with pytest.raises(RuntimeError):
        validate_provider(
            provider,
            receipt[0]["project"],
            "postgres",
            "test-" + "b" * 48,
            receipt[0]["session"],
            "test_" + "a" * 24,
        )


def test_redis_authentication_configuration(provider, receipt):
    from test_resources import REDIS_COMMAND

    data, _ = receipt
    provider["Config"]["Labels"]["com.docker.compose.service"] = "redis"
    provider["Config"]["Cmd"] = REDIS_COMMAND
    provider["Config"]["Env"] = ["REDIS_PASSWORD=test-" + "d" * 48]
    provider["HostConfig"]["Tmpfs"] = {"/data": ""}
    provider["NetworkSettings"]["Ports"] = {
        "6379/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]
    }
    assert (
        validate_provider(provider, data["project"], "redis", "test-" + "d" * 48, data["session"])
        == 49152
    )
    provider["Config"]["Env"] = []
    with pytest.raises(RuntimeError):
        validate_provider(provider, data["project"], "redis", "test-" + "d" * 48, data["session"])


@pytest.fixture
def private_receipt(tmp_path, monkeypatch, receipt):
    import json

    import test_resources as resources

    data, env = receipt
    monkeypatch.setattr(resources, "ROOT", tmp_path)
    directory = tmp_path / ".host-sessions" / (data["project"] + ".unique")
    directory.mkdir(parents=True, mode=0o700)
    path = directory / "owned-test.json"
    data["directory"] = str(directory)
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    env["TEST_SESSION_MANIFEST"] = str(path)
    return path, data, env


@pytest.mark.parametrize(
    "change", ["file-mode", "directory-mode", "symlink", "directory-link", "hardlink", "owner"]
)
def test_private_receipt_substitution_is_rejected(private_receipt, monkeypatch, change):
    import os

    from test_resources import private_receipt_path

    path, data, _ = private_receipt
    if change == "file-mode":
        path.chmod(0o644)
    elif change == "directory-mode":
        path.parent.chmod(0o755)
    elif change == "symlink":
        other = path.with_name("other")
        path.rename(other)
        path.symlink_to(other)
    elif change == "directory-link":
        parent = path.parent
        other = parent.with_name(parent.name + "-actual")
        parent.rename(other)
        parent.symlink_to(other, target_is_directory=True)
    elif change == "hardlink":
        os.link(path, path.with_name("alias"))
    else:
        monkeypatch.setattr(os, "getuid", lambda: -1)
    with pytest.raises(RuntimeError):
        private_receipt_path(path, data["project"])


def test_host_fixture_reinspects_live_identity(private_receipt, monkeypatch):
    import test_ownership as ownership

    _, data, env = private_receipt
    calls = []

    def inspect(*args):
        calls.append(args)
        return data["providers"], {"postgres": 49151, "redis": 49152}, data["network"]

    monkeypatch.setattr(ownership, "inspect_providers", inspect)
    assert ownership.owned_test_config(env) == env
    assert len(calls) == 1
    monkeypatch.setattr(ownership, "inspect_providers", lambda *args: ({}, {}, "wrong"))
    with pytest.raises(RuntimeError, match="Unverified"):
        ownership.owned_test_config(env)


@pytest.mark.parametrize("change", ["session", "extra-port", "bind", "tmpfs", "stopped", "oneoff"])
def test_additional_provider_boundaries(provider, receipt, change):
    if change == "session":
        provider["Config"]["Labels"]["org.goalstats.test-session"] = "0" * 48
    elif change == "extra-port":
        provider["NetworkSettings"]["Ports"]["1234/tcp"] = None
    elif change == "bind":
        provider["Mounts"] = [{"Type": "bind"}]
    elif change == "tmpfs":
        provider["HostConfig"]["Tmpfs"] = {}
    elif change == "stopped":
        provider["State"]["Running"] = False
    else:
        provider["Config"]["Labels"]["com.docker.compose.oneoff"] = "True"
    with pytest.raises(RuntimeError):
        validate_provider(
            provider,
            receipt[0]["project"],
            "postgres",
            "test-" + "b" * 48,
            receipt[0]["session"],
            "test_" + "a" * 24,
        )


@pytest.mark.parametrize("signame,expected", [("SIGINT", 130), ("SIGTERM", 143)])
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("stubborn", [True, False])
def test_supervisor_terminates_stubborn_process_tree(tmp_path, signame, expected, nested, stubborn):
    import json
    import os
    import signal
    import subprocess
    import sys
    import time
    from pathlib import Path

    pidfile = tmp_path / "children.json"
    # The grandchild acknowledges startup before the leaf atomically publishes its PIDs.
    code = (
        "import json, os, signal, subprocess, sys, time; from pathlib import Path; "
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN); " if stubborn else "")
        + "child = subprocess.Popen([sys.executable, '-B', '-c', "
        "'import time; print(1, flush=True); time.sleep(60)'], stdout=subprocess.PIPE); "
        "assert child.stdout.readline() == b'1\\n'; "
        "p = Path(sys.argv[1]); "
        "p.with_suffix('.tmp').write_text(json.dumps([os.getpid(), child.pid])); "
        "p.with_suffix('.tmp').replace(p); time.sleep(60)"
    )
    helper = Path(__file__).resolve().parents[2] / "scripts/testing"
    # Entering wait proves Popen returned, the child is registered, and handlers
    # are installed. This instruments the real main/supervise path, not its logic.
    harness = (
        "import os, sys, subprocess; from pathlib import Path; "
        f"sys.path.insert(0, {str(helper)!r}); import test_ownership as ownership\n"
        "ready = Path(sys.argv.pop(1))\n"
        "class Registered(subprocess.Popen):\n"
        " def wait(self, *args, **kwargs):\n"
        "  if not ready.exists():\n"
        "   pending = ready.with_suffix('.tmp')\n"
        "   pending.write_text(str(os.getpid()))\n"
        "   pending.replace(ready)\n"
        "  return super().wait(*args, **kwargs)\n"
        "ownership.subprocess.Popen = Registered\n"
        "sys.exit(ownership.main())\n"
    )
    command = [sys.executable, "-B", "-c", code, str(pidfile)]
    markers = [tmp_path / "outer.ready"]
    wrapper = tmp_path / "wrapper.pid"
    if nested:
        markers.append(tmp_path / "inner.ready")
        inner = [sys.executable, "-B", "-c", harness, str(markers[1]), "execute", *command]
        command = [
            sys.executable,
            "-B",
            "-c",
            "import os, subprocess; from pathlib import Path; "
            f"Path({str(wrapper)!r}).write_text(str(os.getpid())); "
            f"subprocess.run({inner!r}, check=False)",
        ]
    unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
    supervisor = subprocess.Popen(
        [sys.executable, "-B", "-c", harness, str(markers[0]), "execute", *command],
        stderr=subprocess.PIPE,
        text=True,
    )
    owned = []
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if pidfile.exists() and all(p.exists() for p in markers):
                break
            assert supervisor.poll() is None, "Supervisor exited before readiness"
            time.sleep(0.01)
        assert pidfile.exists() and all(p.exists() for p in markers), "Tree did not become ready"
        owned = json.loads(pidfile.read_text()) + [int(p.read_text()) for p in markers]
        if nested:
            owned.append(int(wrapper.read_text()))
        supervisor.send_signal(getattr(signal, signame))
        _, errors = supervisor.communicate(timeout=12)
        assert supervisor.returncode == expected, errors
        assert not errors, errors  # Includes errors from inner supervisors.
        deadline = time.monotonic() + 3
        while True:
            states = subprocess.run(
                ["ps", "-p", ",".join(map(str, owned)), "-o", "stat="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.split()
            if not states:
                break
            assert time.monotonic() < deadline, f"Owned processes survived cleanup: {states}"
            time.sleep(0.01)
        assert unrelated.poll() is None, "An unrelated process was terminated"
    finally:
        if supervisor.poll() is None:
            supervisor.terminate()
            supervisor.communicate(timeout=12)
        if pidfile.exists():
            owned.extend(json.loads(pidfile.read_text()))
        for p in markers:
            if p.exists():
                owned.append(int(p.read_text()))
        if wrapper.exists():
            owned.append(int(wrapper.read_text()))
        for pid in set(owned):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        unrelated.terminate()
        unrelated.wait(timeout=5)


@pytest.mark.parametrize("signame,expected", [("SIGINT", 130), ("SIGTERM", 143)])
def test_supervisor_signal_during_child_registration(monkeypatch, signame, expected):
    import os
    import signal
    import subprocess
    import sys

    import test_ownership as ownership

    popen = subprocess.Popen
    children = []
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def start(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        # Popen has created the group but supervise has not assigned child yet.
        os.kill(os.getpid(), getattr(signal, signame))
        return child

    monkeypatch.setattr(ownership.subprocess, "Popen", start)
    try:
        assert (
            ownership.supervise([sys.executable, "-B", "-c", "import time; time.sleep(60)"])
            == expected
        )
        assert children[0].poll() is not None
        assert all(signal.getsignal(sig) == handler for sig, handler in previous.items())
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


@pytest.mark.parametrize("code", [0, 1, 7])
def test_supervisor_preserves_real_child_exit(code):
    import subprocess
    import sys
    from pathlib import Path

    helper = Path(__file__).resolve().parents[2] / "scripts/testing/test_ownership.py"
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(helper),
            "execute",
            sys.executable,
            "-B",
            "-c",
            f"raise SystemExit({code})",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == code
    assert not result.stderr


@pytest.mark.parametrize("output", ["", "123 Z\n456 S\n"])
def test_darwin_exited_group_permission_race(monkeypatch, output):
    import subprocess

    import test_ownership as ownership

    monkeypatch.setattr(ownership.sys, "platform", "darwin")

    def denied(*args):
        raise PermissionError("private")

    def inspect(command, **kwargs):
        assert command == ["/bin/ps", "-axo", "pgid=,stat="]
        assert kwargs["check"] and kwargs["timeout"] == 5
        return subprocess.CompletedProcess(command, 0, output)

    monkeypatch.setattr(ownership.os, "killpg", denied)
    monkeypatch.setattr(ownership.subprocess, "run", inspect)
    with pytest.raises(ProcessLookupError, match="has exited"):
        ownership.signal_group(123, 0)


@pytest.mark.parametrize("case", ["live", "inspection-failure", "malformed", "non-darwin"])
def test_group_permission_failure_is_not_hidden(monkeypatch, case):
    import subprocess

    import test_ownership as ownership

    monkeypatch.setattr(ownership.sys, "platform", "linux" if case == "non-darwin" else "darwin")

    def denied(*args):
        raise PermissionError("private")

    def inspect(command, **kwargs):
        if case == "inspection-failure":
            raise subprocess.TimeoutExpired(command, 5)
        assert case != "non-darwin"
        return subprocess.CompletedProcess(
            command, 0, "invalid" if case == "malformed" else "123 S\n"
        )

    monkeypatch.setattr(ownership.os, "killpg", denied)
    monkeypatch.setattr(ownership.subprocess, "run", inspect)
    expected = {"inspection-failure": subprocess.TimeoutExpired, "malformed": ValueError}.get(
        case, PermissionError
    )
    with pytest.raises(expected):
        ownership.signal_group(123, 0)


@pytest.mark.parametrize("signame", [None, "SIGINT", "SIGTERM"])
@pytest.mark.parametrize("child_code", [0, 7])
def test_cleanup_failure_reported_without_overriding_primary_failure(
    monkeypatch, capsys, signame, child_code
):
    import signal

    import test_ownership as ownership

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    class ExitedChild:
        pid = 123

        def wait(self, **kwargs):
            if signame:
                sig = getattr(signal, signame)
                signal.getsignal(sig)(sig, None)
                # A later TERM must not overwrite the first signal.
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return child_code

    def denied(*args):
        raise PermissionError("private-credential")

    monkeypatch.setattr(ownership.subprocess, "Popen", lambda *args, **kwargs: ExitedChild())
    monkeypatch.setattr(ownership, "signal_group", denied)
    if signame or child_code:
        expected = 128 + getattr(signal, signame) if signame else child_code
        assert ownership.supervise(["unused"]) == expected
    else:
        with pytest.raises(PermissionError):
            ownership.supervise(["unused"])
    errors = capsys.readouterr().err
    assert "Owned process cleanup failed" in errors
    assert "private-credential" not in errors
    assert all(signal.getsignal(sig) == handler for sig, handler in previous.items())
