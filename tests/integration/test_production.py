"""Production configuration and HTTP authentication without persistent providers."""

import pytest

from settings.base import ConfigurationError
from settings.environment import load_application

TOKEN = "test-only-service-token-0123456789abcdef"


def production_config(explicit_config):
    return {**explicit_config, "APP_ENV": "production", "SERVICE_API_TOKEN": TOKEN}


@pytest.mark.parametrize("token", ["", "short", "x" * 32 + "\n", "é" * 32])
def test_production_requires_safe_token(explicit_config, token):
    with pytest.raises(ConfigurationError, match="SERVICE_API_TOKEN") as error:
        load_application({**production_config(explicit_config), "SERVICE_API_TOKEN": token})
    if token:
        assert token not in str(error.value)


def test_production_external_settings_are_private_and_isolated(explicit_config):
    settings = load_application(
        {
            **production_config(explicit_config),
            "DATABASE_URL": "postgresql://service:private@db.example.com/goalstats"
            "?sslmode=verify-full&sslrootcert=system",
            "REDIS_URL": "rediss://default:private@redis.example.com:6379/0",
        }
    )
    assert settings.core.app_env == "production"
    assert settings.redis.cache_key_prefix == "goal-stats-service:production:v1"
    assert settings.database.url.host == "db.example.com"
    assert settings.redis.url.startswith("rediss://")
    assert TOKEN not in repr(settings) and "private" not in repr(settings)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "Basic abc", "Bearer é"])
def test_production_rejects_mutations_before_handlers(
    app_factory, explicit_config, method, authorization
):
    app = app_factory(production_config(explicit_config))
    app.add_url_rule("/probe", view_func=lambda: "accepted", methods=[method])
    headers = {} if authorization is None else {"Authorization": authorization}
    response = app.test_client().open("/probe", method=method, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.mimetype == "application/problem+json"
    assert TOKEN not in response.text


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_production_accepts_service_token(app_factory, explicit_config, method):
    app = app_factory(production_config(explicit_config))
    app.add_url_rule("/probe", view_func=lambda: "accepted", methods=[method])
    response = app.test_client().open(
        "/probe", method=method, headers={"Authorization": "Bearer " + TOKEN}
    )
    assert response.status_code == 200 and response.text == "accepted"


def test_production_health_is_public_and_domain_mutation_is_guarded(app_factory, explicit_config):
    app = app_factory(production_config(explicit_config))
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.head("/health").status_code == 200
    assert client.options("/api/v1/scenarios").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.post("/api/v1/scenarios", json={}).status_code == 401
    # Valid authentication reaches existing schema validation, without a DB write.
    assert (
        client.post(
            "/api/v1/scenarios", json={}, headers={"Authorization": "Bearer " + TOKEN}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("mode", ["local", "dev", "test"])
def test_existing_modes_do_not_require_authentication(app_factory, explicit_config, mode):
    app = app_factory({**explicit_config, "APP_ENV": mode})
    app.add_url_rule("/probe", view_func=lambda: "accepted", methods=["POST"])
    assert app.test_client().post("/probe").status_code == 200
