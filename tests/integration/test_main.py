import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import main


def test_factory_instances_have_independent_resources(app_factory, explicit_config, monkeypatch):
    services = {"item": [], "action": []}

    def track(kind, constructor):
        def build(database, cache):
            service = constructor(database, cache)
            services[kind].append(service)
            return service

        return build

    monkeypatch.setattr(main, "ItemService", track("item", main.ItemService))
    monkeypatch.setattr(main, "ActionService", track("action", main.ActionService))
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
    assert (
        set(first.extensions)
        == set(second.extensions)
        == {
            "goalstats_settings",
            "goalstats_database",
            "goalstats_cache",
            "goalstats_item_cache",
            "goalstats_action_cache",
        }
    )
    for key in first.extensions:
        assert first.extensions[key] is not second.extensions[key]
    for name in ("items", "actions", "health"):
        assert first.blueprints[name] is not second.blueprints[name]
    for kind in services:
        assert len(services[kind]) == 2
        assert services[kind][0] is not services[kind][1]
        for app, service in zip((first, second), services[kind], strict=True):
            assert service.database is app.extensions["goalstats_database"]
            assert service.cache is app.extensions[f"goalstats_{kind}_cache"]
            monkeypatch.setattr(service, "list", Mock(return_value=[]))
        for index in (0, 1, 0, 1):
            app = (first, second)[index]
            other_calls = services[kind][1 - index].list.call_count
            assert app.test_client().get(f"/{kind}s").json == []
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
    assert "/items" in spec["paths"] and "/actions" in spec["paths"]
    assert set(spec["components"]["schemas"]["ProblemDetailSchema"]["required"]) == {
        "type",
        "title",
        "status",
        "detail",
    }
    assert (
        "application/problem+json"
        in spec["paths"]["/items"]["get"]["responses"]["default"]["content"]
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
assert set(Base.metadata.tables) == {
    'items', 'actions', 'football_teams', 'football_history', 'football_snapshots'
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
