"""PostgreSQL machine derivation and validated runtime configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
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
        # Connection budgets and provider selection belong to this application.
        if url.query:
            raise ValueError
        return url.set(drivername="postgresql+psycopg")
    except (ArgumentError, ValueError, TypeError):
        raise ConfigurationError(
            "DATABASE_URL must be a PostgreSQL URL with host, username and database; "
            "query parameters are not supported."
        ) from None


@dataclass(frozen=True)
class DatabaseSettings:
    url: URL = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", database_url(self.url))
