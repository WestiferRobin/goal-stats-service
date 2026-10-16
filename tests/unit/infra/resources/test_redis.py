import logging
from unittest.mock import Mock

import pytest
from redis.exceptions import RedisError

from infra.resources.redis import RedisCache
from settings.environment import load_application


@pytest.mark.parametrize("payload", [b"{", b"[]", b"null", b"1", b"\xff"])
def test_generic_cache_treats_corrupt_data_as_miss(explicit_config, payload):
    cache = RedisCache(load_application(explicit_config).redis, Mock(spec=logging.Logger))
    cache.client = Mock()
    cache.client.get.return_value = payload
    assert cache.get("key") is None


def test_provider_failures_are_safe_and_optional(explicit_config):
    logger = Mock(spec=logging.Logger)
    cache = RedisCache(load_application(explicit_config).redis, logger)
    assert cache.get("x") is None
    assert cache.ready("x") is False
    cache.set("x", {}, 1)
    cache.delete("x")
    cache.client = Mock()
    for operation in [cache.client.get, cache.client.set, cache.client.delete]:
        operation.side_effect = RedisError("password=private")
    assert cache.get("x") is None
    cache.set("x", {}, 1)
    cache.delete("x")
    assert cache.ready("x") is False
    assert "private" not in str(logger.mock_calls)
