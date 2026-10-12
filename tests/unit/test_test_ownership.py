"""Host attestations and in-container receipts fail closed before provider access."""

from copy import deepcopy

import pytest
from test_ownership import validate_receipt
from test_resources import validate_project, validate_provider


@pytest.fixture
def receipt():
    project = "goal-stats-service-test-" + "a" * 24
    database = (
        "postgresql+psycopg://goalstats:test-" + "b" * 48 + "@postgres:5432/goalstats_test_runtime"
    )
    data = {
        "version": 2,
        "project": project,
        "hostname": project + "-runner",
        "providers": {"postgres": "c" * 64, "redis": "d" * 64},
        "TEST_DATABASE_URL": database,
        "TEST_REDIS_URL": "redis://redis:6379/0",
    }
    env = {
        "TEST_PROJECT": project,
        "APP_ENV": "test",
        "DATABASE_URL": database,
        "REDIS_URL": data["TEST_REDIS_URL"],
        "TEST_DATABASE_URL": database,
        "TEST_REDIS_URL": data["TEST_REDIS_URL"],
    }
    return data, env


def test_valid_receipt(receipt):
    data, env = receipt
    validate_receipt(data, env, data["hostname"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("project", "goalstats-service-local"),
        ("hostname", "another-container"),
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
        validate_receipt(data, env, env["TEST_PROJECT"] + "-runner")
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "field",
    ["TEST_PROJECT", "APP_ENV", "DATABASE_URL", "REDIS_URL", "TEST_DATABASE_URL", "TEST_REDIS_URL"],
)
def test_conflicting_environment(receipt, field):
    data, env = receipt
    env[field] = "conflicting-secret"
    with pytest.raises(RuntimeError, match="Invalid owned"):
        validate_receipt(data, env, data["hostname"])


@pytest.mark.parametrize("data", [{}, None, {"version": 2}])
def test_missing_or_malformed_receipt(data):
    with pytest.raises(RuntimeError):
        validate_receipt(data, {}, "unowned")


def test_wrong_container(receipt):
    data, env = receipt
    with pytest.raises(RuntimeError):
        validate_receipt(data, env, "other-container")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://goalstats:test-"
        + "b" * 48
        + "@localhost:5432/goalstats_test_runtime",
        "postgresql+psycopg://goalstats:test-"
        + "b" * 48
        + "@postgres:5432/goal_stats_service_local",
        "postgresql+psycopg://goalstats:development-password@postgres:5432/goalstats_test_runtime",
    ],
)
def test_matching_environment_cannot_authorize_arbitrary_targets(receipt, url):
    data, env = receipt
    data["TEST_DATABASE_URL"] = env["TEST_DATABASE_URL"] = env["DATABASE_URL"] = url
    with pytest.raises(RuntimeError):
        validate_receipt(data, env, data["hostname"])


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
            },
            "Env": [
                "POSTGRES_USER=goalstats",
                "POSTGRES_DB=goalstats_test_runtime",
                "POSTGRES_PASSWORD=test-" + "b" * 48,
            ],
        },
        "State": {"Running": True, "Health": {"Status": "healthy"}},
        "HostConfig": {"Tmpfs": {"/var/lib/postgresql/data": ""}},
        "Mounts": [],
        "NetworkSettings": {"Ports": {"5432/tcp": None}, "Networks": {project + "_default": {}}},
    }


def test_provider_verified_before_receipt(provider, receipt):
    validate_provider(provider, receipt[0]["project"], "postgres", "test-" + "b" * 48)


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
        validate_provider(c, receipt[0]["project"], "postgres", "test-" + "b" * 48)


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
def test_docker_requires_readable_valid_receipt(tmp_path, monkeypatch, content):
    import test_ownership as ownership

    marker = tmp_path / "dockerenv"
    marker.touch()
    receipt_path = tmp_path / "owned-test.json"
    if content is not None:
        receipt_path.write_text(content)
    monkeypatch.setattr(
        ownership, "Path", lambda value: marker if value == "/.dockerenv" else receipt_path
    )
    with pytest.raises(RuntimeError, match="Unverified TEST"):
        ownership.verify_test_providers({})


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"TEST_SESSION_MANIFEST": "/old/manifest.json"},
        {"TEST_DATABASE_URL": "postgresql://private@localhost/dev"},
    ],
)
def test_host_provider_configuration_is_refused(tmp_path, monkeypatch, env):
    import test_ownership as ownership

    monkeypatch.setattr(ownership, "Path", lambda value: tmp_path / "absent")
    with pytest.raises(RuntimeError, match="use make test") as error:
        ownership.owned_test_config(env)
    assert "private@" not in str(error.value)
