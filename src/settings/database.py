"""PostgreSQL machine derivation and validated runtime configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from settings.base import ConfigurationError, ExecutionContext

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

DATABASE = "goal_stats_service"
PORT_DEFAULTS = {"LOCAL_POSTGRES_PORT": "55432"}
PASSWORD_KEYS = frozenset({"POSTGRES_PASSWORD", "DEV_POSTGRES_PASSWORD"})


def credentials(values: Mapping[str, str]) -> None:
    for key in PASSWORD_KEYS:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,128}", values.get(key, "")):
            raise ConfigurationError(
                f"{key} must be 16–128 URL-safe characters; preserve existing credentials."
            )


def derive_database_url(values: Mapping[str, str], mode: str, *, context: ExecutionContext) -> str:
    if context not in {"host", "container"}:
        raise ConfigurationError("Execution context must be host or container.")
    if mode not in {"local", "dev"} or (context == "host" and mode != "local"):
        raise ConfigurationError(
            "Machine database configuration supports LOCAL/DEV; host is LOCAL."
        )
    password = values["POSTGRES_PASSWORD" if mode == "local" else "DEV_POSTGRES_PASSWORD"]
    address = "127.0.0.1:" + values["LOCAL_POSTGRES_PORT"] if context == "host" else "postgres:5432"
    return f"postgresql+psycopg://goalstats:{password}@{address}/{DATABASE}_{mode}"


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


def validate_prototype_target(value: URL) -> None:
    """Retain no-option machine/test imports, without authorizing implicit cloud writes."""
    url = database_url(value)
    if url.host not in {"127.0.0.1", "localhost", "postgres"} or not (
        url.database in {"goal_stats_service_local", "goal_stats_service_dev"}
        or (url.database or "").startswith("goalstats_test_")
    ):
        raise ConfigurationError(
            "Prototype import is restricted to established local/test targets."
        )
