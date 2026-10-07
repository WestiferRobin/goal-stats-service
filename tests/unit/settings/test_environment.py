import os

import pytest

from settings.base import ConfigurationError
from settings.environment import LOCAL_KEYS, application, load_application, machine, read_private
from settings.environment import test_policy as load_test_policy


def test_context_changes_address_not_identity():
    values = machine(
        {"POSTGRES_PASSWORD": "abcdefghijklmnop", "DEV_POSTGRES_PASSWORD": "ponmlkjihgfedcba"}
    )
    host = application(values, "local", host=True)
    docker = application(values, "local")
    assert (
        host["DATABASE_URL"].replace("127.0.0.1:55432", "postgres:5432") == docker["DATABASE_URL"]
    )
    assert host["REDIS_URL"].replace("127.0.0.1:56379", "redis:6379") == docker["REDIS_URL"]
    assert host["CACHE_KEY_PREFIX"] == docker["CACHE_KEY_PREFIX"]
    assert "ponmlkjihgfedcba" in application(values, "dev")["DATABASE_URL"]
    for mode in ("dev", "test"):
        with pytest.raises(ConfigurationError):
            application(values, mode, host=True)


@pytest.mark.parametrize(
    "content", ["LOG_LEVEL=INFO\nLOG_LEVEL=DEBUG", "UNKNOWN=private", "broken"]
)
def test_active_private_parser_rejects_lines(tmp_path, content):
    path = tmp_path / ".env.local"
    path.write_text(content)
    path.chmod(0o600)
    with pytest.raises(ConfigurationError, match=r".env.local:\d"):
        read_private(path, LOCAL_KEYS)


def test_policy_does_not_authorize_providers(tmp_path):
    assert load_test_policy(tmp_path)["OPENAPI_ENABLED"] == "true"
    path = tmp_path / ".env.test"
    path.write_text("DATABASE_URL=private")
    path.chmod(0o600)
    with pytest.raises(ConfigurationError):
        load_test_policy(tmp_path)


def test_typed_factory_bypasses_loading(monkeypatch):
    import main

    settings = load_application({"DATABASE_URL": "postgresql://u:p@localhost/unit"})
    before = dict(os.environ)
    monkeypatch.setattr(main, "load_application", lambda _: pytest.fail("reparsed settings"))
    app = main.create_app(settings)
    assert app.extensions["goalstats_settings"] is settings
    assert dict(os.environ) == before
    app.extensions["goalstats_database"].dispose()


def test_current_example_and_container_identity(tmp_path, monkeypatch):
    from pathlib import Path

    from settings import environment as host

    path = tmp_path / ".env.local"
    path.write_bytes((Path(__file__).resolve().parents[3] / ".env.example").read_bytes())
    path.chmod(0o600)
    monkeypatch.setattr(host, "LOCAL_FILE", path)
    values = host.local_values()
    config = host.load_local({})
    assert config.core.host_app_port == 5100
    assert config.database.url.host == "127.0.0.1"
    assert config.database.url.port == 55432
    assert config.database.url.database == "goal_stats_service_local"
    assert config.database.url.username == "goalstats"
    assert config.database.url.password == values["POSTGRES_PASSWORD"]
    assert config.redis.url == "redis://127.0.0.1:56379/0"
    assert config.redis.cache_key_prefix == "goal-stats-service:local:v1"


@pytest.mark.parametrize("value", ["$(touch secret)", "${HOME}", '"secret"', "a b", "a#b", "a@b"])
def test_public_password_rejects_ambiguous_values_without_disclosure(tmp_path, value):
    from settings.environment import local_values

    path = tmp_path / ".env.local"
    path.write_text("POSTGRES_PASSWORD=" + value + "\n")
    path.chmod(0o600)
    with pytest.raises(ConfigurationError) as error:
        local_values(path)
    assert value not in str(error.value)


@pytest.mark.parametrize("key", ["APP_PORT", "POSTGRES_PORT", "REDIS_PORT"])
def test_public_ports_validate(tmp_path, key):
    from settings.environment import local_values

    path = tmp_path / ".env.local"
    path.write_text("POSTGRES_PASSWORD=safe-password\n" + key + "=65536\n")
    path.chmod(0o600)
    with pytest.raises(ConfigurationError, match=key):
        local_values(path)
