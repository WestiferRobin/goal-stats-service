from unittest.mock import create_autospec

import pytest
from flask import Flask

from infra.resources.db import Database
from infra.resources.redis import RedisCache
from routers.infra import create_health_blueprint


@pytest.mark.parametrize(
    ("database_ready", "redis_ready", "body", "status"),
    [(True, True, "Healthy", 200), (True, False, "Degraded", 200), (False, True, "Unhealthy", 503)],
)
def test_health_uses_explicit_resources_only(
    monkeypatch, database_ready, redis_ready, body, status
):
    database = create_autospec(Database, instance=True)
    cache = create_autospec(RedisCache, instance=True)
    cache.ready.return_value = redis_ready
    probes = []

    def probe(actual):
        assert actual is database
        probes.append(actual)
        return database_ready

    monkeypatch.setattr("infra.base.is_ready", probe)
    app = Flask(__name__)
    app.register_blueprint(create_health_blueprint(database, cache, "explicit-prefix"))
    assert app.extensions == {}
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200 and response.text == "Healthy"
    assert probes == []
    cache.ready.assert_not_called()
    response = client.get("/ready")
    assert response.status_code == status and response.text == body
    assert response.mimetype == "text/plain"
    assert probes == [database]
    if database_ready:
        cache.ready.assert_called_once_with("explicit-prefix")
    else:
        cache.ready.assert_not_called()
