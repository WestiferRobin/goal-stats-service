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


@pytest.mark.postgres
def test_production_domain_workflow_preserves_v2_and_seeded_simulation(
    scenario_client, app_factory, postgres_config, import_database, scenario_body
):
    from models.team import Team
    from tests.fixtures.historical_database import snapshot

    with import_database.transaction() as session:
        session.add(Team(team_id=4, name="Fourth", name_key="fourth", category="test"))
    client = app_factory(production_config(postgres_config)).test_client()
    headers = {"Authorization": "Bearer " + TOKEN}
    preview_body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    simulation = {
        "teams": [
            dict(team_id=i, offense=70, defense=70, form=70, star_power=70, clutch=70)
            for i in range(1, 5)
        ],
        "simulations": 1000,
        "seed": 2026,
    }
    before = snapshot(import_database)
    for url, body in [
        ("/api/v1/predictions/preview", preview_body),
        ("/api/v1/scenarios", scenario_body),
        ("/api/v1/competitions/simulate", simulation),
    ]:
        for denied in ({}, {"Authorization": "Bearer wrong"}):
            assert client.post(url, json=body, headers=denied).status_code == 401
    assert snapshot(import_database) == before
    preview = client.post("/api/v1/predictions/preview", json=preview_body, headers=headers)
    assert preview.status_code == 200
    assert preview.json["model"] == "road-to-the-final-heuristic-v2"
    assert snapshot(import_database) == before
    created = client.post("/api/v1/scenarios", json=scenario_body, headers=headers)
    assert created.status_code == 201
    url = created.headers["Location"]
    before = snapshot(import_database)
    for denied in ({}, {"Authorization": "Bearer wrong"}):
        assert client.post(url + "/predictions", headers=denied).status_code == 401
        assert client.patch(url, json={"match_minute": 105}, headers=denied).status_code == 401
    assert snapshot(import_database) == before
    first = client.post(url + "/predictions", headers=headers)
    assert first.status_code == 201
    assert first.json["output"] == preview.json
    assert client.patch(url, json={"match_minute": 105}, headers=headers).status_code == 200
    second = client.post(url + "/predictions", headers=headers)
    assert second.status_code == 201
    assert second.json["prediction_id"] != first.json["prediction_id"]
    assert second.json["output"]["expected_goals_remaining"] == {"team1": 0, "team2": 0}
    assert client.get(first.headers["Location"]).json == first.json
    assert client.get(url + "/predictions").json == [second.json, first.json]
    before = snapshot(import_database)
    result = client.post("/api/v1/competitions/simulate", json=simulation, headers=headers)
    assert result.status_code == 200
    assert result.json["seed"] == 2026
    assert (
        client.post("/api/v1/competitions/simulate", json=simulation, headers=headers).json
        == result.json
    )
    assert snapshot(import_database) == before
