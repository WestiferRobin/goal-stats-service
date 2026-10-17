import json
from pathlib import Path

import pytest
from sqlalchemy import text

from services.prediction import PredictionService
from tests.fixtures.historical_database import count, generate, history_url


@pytest.mark.postgres
@pytest.mark.parametrize(
    "changes",
    [
        {"team1_offense": None},
        {"team2_clutch": None},
        {"team1_defense": float("nan")},
        {"team1_form": 101},
        {"team2_possession": 100},
    ],
)
def test_unready_inputs_are_identified_without_writes(
    scenario_client, saved_scenario, import_database, monkeypatch, changes
):
    # Current DB constraints forbid these states. Simulate legacy/corrupt loader input
    # without weakening the schema or touching persistent development records.
    load = PredictionService._load_scenario

    def invalid(self, scenario_id):
        return {**load(self, scenario_id), **changes}

    monkeypatch.setattr(PredictionService, "_load_scenario", invalid)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 400
    assert "not prediction-ready" in response.json["detail"]
    if "team2_possession" not in changes:
        assert next(iter(changes)) in response.json["detail"]
    assert count(import_database) == 0
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json
        == saved_scenario
    )


@pytest.mark.postgres
def test_missing_rating_field_is_identified(
    scenario_client, saved_scenario, monkeypatch, import_database
):
    load = PredictionService._load_scenario

    def missing(self, scenario_id):
        data = load(self, scenario_id)
        del data["team1_offense"]
        return data

    monkeypatch.setattr(PredictionService, "_load_scenario", missing)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 400 and "team1_offense" in response.json["detail"]
    assert count(import_database) == 0


@pytest.mark.postgres
def test_history_empty_order_pagination_and_missing(
    scenario_client, saved_scenario, import_database
):
    url = history_url(saved_scenario)
    assert scenario_client.get(url).json == []
    rows = [generate(scenario_client, saved_scenario).json for _ in range(3)]
    with import_database.transaction() as session:
        session.execute(text("UPDATE predictions SET generated_at='2026-01-01T00:00:00Z'"))
    all_rows = scenario_client.get(url).json
    assert [r["prediction_id"] for r in all_rows] == [r["prediction_id"] for r in rows[::-1]]
    assert scenario_client.get(url + "?limit=1&offset=1").json == all_rows[1:2]
    assert scenario_client.get(url + "?offset=10").json == []
    assert scenario_client.get("/api/v1/scenarios/2147483647/predictions").status_code == 404
    assert scenario_client.post("/api/v1/scenarios/2147483647/predictions").status_code == 404
    assert scenario_client.get("/api/v1/predictions/2147483647").status_code == 404


@pytest.mark.postgres
@pytest.mark.parametrize(
    "suffix",
    [
        "?limit=0",
        "?limit=201",
        "?offset=-1",
        "?offset=x",
        "?offset=9223372036854775808",
        "?unknown=1",
    ],
)
def test_invalid_pagination(scenario_client, saved_scenario, suffix):
    assert scenario_client.get(history_url(saved_scenario) + suffix).status_code == 400


@pytest.mark.postgres
@pytest.mark.parametrize("identifier", ["0", "-1", "no", "1.5", "2147483648"])
def test_invalid_ids(scenario_client, identifier):
    for method, path in [
        ("get", f"/api/v1/predictions/{identifier}"),
        ("get", f"/api/v1/scenarios/{identifier}/predictions"),
        ("post", f"/api/v1/scenarios/{identifier}/predictions"),
    ]:
        assert getattr(scenario_client, method)(path).status_code == 400


@pytest.mark.postgres
def test_generation_rejects_body_and_query_overrides(scenario_client, saved_scenario):
    url = history_url(saved_scenario)
    assert scenario_client.post(url, json={}).status_code == 400
    assert scenario_client.post(url, json={"team1_offense": 99}).status_code == 400
    assert scenario_client.post(url + "?minute=0").status_code == 400


@pytest.mark.postgres
def test_saved_workflow_matches_router_baseline(scenario_client, scenario_body):
    client = scenario_client
    responses = {}

    def record(name, response):
        assert response.status_code < 500, response.json
        responses[name] = {
            "status": response.status_code,
            "content_type": response.content_type,
            "location": response.headers.get("Location"),
            "json": response.json,
        }
        return response

    scenario = record("create", client.post("/api/v1/scenarios", json=scenario_body))
    path = scenario.headers["Location"]
    record("get", client.get(path))
    record("list", client.get("/api/v1/scenarios"))
    prediction = record("generate_bodyless", client.post(path + "/predictions"))
    record("patch", client.patch(path, json={"match_minute": 80, "team2_goals": 1}))
    record("saved_prediction", client.get(prediction.headers["Location"]))
    record("history", client.get(path + "/predictions"))
    record("body_rejected", client.post(path + "/predictions", json={}))
    record("invalid_patch", client.patch(path, json={"team1_offense": 99}))
    record("missing_scenario", client.get("/api/v1/scenarios/999"))
    record("missing_prediction", client.get("/api/v1/predictions/999"))
    record("missing_team", client.get("/api/v1/catalog/teams/999"))
    record("missing_match", client.get("/api/v1/catalog/matches/999"))

    def stable(value):
        if isinstance(value, dict):
            return {
                key: "<timestamp>" if key in {"created_at", "generated_at"} else stable(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value

    baseline = json.loads(Path(__file__).with_name("router_contract.json").read_text())
    assert stable(responses) == baseline


@pytest.mark.postgres
def test_preview_is_read_only_and_matches_saved_calculation(
    scenario_client, scenario_body, import_database
):
    from tests.fixtures.historical_database import snapshot

    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    before = snapshot(import_database)
    response = scenario_client.post("/api/v1/predictions/preview", json=body)
    assert response.status_code == 200, response.json
    assert snapshot(import_database) == before
    saved = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    prediction = scenario_client.post(saved.headers["Location"] + "/predictions")
    assert prediction.json["output"] == response.json
    before = snapshot(import_database)
    for changes, status in [
        ({"team2_id": 999}, 404),
        ({"team2_id": 1}, 400),
        ({"team1_offense": None}, 400),
    ]:
        assert (
            scenario_client.post(
                "/api/v1/predictions/preview", json={**body, **changes}
            ).status_code
            == status
        )
    assert snapshot(import_database) == before
