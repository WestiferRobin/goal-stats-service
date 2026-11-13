"""Dependency-free configuration primitives; no file or process discovery."""

import ipaddress
from enum import StrEnum


class ConfigurationError(ValueError):
    """Safe configuration failure without rejected values."""


class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    TEST = "test"
    PRODUCTION = "production"


def port(value: str, key: str) -> int:
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise ConfigurationError(f"{key} must be an integer from 1 to 65535.")
    return int(value)


def boolean(value: str) -> bool:
    match value.strip().lower():
        case "true" | "1":
            return True
        case "false" | "0":
            return False
        case _:
            raise ConfigurationError("OPENAPI_ENABLED must be true, false, 1 or 0.")


def loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False
