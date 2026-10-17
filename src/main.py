"""Application factory; direct execution alone loads LOCAL machine configuration."""

import logging
import os
import socket
import sys
from collections.abc import Mapping
from hmac import compare_digest
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


from flask import Flask, Response, request
from flask.logging import default_handler
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from exceptions.handlers import problem, register_error_handlers, request_validation
from football.cli import register_commands
from infra.repositories.competition import CompetitionRepository
from infra.repositories.match import MatchRepository
from infra.repositories.prediction import PredictionRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from infra.resources.db import Database, is_ready
from infra.resources.redis import RedisCache
from routers.competition import create_competition_blueprint
from routers.infra import create_health_blueprint
from routers.match import create_match_blueprint
from routers.openapi import create_docs_blueprint
from routers.prediction import create_predictions_blueprint
from routers.scenario import create_scenarios_blueprint
from routers.team import create_team_blueprint
from schemas.problem import ProblemDetailSchema
from services.competition import CompetitionService
from services.match import MatchService
from services.prediction import PredictionService
from services.scenario import ScenarioService
from services.team import TeamService
from settings.base import ConfigurationError, Environment
from settings.core import API_TITLE, API_VERSION, LOGGER_NAME
from settings.environment import Settings, load_application, load_local, local_runtime


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
    if settings.core.app_env == Environment.PRODUCTION:

        @app.before_request
        def authenticate_mutation() -> Response | None:
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return None
            expected = ("Bearer " + settings.core.service_api_token).encode("ascii")
            supplied = request.headers.get("Authorization", "").encode("utf-8")
            if not compare_digest(supplied, expected):
                response = problem(401, "Valid service authentication is required.")
                response.headers["WWW-Authenticate"] = "Bearer"
                return response
            return None

    app.logger = logging.Logger(LOGGER_NAME, level=settings.core.log_level)
    app.logger.addHandler(default_handler)
    database = Database(settings.database)
    cache = RedisCache(settings.redis, app.logger)
    app.extensions["goalstats_settings"] = settings
    app.extensions["goalstats_database"] = database
    app.extensions["goalstats_cache"] = cache

    team_repo = TeamRepository(database)
    competition_repo = CompetitionRepository(database)
    match_repo = MatchRepository(database)
    scenario_repo = ScenarioRepository(database)
    prediction_repo = PredictionRepository(database)
    team_service = TeamService(repo=team_repo)
    competition_service = CompetitionService(repo=competition_repo, team_service=team_service)
    match_service = MatchService(repo=match_repo, team_service=team_service)
    scenario_service = ScenarioService(
        repo=scenario_repo, team_service=team_service, match_service=match_service
    )
    prediction_service = PredictionService(
        repo=prediction_repo, scenario_service=scenario_service, team_service=team_service
    )

    if settings.redis.url is None:
        app.logger.warning("Redis is unconfigured; database fallback is available")
    app.register_api(create_health_blueprint(database, cache, settings.redis.cache_key_prefix))
    app.register_api(create_team_blueprint(team_service))
    app.register_api(create_competition_blueprint(competition_service))
    app.register_api(create_match_blueprint(match_service))
    app.register_api(create_scenarios_blueprint(scenario_service))
    app.register_api(create_predictions_blueprint(prediction_service))
    register_commands(app, database)
    register_error_handlers(app)
    if settings.core.openapi_enabled:
        app.register_blueprint(create_docs_blueprint(app))
    return app


def _check_app_port(port: int) -> None:
    with socket.socket() as probe:
        # Permit an immediate restart after closed connections, but never a live listener.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise ConfigurationError(
                f"LOCAL application port {port} is unavailable. Stop the other application "
                "or change APP_PORT."
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
            "LOCAL PostgreSQL is unavailable. Run make infra and verify the existing configuration."
        ) from None
    if not is_ready(database):
        app.logger.warning(
            "LOCAL database is not ready. If migrations are pending, run make run or make deploy."
        )
    if not cache.ready(settings.redis.cache_key_prefix):
        app.logger.warning(
            "LOCAL Redis is unavailable; database fallback remains active. Run make infra."
        )


def development_main() -> None:
    settings = load_local()
    os.environ["API_FOOTBALL_KEY"] = local_runtime()["API_FOOTBALL_KEY"]
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
