import pytest

from settings.base import ConfigurationError
from settings.environment import load_application


@pytest.mark.parametrize(
    "key,value",
    [
        ("REDIS_URL", "http://private@host/0"),
        ("REDIS_URL", "redis://host/abc"),
        ("REDIS_URL", "redis://host/0?socket_timeout=999"),
        ("REDIS_URL", "redis://host:99999/0"),
        ("CACHE_KEY_PREFIX", "bad prefix"),
        ("CACHE_KEY_PREFIX", ""),
        ("CACHE_TTL_SECONDS", "0"),
        ("CACHE_TTL_SECONDS", "x"),
        ("CACHE_TTL_SECONDS", "86401"),
    ],
)
def test_cache_settings_fail_safely(explicit_config, key, value):
    with pytest.raises(ConfigurationError) as error:
        load_application({**explicit_config, key: value})
    assert key in str(error.value)
    assert "private" not in str(error.value)


def test_cache_settings_defaults_and_explicit_isolation(explicit_config, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "invalid")
    settings = load_application(explicit_config)
    assert settings.redis.url is None
    assert settings.redis.cache_key_prefix == "goal-stats-service:test:v1"
    assert settings.redis.cache_ttl_seconds == 300
    settings = load_application({**explicit_config, "REDIS_URL": "redis://:private@localhost/0"})
    assert "private" not in repr(settings)
