"""Validated PostgreSQL runtime configuration and import authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from settings.base import ConfigurationError

if TYPE_CHECKING:
    from sqlalchemy.engine import URL


def database_url(value: str | URL) -> URL:
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError

    try:
        url = make_url(value)
        if url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError
        if not url.host or not url.username or not url.database:
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        if any(c in url.host for c in ",/ "):
            raise ValueError
        # Only TLS options are caller-controlled; never allow host/service overrides.
        query = url.query
        if set(query) - {"sslmode", "sslrootcert", "sslcert", "sslkey"}:
            raise ValueError
        if any(not isinstance(v, str) or not v or "\x00" in v for v in query.values()):
            raise ValueError
        mode = query.get("sslmode")
        if query and mode not in {"disable", "require", "verify-ca", "verify-full"}:
            raise ValueError
        root = query.get("sslrootcert")
        if mode in {"verify-ca", "verify-full"} and not root:
            raise ValueError
        if mode == "disable" and set(query) != {"sslmode"}:
            raise ValueError
        if bool(query.get("sslcert")) != bool(query.get("sslkey")):
            raise ValueError
        for key in ("sslrootcert", "sslcert", "sslkey"):
            tls_value = query.get(key)
            if tls_value is not None:
                if tls_value == "system" and key == "sslrootcert" and mode == "verify-full":
                    continue
                if not isinstance(tls_value, str) or not PurePosixPath(tls_value).is_absolute():
                    raise ValueError
        return url.set(drivername="postgresql+psycopg")
    except (ArgumentError, ValueError, TypeError):
        raise ConfigurationError(
            "DATABASE_URL must be a PostgreSQL URL with host, username and database; "
            "only explicit sslmode and absolute sslrootcert/sslcert/sslkey TLS settings are "
            "supported. Certificate verification requires sslrootcert; client cert/key must pair."
        ) from None


@dataclass(frozen=True)
class DatabaseSettings:
    url: URL = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", database_url(self.url))


@dataclass(frozen=True)
class ImportTarget:
    """Explicit authorization, independent of application environment labels."""

    target: str
    expect_host: str
    expect_database: str
    confirm_production: bool = False

    def validate(self, value: URL) -> None:
        url = database_url(value)
        if self.target not in {"local", "cloud", "test"}:
            raise ConfigurationError(
                "An explicit import target is required: local, cloud, or test."
            )
        if not self.expect_host or not self.expect_database:
            raise ConfigurationError("--expect-host and --expect-database are required.")
        if url.host != self.expect_host:
            raise ConfigurationError("Database hostname does not match --expect-host.")
        if url.database != self.expect_database:
            raise ConfigurationError("Database name does not match --expect-database.")
        if self.target == "cloud":
            if not self.confirm_production:
                raise ConfigurationError("Cloud imports and dry-runs require --confirm-production.")
            if url.query.get("sslmode") != "verify-full" or not url.query.get("sslrootcert"):
                raise ConfigurationError(
                    "Cloud imports require sslmode=verify-full and sslrootcert."
                )
        elif self.target == "local":
            expected_port = {"127.0.0.1": 55432, "postgres": 5432}.get(url.host or "")
            if (
                url.database != "goal_stats_service_local"
                or url.username != "goalstats"
                or expected_port is None
                or (url.port or 5432) != expected_port
            ):
                raise ConfigurationError(
                    "Local target requires the established local host/port, "
                    "goal_stats_service_local database and goalstats user."
                )
        elif url.host not in {"127.0.0.1", "localhost", "postgres"} or not (
            url.database or ""
        ).startswith("goalstats_test_"):
            raise ConfigurationError("Test target requires a local goalstats_test_* database.")
