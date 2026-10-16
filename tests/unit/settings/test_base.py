import pytest

from settings.base import ConfigurationError, boolean
from settings.environment import load_application

URL = "postgresql://service:private_password@localhost/goalstats_test_config"


def test_explicit_settings_ignore_developer_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///developer.db")
    monkeypatch.setenv("OPENAPI_ENABLED", "invalid")
    result = load_application({"DATABASE_URL": URL})
    assert result.core.app_env == "local"
    assert result.core.openapi_enabled is False
    assert result.database.url.drivername == "postgresql+psycopg"
    assert "private_password" not in repr(result)


def test_environment_is_used_only_when_no_mapping_is_supplied(monkeypatch):
    monkeypatch.setenv("APP_ENV", "DEV")
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("OPENAPI_ENABLED", "true")
    settings = load_application()
    assert (settings.core.app_env, settings.core.log_level, settings.core.openapi_enabled) == (
        "dev",
        "WARNING",
        True,
    )
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_application({})


@pytest.mark.parametrize("env", ["local", "dev", "test"])
def test_supported_environments(env):
    assert load_application({"APP_ENV": env, "DATABASE_URL": URL}).core.app_env == env


@pytest.mark.parametrize(
    "value, expected", [("true", True), ("false", False), ("1", True), ("0", False)]
)
def test_boolean_contract(value, expected):
    assert boolean(value) is expected


@pytest.mark.parametrize(
    "key,value", [("APP_ENV", "prod"), ("LOG_LEVEL", "verbose"), ("OPENAPI_ENABLED", "yes")]
)
def test_invalid_settings_fail_with_safe_field_name(key, value):
    with pytest.raises(ConfigurationError, match=key):
        load_application({"DATABASE_URL": URL, key: value})


@pytest.mark.parametrize(
    "host,expected",
    [
        ("localhost", True),
        ("127.0.0.2", True),
        ("::1", True),
        ("192.0.2.1", False),
        (None, False),
        ("not-an-address", False),
    ],
)
def test_loopback_classification_does_not_resolve_hostnames(host, expected):
    """Classify literal loopbacks and reject arbitrary hosts without DNS lookups."""
    from settings.base import loopback

    assert loopback(host) is expected
