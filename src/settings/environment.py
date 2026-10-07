"""Explicit private sources and typed composition; never a global settings singleton."""

import os
import re
import socket
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from settings.base import ConfigurationError, ExecutionContext, boolean, port
from settings.core import POLICY_DEFAULTS as CORE_POLICY
from settings.core import PORT_DEFAULTS as CORE_PORTS
from settings.core import SERVICE as SERVICE
from settings.core import CoreSettings, environment, log_level
from settings.database import DATABASE as DATABASE
from settings.database import (
    PASSWORD_KEYS,
    DatabaseSettings,
    credentials,
    database_url,
    derive_database_url,
)
from settings.database import PORT_DEFAULTS as DB_PORTS
from settings.redis import POLICY_DEFAULTS as REDIS_POLICY
from settings.redis import PORT_DEFAULTS as REDIS_PORTS
from settings.redis import RedisSettings, cache_ttl, default_prefix, derive_redis_url

# These mappings are views of concern-owned defaults, also used by stdlib tooling.
POLICY_DEFAULTS = {**CORE_POLICY, **REDIS_POLICY}
PORT_DEFAULTS = {**CORE_PORTS, **DB_PORTS, **REDIS_PORTS}
LOCAL_KEYS = frozenset(PORT_DEFAULTS) | frozenset(POLICY_DEFAULTS) | PASSWORD_KEYS
LOCAL_FILE = Path(__file__).resolve().parents[2] / ".env.local"
DIRECT_KEYS = frozenset(
    {
        "APP_ENV",
        "DATABASE_URL",
        "REDIS_URL",
        "CACHE_KEY_PREFIX",
        "CACHE_TTL_SECONDS",
        "LOG_LEVEL",
        "OPENAPI_ENABLED",
        "HOST_APP_PORT",
        "FLASK_DEBUG",
    }
)


def read_private(path: Path, keys: frozenset[str]) -> dict[str, str]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ConfigurationError(
                    f"{path.name}: configuration must be a private regular file owned by this user."
                )
            content = stream.read()
    except FileNotFoundError:
        kind = "LOCAL" if path.name == ".env.local" else "TEST"
        raise ConfigurationError(
            f"{path.name}: {kind} configuration is missing. Run make setup."
        ) from None
    except (OSError, UnicodeError):
        raise ConfigurationError(
            f"{path.name}: cannot read private configuration; symlinks are forbidden."
        ) from None
    result: dict[str, str] = {}
    for number, line in enumerate(content.splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key not in keys or key in result or "\x00" in value:
            raise ConfigurationError(
                f"{path.name}:{number}: configuration requires unique supported KEY=value lines."
            )
        result[key] = value
    return result


def policy(values: Mapping[str, str]) -> dict[str, str]:
    if set(values) - POLICY_DEFAULTS.keys():
        raise ConfigurationError(
            "TEST policy contains unsupported keys; provider configuration is forbidden."
        )
    result = {**POLICY_DEFAULTS, **values}
    result["LOG_LEVEL"] = log_level(result["LOG_LEVEL"])
    boolean(result["OPENAPI_ENABLED"])
    cache_ttl(result["CACHE_TTL_SECONDS"])
    return result


def test_policy(root: Path) -> dict[str, str]:
    path = root / ".env.test"
    values = (
        read_private(path, frozenset(POLICY_DEFAULTS)) if path.exists() or path.is_symlink() else {}
    )
    try:
        return policy(values)
    except ConfigurationError as exc:
        raise ConfigurationError(f"{path.name}: {exc}") from None


def machine(values: Mapping[str, str]) -> dict[str, str]:
    if set(values) - LOCAL_KEYS:
        raise ConfigurationError(
            "Unsupported LOCAL machine key; run make setup to migrate legacy configuration."
        )
    result = {
        **PORT_DEFAULTS,
        **policy({k: v for k, v in values.items() if k in POLICY_DEFAULTS}),
        **values,
    }
    credentials(result)
    for key in PORT_DEFAULTS:
        port(result[key], key)
    if len({int(result[k]) for k in PORT_DEFAULTS}) != len(PORT_DEFAULTS):
        raise ConfigurationError("Machine app/provider ports must be distinct.")
    return result


def load_machine(path: Path) -> dict[str, str]:
    values = read_private(path, LOCAL_KEYS)
    try:
        return machine(values)
    except ConfigurationError as exc:
        raise ConfigurationError(f"{path.name}: {exc}") from None


def application(values: Mapping[str, str], mode: str, *, host: bool = False) -> dict[str, str]:
    if mode not in {"local", "dev"} or (host and mode != "local"):
        raise ConfigurationError(
            "Machine configuration supports LOCAL/DEV only; host execution is LOCAL."
        )
    context: ExecutionContext = "host" if host else "container"
    return {
        **policy({k: v for k, v in values.items() if k in POLICY_DEFAULTS}),
        "APP_ENV": mode,
        "DATABASE_URL": derive_database_url(values, mode, context=context),
        "REDIS_URL": derive_redis_url(values, context=context),
        "CACHE_KEY_PREFIX": default_prefix(mode),
        "HOST_APP_PORT": values["HOST_APP_PORT"],
        "FLASK_DEBUG": "0",
    }


@dataclass(frozen=True)
class Settings:
    core: CoreSettings
    database: DatabaseSettings
    redis: RedisSettings

    def __post_init__(self) -> None:
        if not (
            isinstance(self.core, CoreSettings)
            and isinstance(self.database, DatabaseSettings)
            and isinstance(self.redis, RedisSettings)
        ):
            raise ConfigurationError("Settings require validated core, database and Redis groups.")


def load_application(values: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if values is None else values
    mode = environment(source.get("APP_ENV", "local"))
    return Settings(
        CoreSettings(
            mode,
            log_level(source.get("LOG_LEVEL", CORE_POLICY["LOG_LEVEL"])),
            boolean(source.get("OPENAPI_ENABLED", "false")),
            port(source.get("HOST_APP_PORT", "5100"), "HOST_APP_PORT"),
        ),
        DatabaseSettings(database_url(source.get("DATABASE_URL", ""))),
        RedisSettings(
            source.get("REDIS_URL") or None,
            source.get("CACHE_KEY_PREFIX", default_prefix(mode)),
            cache_ttl(source.get("CACHE_TTL_SECONDS", REDIS_POLICY["CACHE_TTL_SECONDS"])),
        ),
    )


# The public local contract is intentionally separate from retained private DEV tooling.
DEVELOPMENT_DEFAULTS = {
    "APP_PORT": "5100",
    "POSTGRES_PORT": "55432",
    "REDIS_PORT": "56379",
    **POLICY_DEFAULTS,
    "API_FOOTBALL_KEY": "",
}
DEVELOPMENT_KEYS = frozenset(DEVELOPMENT_DEFAULTS) | {"POSTGRES_PASSWORD"}


def local_values(path: Path | None = None) -> dict[str, str]:
    values = {**DEVELOPMENT_DEFAULTS, **read_private(path or LOCAL_FILE, DEVELOPMENT_KEYS)}
    # Literal, unquoted values only: identical interpretation in Python and Compose.
    for key, value in values.items():
        if not re.fullmatch(r"[a-zA-Z0-9_./:@+\-]*", value):
            raise ConfigurationError(f"{key} must be an unquoted literal without whitespace.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", values.get("POSTGRES_PASSWORD", "")):
        raise ConfigurationError("POSTGRES_PASSWORD must be nonempty and URL-safe; preserve it.")
    for key in ("APP_PORT", "POSTGRES_PORT", "REDIS_PORT"):
        port(values[key], key)
    if len({int(values[k]) for k in ("APP_PORT", "POSTGRES_PORT", "REDIS_PORT")}) != 3:
        raise ConfigurationError("Application and provider ports must be distinct.")
    policy({key: values[key] for key in POLICY_DEFAULTS})
    return values


def local_runtime(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    if "APP_ENV" in source and source["APP_ENV"] != "local":
        raise ConfigurationError("Conflicting inherited APP_ENV; use local development settings.")
    values = local_values()
    runtime = {
        **values,
        "APP_ENV": "local",
        "DATABASE_URL": (
            "postgresql+psycopg://goalstats:"
            + values["POSTGRES_PASSWORD"]
            + "@127.0.0.1:"
            + values["POSTGRES_PORT"]
            + "/goal_stats_service_local"
        ),
        "REDIS_URL": "redis://127.0.0.1:" + values["REDIS_PORT"] + "/0",
        "CACHE_KEY_PREFIX": default_prefix("local"),
        "HOST_APP_PORT": values["APP_PORT"],
        "FLASK_DEBUG": "0",
    }
    for key, value in runtime.items():
        if key in source and source[key] != value:
            raise ConfigurationError(f"Conflicting inherited {key}; use .env.local instead.")
    return runtime


def check_local_port() -> None:
    value = int(local_runtime()["HOST_APP_PORT"])
    with socket.socket() as probe:
        # Permit an immediate restart after closed connections, but never a live listener.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", value))
        except OSError:
            raise ConfigurationError(
                f"Application port {value} is occupied. "
                "Stop host Flask with Ctrl-C or IDE Stop, then retry. "
                "If another application owns the port, stop it yourself or change APP_PORT."
            ) from None


def load_local(environ: Mapping[str, str] | None = None) -> Settings:
    return load_application(local_runtime(environ))
