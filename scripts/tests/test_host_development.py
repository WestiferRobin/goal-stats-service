"""Provider-free host safety checks; no test connects to a database or cache."""

import fcntl
import json
import os
from copy import deepcopy
from unittest.mock import Mock

import host_development as host
import pytest
import test_ownership as ownership
from workflow import Stack, read_settings


@pytest.mark.parametrize("key", ["HOST_APP_PORT", "LOCAL_POSTGRES_PORT", "LOCAL_REDIS_PORT"])
@pytest.mark.parametrize("value", ["0", "65536", "no", "-1", "５３００", ""])
def test_invalid_host_port_refused(tmp_path, key, value):
    path = tmp_path / ".env.local"
    path.write_text(
        f"POSTGRES_PASSWORD=abcdefghijklmnop\nDEV_POSTGRES_PASSWORD=ponmlkjihgfedcba\nLOCAL_APP_PORT=5100\n{key}={value}\n"
    )
    path.chmod(0o600)
    with pytest.raises(RuntimeError, match=key):
        read_settings(path)


def test_ambient_provider_ports_do_not_override_configuration(monkeypatch):
    monkeypatch.setenv("LOCAL_POSTGRES_PORT", "1")
    monkeypatch.setenv("LOCAL_REDIS_PORT", "2")
    stack = Stack("local", settings={"POSTGRES_PASSWORD": "unused", "APP_PORT": "5100"})
    assert stack.process_env["LOCAL_POSTGRES_PORT"] == "55432"
    assert stack.process_env["LOCAL_REDIS_PORT"] == "56379"


def test_provider_stop_refuses_active_full_app():
    stack = Mock(env="local")
    stack.compose.return_value.stdout = "active-app"
    with pytest.raises(RuntimeError, match="active"):
        host.local_providers(stack, stop=True)
    assert stack.compose.call_count == 1


def test_provider_stop_targets_only_providers():
    stack = Mock(env="local")
    stack.compose.return_value.stdout = ""
    host.local_providers(stack, stop=True)
    assert stack.compose.call_args.args == ("stop", "postgres", "redis")


def test_arbitrary_urls_refused_without_docker(monkeypatch):
    inspect = Mock(side_effect=AssertionError("must not query Docker"))
    monkeypatch.setattr(ownership, "inspect_container", inspect)
    with pytest.raises(RuntimeError, match="Unverified"):
        ownership.verify_test_providers(
            {
                "TEST_DATABASE_URL": "postgresql://u:p@localhost/goalstats_test_arbitrary",
                "TEST_REDIS_URL": "redis://localhost/0",
                "TEST_DATABASE_DISPOSABLE": "1",
                "TEST_REDIS_DISPOSABLE": "1",
            }
        )
    inspect.assert_not_called()


@pytest.fixture
def owned_session(tmp_path, monkeypatch):
    # tmp_path may contain a /var -> /private/var symlink on macOS.
    root = tmp_path.resolve()
    monkeypatch.setattr(ownership, "ROOT", root)
    project = "goal-stats-service-test-" + "a" * 24
    token = "b" * 48
    directory = root / ".host-sessions" / project
    directory.mkdir(parents=True, mode=0o700)
    path = directory / "manifest.json"
    urls = {
        "TEST_DATABASE_URL": "postgresql+psycopg://goalstats:password@127.0.0.1:15432/goalstats_test_runtime",
        "TEST_REDIS_URL": "redis://:password@127.0.0.1:16379/0",
    }
    manifest = {
        "version": 1,
        "state": "active",
        "root": str(root),
        "project": project,
        "token": token,
        "pid": os.getpid(),
        "urls": urls,
        "containers": {"postgres": "pg-id", "redis": "redis-id"},
    }
    host.private_write(path, json.dumps(manifest))
    lock_path = directory / "owner.lock"
    host.private_write(lock_path, "")
    containers = {}
    for service, internal, port, target in (
        ("postgres", "5432/tcp", "15432", "/var/lib/postgresql/data"),
        ("redis", "6379/tcp", "16379", "/data"),
    ):
        containers[manifest["containers"][service]] = {
            "Id": manifest["containers"][service],
            "State": {"Running": True, "Health": {"Status": "healthy"}},
            "Config": {
                "Labels": {
                    "com.docker.compose.project": project,
                    "com.docker.compose.service": service,
                    ownership.SESSION_LABEL: token,
                },
                "Env": [
                    "POSTGRES_USER=goalstats",
                    "POSTGRES_PASSWORD=password",
                    "POSTGRES_DB=goalstats_test_runtime",
                ],
                "Cmd": [
                    "redis-server",
                    "--save",
                    "",
                    "--appendonly",
                    "no",
                    "--requirepass",
                    "password",
                ],
            },
            "NetworkSettings": {
                "Ports": {internal: [{"HostIp": "127.0.0.1", "HostPort": port}]},
                "Networks": {project + "_default": {}},
            },
            "HostConfig": {"Tmpfs": {target: ""}},
            "Mounts": [],
        }
    monkeypatch.setattr(ownership, "inspect_container", lambda cid: deepcopy(containers[cid]))
    with lock_path.open() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield {**urls, "TEST_SESSION_MANIFEST": str(path)}, manifest, containers, lock


def test_owned_host_session_accepts_exact_private_live_lease(owned_session):
    env, manifest, _, _ = owned_session
    assert ownership.verify_host_session(env) == manifest


@pytest.mark.parametrize(
    "change",
    [
        "url",
        "redis_url",
        "stopped",
        "unhealthy",
        "project",
        "service",
        "token",
        "identity",
        "binding",
        "public",
        "volume",
        "tmpfs",
        "network",
        "password",
        "redis_password",
        "lease",
        "manifest_mode",
        "manifest_state",
    ],
)
def test_owned_session_refuses_mismatch_before_connections(owned_session, change):
    env, manifest, containers, lock = owned_session
    pg = containers["pg-id"]
    match change:
        case "url":
            env["TEST_DATABASE_URL"] += "wrong"
        case "redis_url":
            env["TEST_REDIS_URL"] += "wrong"
        case "stopped":
            pg["State"]["Running"] = False
        case "unhealthy":
            pg["State"]["Health"]["Status"] = "unhealthy"
        case "project":
            pg["Config"]["Labels"]["com.docker.compose.project"] = "local"
        case "service":
            pg["Config"]["Labels"]["com.docker.compose.service"] = "app"
        case "token":
            pg["Config"]["Labels"][ownership.SESSION_LABEL] = "wrong"
        case "identity":
            pg["Id"] = "replacement"
        case "binding":
            pg["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"] = "5432"
        case "public":
            pg["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
        case "volume":
            pg["Mounts"] = [{"Type": "volume"}]
        case "tmpfs":
            pg["HostConfig"]["Tmpfs"] = {}
        case "network":
            pg["NetworkSettings"]["Networks"] = {"local": {}}
        case "password":
            pg["Config"]["Env"][1] = "POSTGRES_PASSWORD=wrong"
        case "redis_password":
            containers["redis-id"]["Config"]["Cmd"][-1] = "wrong"
        case "lease":
            fcntl.flock(lock, fcntl.LOCK_UN)
        case "manifest_mode":
            os.chmod(env["TEST_SESSION_MANIFEST"], 0o644)
        case "manifest_state":
            manifest["state"] = "stopped"
            from pathlib import Path

            Path(env["TEST_SESSION_MANIFEST"]).write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="Unverified"):
        ownership.verify_host_session(env)


def test_owned_session_discovered_without_environment_profile(owned_session):
    env, _, _, _ = owned_session
    values = ownership.owned_test_config({})
    assert values["TEST_DATABASE_URL"] == env["TEST_DATABASE_URL"]
    assert values["TEST_REDIS_URL"] == env["TEST_REDIS_URL"]
    assert values["TEST_DATABASE_DISPOSABLE"] == "1"


def test_ambiguous_sessions_refused_without_provider_inspection(owned_session, monkeypatch):
    from pathlib import Path

    env, _, _, _ = owned_session
    extra = Path(env["TEST_SESSION_MANIFEST"]).parent.parent / "other"
    extra.mkdir()
    (extra / "manifest.json").write_text("{}")
    inspect = Mock(side_effect=AssertionError("must not inspect"))
    monkeypatch.setattr(ownership, "inspect_container", inspect)
    with pytest.raises(RuntimeError, match="exactly one"):
        ownership.owned_test_config({})
    inspect.assert_not_called()
