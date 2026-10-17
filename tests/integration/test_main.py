import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import jsonify, request
from flask_openapi3.blueprint import APIBlueprint
from pydantic import BaseModel, ConfigDict
from sqlalchemy import event
from werkzeug.exceptions import BadRequest

import main
from exceptions.base import DomainError
from exceptions.handlers import object_body
from settings.environment import load_application
from tests.fixtures.historical_database import snapshot


@pytest.mark.postgres
@pytest.mark.parametrize("mode", ["factory", "host"])
def test_empty_database_startup_never_imports(
    import_database, postgres_config, app_factory, monkeypatch, mode
):
    before = snapshot(import_database)
    expected = {
        "teams",
        "competitions",
        "matches",
        "scenarios",
        "predictions",
    }
    assert expected <= before.keys()
    assert all(before[table] == [] for table in expected)
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def forbidden(*args, **kwargs):
        pytest.fail("Startup must never select a dataset or invoke an importer")

    for module, name in [
        ("football.cli", "import_historical_dataset"),
        ("football.historical_import", "load_manifest"),
    ]:
        monkeypatch.setattr(f"{module}.{name}", forbidden)
    monkeypatch.setattr(main, "Database", lambda _: import_database)
    event.listen(import_database.engine, "before_cursor_execute", track)
    apps = []

    def check(app):
        apps.append(app)
        client = app.test_client()
        for path in ("/health", "/ready", "/swagger", "/swagger/v1/swagger.json"):
            assert client.get(path).status_code == 200, path
        spec = client.get("/swagger/v1/swagger.json").json
        assert len(spec["paths"]) == 14
        for path in (
            "/api/v1/catalog/teams",
            "/api/v1/catalog/matches",
            "/api/v1/catalog/competitions",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json == [], path

    try:
        if mode == "factory":
            check(app_factory(postgres_config))
        else:
            monkeypatch.setenv("API_FOOTBALL_KEY", "")
            monkeypatch.setattr(main, "load_local", lambda: load_application(postgres_config))
            monkeypatch.setattr(main, "local_runtime", lambda: {"API_FOOTBALL_KEY": ""})
            monkeypatch.setattr(main, "_check_app_port", lambda _: None)
            # Run the actual host entrypoint, replacing only its blocking HTTP loop.
            monkeypatch.setattr(main.Flask, "run", lambda app, **kwargs: check(app))
            main.development_main()
        assert snapshot(import_database) == before
        assert not any(
            s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"))
            for s in statements
        )
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)
        for app in apps:
            app.extensions["goalstats_cache"].close()


@pytest.mark.parametrize(
    "path,method,status",
    [
        ("/missing", "get", 404),
        ("/health", "post", 405),
        ("/_domain", "get", 400),
        ("/_invalid_output", "get", 500),
        ("/_http", "get", 400),
        ("/_unexpected", "get", 500),
    ],
)
def test_consistent_safe_problem_details(error_app, path, method, status, capsys):
    response = getattr(error_app.test_client(), method)(path, headers={"Accept": "text/html"})
    assert response.status_code == status
    assert response.mimetype == "application/problem+json"
    assert set(response.json) == {"type", "title", "status", "detail"}
    assert response.json["status"] == status
    assert response.json["type"] == "about:blank"
    assert "private_password" not in response.text
    assert "internal_connection_failure" not in response.text
    # Match concrete implementation identifiers/URL schemes, not ordinary
    # user-facing words such as "database" or "connection".
    assert not re.search(
        r"traceback \(most recent call last\)|\bpsycopg\b|"
        r"postgres(?:ql)?(?:\+psycopg)?://|rediss?://",
        response.text,
        re.IGNORECASE,
    )
    assert "private_password" not in capsys.readouterr().err
    if status == 405:
        assert {"GET", "HEAD", "OPTIONS"} <= set(
            response.headers["Allow"].replace(" ", "").split(",")
        )


@pytest.fixture
def error_app(app):
    # Test-only routes exercise real Flask/Pydantic boundaries, never production debug routes.
    blueprint = APIBlueprint("boundary_test", __name__)

    class InputSchema(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str

    blueprint.before_request(object_body)

    @blueprint.post("/_validation", responses={200: InputSchema})
    def validate(body: InputSchema):
        return jsonify(body.model_dump(mode="json"))

    @app.post("/_json")
    def json_body():
        return request.get_json()

    @app.get("/_domain")
    def domain():
        raise DomainError(PRIVATE_DETAILS)

    @app.get("/_invalid_output")
    def invalid_output():
        return InputSchema.model_validate({"name": None})

    @app.get("/_http")
    def http():
        raise BadRequest(PRIVATE_DETAILS)

    @app.get("/_unexpected")
    def unexpected():
        raise RuntimeError(PRIVATE_DETAILS)

    app.register_api(blueprint)
    return app


PRIVATE_DETAILS = (
    "private_password internal_connection_failure psycopg.OperationalError "
    "postgresql://user:secret@database/private "
    "postgresql+psycopg://user:secret@database/private redis://cache:6379/0 "
    "Traceback (most recent call last):"
)


@pytest.mark.parametrize(
    "path", ["/_json", "/_validation", "/api/v1/scenarios", "/api/v1/predictions/preview"]
)
def test_malformed_json_uses_problem_details(error_app, path):
    response = error_app.test_client().post(
        path, data="{broken private_password", content_type="application/json"
    )
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"
    assert "private_password" not in response.text


def test_pydantic_validation_uses_400_and_unknown_fields_are_rejected(error_app):
    client = error_app.test_client()
    for data in [{}, {"name": "valid", "unexpected": "private_password"}]:
        response = client.post("/_validation", json=data)
        assert response.status_code == 400
        assert response.mimetype == "application/problem+json"
        assert "private_password" not in response.text
    assert client.post("/_validation", json={"name": "valid"}).json == {"name": "valid"}


def test_non_json_body_is_safe_415(error_app):
    response = error_app.test_client().post(
        "/_json", data="private_password", content_type="text/plain"
    )
    assert response.status_code == 415
    assert response.mimetype == "application/problem+json"
    assert "private_password" not in response.text


def test_factory_instances_have_independent_resources(app_factory, explicit_config, monkeypatch):
    services = {"team": [], "competition": []}

    def track(kind, constructor):
        def build(*args, **kwargs):
            service = constructor(*args, **kwargs)
            services[kind].append(service)
            return service

        return build

    monkeypatch.setattr(main, "TeamService", track("team", main.TeamService))
    monkeypatch.setattr(main, "CompetitionService", track("competition", main.CompetitionService))
    first = app_factory(explicit_config)
    second = app_factory({**explicit_config, "OPENAPI_ENABLED": "false", "LOG_LEVEL": "ERROR"})
    assert (
        first.extensions["goalstats_database"].engine
        is not second.extensions["goalstats_database"].engine
    )
    assert first.api_doc is not second.api_doc
    assert first.api_doc == second.api_doc
    first.api_doc["info"]["description"] = "First application only"
    assert "description" not in second.api_doc["info"]
    assert first.logger is not second.logger
    assert first.logger.level != second.logger.level
    assert set(first.extensions) == set(second.extensions)
    assert {"goalstats_settings", "goalstats_database", "goalstats_cache"} <= set(first.extensions)
    for key in first.extensions:
        assert first.extensions[key] is not second.extensions[key]
    for name in ("team", "competition", "match", "scenarios", "saved_predictions", "health"):
        assert first.blueprints[name] is not second.blueprints[name]
    for kind in services:
        assert len(services[kind]) == 2
        assert services[kind][0] is not services[kind][1]
        for app, service in zip((first, second), services[kind], strict=True):
            assert (
                service.repo.database if hasattr(service, "repo") else service.database
            ) is app.extensions["goalstats_database"]
            monkeypatch.setattr(service, "list", Mock(return_value=[]))
        for index in (0, 1, 0, 1):
            app = (first, second)[index]
            other_calls = services[kind][1 - index].list.call_count
            assert app.test_client().get(f"/api/v1/catalog/{kind}s").json == []
            assert services[kind][1 - index].list.call_count == other_calls
        assert [service.list.call_count for service in services[kind]] == [2, 2]
    assert first.test_client().get("/swagger/v1/swagger.json").status_code == 200
    assert second.test_client().get("/swagger/v1/swagger.json").status_code == 404


def test_health_is_independent_of_unreachable_database(app):
    db = app.extensions["goalstats_database"]
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.text == "Healthy"
    assert response.mimetype == "text/plain"
    assert db.engine.pool.checkedout() == 0


def test_unavailable_database_is_unhealthy_without_provider_details(app):
    response = app.test_client().get("/ready")
    assert response.status_code == 503
    assert response.text == "Unhealthy"
    assert response.mimetype == "text/plain"
    assert app.extensions["goalstats_database"].engine.pool.checkedout() == 0


def test_openapi_preserves_problem_contract_and_includes_operational_paths(app):
    spec = app.test_client().get("/swagger/v1/swagger.json").json
    assert spec["openapi"] == "3.1.0"
    assert "/health" in spec["paths"] and "/ready" in spec["paths"]
    assert "/items" not in spec["paths"] and "/actions" not in spec["paths"]
    assert set(spec["components"]["schemas"]["ProblemDetailSchema"]["required"]) == {
        "type",
        "title",
        "status",
        "detail",
    }
    assert (
        "application/problem+json"
        in spec["paths"]["/api/v1/catalog/teams"]["get"]["responses"]["default"]["content"]
    )


def test_import_and_factory_have_no_filesystem_or_provider_side_effects(tmp_path):
    source = Path(__file__).resolve().parents[2] / "src"
    code = r"""
import os, sys

def audit(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'os.mkdir', 'os.remove', 'os.rename'}:
        raise AssertionError('Unexpected side effect: ' + event)
    if event == 'open':
        mode, flags = args[1], args[2]
        writing_mode = isinstance(mode, str) and any(c in mode for c in 'wax+')
        writing_flags = flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        if writing_mode or writing_flags:
            raise AssertionError('Unexpected file write')
sys.addaudithook(audit)
from main import create_app
from models.base import Base
import importlib.util
assert importlib.util.find_spec('services.football') is None
assert importlib.util.find_spec('routers.football') is None
assert importlib.util.find_spec('football.import_data') is None
assert set(Base.metadata.tables) == {
    'teams', 'competitions', 'matches', 'scenarios', 'predictions'
}
app = create_app({'APP_ENV': 'test', 'DATABASE_URL': 'postgresql://u:p@127.0.0.1:1/goalstats_test_import'})
assert app.test_client().get('/health').text == 'Healthy'
app.extensions['goalstats_database'].dispose()
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(source),
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATABASE_URL": "invalid",
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_registered_routes_match_pre_integration_baseline(app):
    baseline = json.loads(Path(__file__).with_name("router_inventory.json").read_text())
    routes = sorted(
        [
            rule.rule,
            rule.endpoint,
            sorted(rule.methods),
            rule.strict_slashes,
            {key: type(value).__name__ for key, value in rule._converters.items()},
        ]
        for rule in app.url_map.iter_rules()
    )
    assert routes == baseline["routes"]
    assert list(app.blueprints) == baseline["blueprints"]


def test_entity_routes_use_their_own_application_services(
    app_factory, explicit_config, monkeypatch, scenario_body
):
    services = {}

    def track(name, constructor):
        services[name] = []

        def build(*args, **kwargs):
            service = constructor(*args, **kwargs)
            services[name].append(service)
            return service

        return build

    for name in (
        "TeamService",
        "CompetitionService",
        "MatchService",
        "ScenarioService",
        "PredictionService",
    ):
        monkeypatch.setattr(main, name, track(name, getattr(main, name)))
    apps = [app_factory(explicit_config), app_factory(explicit_config)]
    for instances in services.values():
        assert len(instances) == 2 and instances[0] is not instances[1]
        for app, service in zip(apps, instances, strict=True):
            assert (
                service.repo.database if hasattr(service, "repo") else service.database
            ) is app.extensions["goalstats_database"]

    for index in (0, 1):
        scenario = services["ScenarioService"][index]
        assert scenario.team_service is services["TeamService"][index]
        assert scenario.match_service is services["MatchService"][index]
        assert services["PredictionService"][index].scenario_service is scenario
    for name, instances in services.items():
        if name != "FootballService":
            assert instances[0].repo is not instances[1].repo
            for instance in instances:
                assert vars(instance.repo) == {"database": instance.repo.database}

    routes = [
        ("TeamService", "list", "get", "/catalog/teams", None, []),
        ("TeamService", "get", "get", "/catalog/teams/1", None, {"team_id": 1}),
        ("CompetitionService", "list", "get", "/catalog/competitions", None, []),
        ("MatchService", "list", "get", "/catalog/matches?limit=1", None, []),
        ("MatchService", "get", "get", "/catalog/matches/1", None, {"match_id": 1}),
        ("ScenarioService", "create", "post", "/scenarios", scenario_body, {"scenario_id": 1}),
        ("ScenarioService", "list", "get", "/scenarios", None, []),
        ("ScenarioService", "get", "get", "/scenarios/1", None, {"scenario_id": 1}),
        (
            "ScenarioService",
            "update",
            "patch",
            "/scenarios/1",
            {"match_minute": 70},
            {"scenario_id": 1},
        ),
        (
            "PredictionService",
            "generate",
            "post",
            "/scenarios/1/predictions",
            None,
            {"prediction_id": 1},
        ),
        ("PredictionService", "history", "get", "/scenarios/1/predictions", None, []),
        ("PredictionService", "get", "get", "/predictions/1", None, {"prediction_id": 1}),
    ]
    for name, method, verb, path, body, result in routes:
        mocks = [Mock(return_value=result), Mock(return_value=result)]
        for instance, mock in zip(services[name], mocks, strict=True):
            monkeypatch.setattr(instance, method, mock)
        for index, app in enumerate(apps):
            kwargs = {} if body is None else {"json": body}
            response = getattr(app.test_client(), verb)("/api/v1" + path, **kwargs)
            assert response.status_code == (201 if verb == "post" else 200)
            assert response.json == result
            mocks[index].assert_called_once()
            assert mocks[1 - index].call_count == index
        assert all(
            app.extensions["goalstats_database"].engine.pool.checkedout() == 0 for app in apps
        )
