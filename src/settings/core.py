"""Core runtime settings and static service identity."""

from dataclasses import dataclass, field

from settings.base import ConfigurationError, Environment, port

SERVICE = "goal-stats-service"
API_TITLE = "GoalStats Monolith API"
API_VERSION = "v1"
LOGGER_NAME = "goal_stats_service"
POLICY_DEFAULTS = {"LOG_LEVEL": "INFO", "OPENAPI_ENABLED": "true"}


def log_level(value: str) -> str:
    level = value.strip().upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL.")
    return level


def environment(value: str) -> Environment:
    try:
        return Environment(value.strip().lower())
    except ValueError:
        raise ConfigurationError("APP_ENV must be local, dev, test or production.") from None


@dataclass(frozen=True)
class CoreSettings:
    app_env: Environment = Environment.LOCAL
    log_level: str = POLICY_DEFAULTS["LOG_LEVEL"]
    openapi_enabled: bool = False
    host_app_port: int = 5100
    service_api_token: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_env", environment(self.app_env))
        object.__setattr__(self, "log_level", log_level(self.log_level))
        if not isinstance(self.openapi_enabled, bool):
            raise ConfigurationError("OPENAPI_ENABLED must be a boolean.")
        port(str(self.host_app_port), "HOST_APP_PORT")
        if self.app_env == Environment.PRODUCTION and (
            not isinstance(self.service_api_token, str)
            or len(self.service_api_token) < 32
            or not self.service_api_token.isascii()
            or not all(33 <= ord(c) <= 126 for c in self.service_api_token)
        ):
            raise ConfigurationError(
                "SERVICE_API_TOKEN must contain at least 32 printable ASCII characters "
                "without whitespace in production."
            )
