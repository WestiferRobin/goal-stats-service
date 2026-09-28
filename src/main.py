"""Application factory; direct execution alone loads LOCAL machine configuration."""

import logging
import socket
import sys
from collections.abc import Mapping
from importlib.util import find_spec
from typing import cast

if __name__ == "__main__":
    if sys.version_info[:2] != (3, 12):
        sys.exit("Direct development requires Python 3.12. Run make setup and select .venv.")
    if any(
        find_spec(name) is None
        for name in (
            "flask",
            "flask_openapi3",
            "pydantic",
            "sqlalchemy",
            "psycopg",
            "redis",
            "flask_openapi3_swagger",
        )
    ):
        sys.exit(
            "Application dependencies are missing. Run make setup and select .venv/bin/python."
        )


from flask import Flask
from flask.logging import default_handler
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from exceptions.handlers import register_error_handlers, request_validation
from football.cli import register_commands
from infra.caches.action import ActionCache
from infra.caches.item import ItemCache
from infra.resources.db import Database, is_ready
from infra.resources.redis import RedisCache
from routers.action import create_actions_blueprint
from routers.football import create_football_blueprint
from routers.infra import create_health_blueprint
from routers.item import create_items_blueprint
from routers.openapi import create_docs_blueprint
from schemas.problem import ProblemDetailSchema
from services.action import ActionService
from services.football import FootballService
from services.item import ItemService
from settings.base import ConfigurationError
from settings.core import API_TITLE, API_VERSION, LOGGER_NAME
from settings.environment import Settings, load_application, load_local


def create_app(config: Settings | Mapping[str, str] | None = None) -> Flask:
    settings = config if isinstance(config, Settings) else load_application(config)
    app = OpenAPI(
        __name__,
        static_folder=None,
        info=Info(title=API_TITLE, version=API_VERSION),
        doc_ui=False,
        validation_error_status=400,
        validation_error_model=ProblemDetailSchema,
        validation_error_callback=request_validation,
    )
    app.config.update(
        APP_ENV=settings.core.app_env, TESTING=settings.core.app_env == "test", DEBUG=False
    )
    app.logger = logging.Logger(LOGGER_NAME, level=settings.core.log_level)
    app.logger.addHandler(default_handler)
    database = Database(settings.database)
    cache = RedisCache(settings.redis, app.logger)
    item_cache = ItemCache(cache, settings.redis.cache_key_prefix, settings.redis.cache_ttl_seconds)
    action_cache = ActionCache(
        cache, settings.redis.cache_key_prefix, settings.redis.cache_ttl_seconds
    )
    app.extensions["goalstats_settings"] = settings
    app.extensions["goalstats_database"] = database
    app.extensions["goalstats_cache"] = cache
    app.extensions["goalstats_item_cache"] = item_cache
    app.extensions["goalstats_action_cache"] = action_cache

    item_service = ItemService(database, item_cache)
    action_service = ActionService(database, action_cache)
    if settings.redis.url is None:
        app.logger.warning("Redis is unconfigured; database fallback is available")
    app.register_api(create_health_blueprint(database, cache, settings.redis.cache_key_prefix))
    app.register_api(create_items_blueprint(item_service))
    app.register_api(create_actions_blueprint(action_service))
    app.register_api(create_football_blueprint(FootballService(database)))
    register_commands(app, database)
    register_error_handlers(app)
    if settings.core.openapi_enabled:
        app.register_blueprint(create_docs_blueprint(app))
    return app


def _check_app_port(port: int) -> None:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise ConfigurationError(
                f"LOCAL application port {port} is unavailable. Stop the other application "
                "or choose HOST_APP_PORT."
            ) from None


def _diagnose_providers(app: Flask) -> None:
    """Bounded reads only. Schema readiness and cache fallback retain their policies."""
    database = cast(Database, app.extensions["goalstats_database"])
    cache = cast(RedisCache, app.extensions["goalstats_cache"])
    settings = cast(Settings, app.extensions["goalstats_settings"])
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database.dispose()
        raise ConfigurationError(
            "LOCAL PostgreSQL is unavailable. Run make providers ENV=local "
            "and verify the existing configuration."
        ) from None
    if not is_ready(database):
        app.logger.warning(
            "LOCAL database is not ready. If migrations are pending, run make migrate ENV=local."
        )
    if not cache.ready(settings.redis.cache_key_prefix):
        app.logger.warning(
            "LOCAL Redis is unavailable; database fallback remains active. "
            "Run make providers ENV=local."
        )


def development_main() -> None:
    settings = load_local()
    _check_app_port(settings.core.host_app_port)
    app = create_app(settings)
    _diagnose_providers(app)
    app.run(
        host="127.0.0.1",
        port=settings.core.host_app_port,
        debug=False,
        use_debugger=False,
        use_reloader=False,
        load_dotenv=False,
    )


if __name__ == "__main__":
    try:
        development_main()
    except ConfigurationError as exc:
        sys.exit(str(exc))
