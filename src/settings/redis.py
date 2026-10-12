"""Optional Redis endpoint and cache policy."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from settings.base import ConfigurationError
from settings.core import SERVICE

POLICY_DEFAULTS = {"CACHE_TTL_SECONDS": "300"}


def default_prefix(mode: str) -> str:
    return f"{SERVICE}:{mode}:v1"


def redis_url(value: str) -> str | None:
    if not value:
        return None
    try:
        url = urlsplit(value)
        if url.scheme not in {"redis", "rediss"} or not url.hostname or url.query or url.fragment:
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        if url.path not in {"", "/"} and not re.fullmatch(r"/[0-9]+", url.path):
            raise ValueError
        return value
    except ValueError:
        raise ConfigurationError(
            "REDIS_URL must be a redis/rediss URL without query parameters."
        ) from None


def cache_ttl(value: str) -> int:
    try:
        result = int(value)
        if not 1 <= result <= 86400:
            raise ValueError
        return result
    except ValueError:
        raise ConfigurationError("CACHE_TTL_SECONDS must be an integer from 1 to 86400.") from None


def cache_prefix(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9:_-]{0,99}", value):
        raise ConfigurationError("CACHE_KEY_PREFIX must be 1–100 safe namespace characters.")
    return value


@dataclass(frozen=True)
class RedisSettings:
    url: str | None = field(default=None, repr=False)
    cache_key_prefix: str = default_prefix("local")
    cache_ttl_seconds: int = int(POLICY_DEFAULTS["CACHE_TTL_SECONDS"])

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", redis_url(self.url or ""))
        cache_prefix(self.cache_key_prefix)
        cache_ttl(str(self.cache_ttl_seconds))
