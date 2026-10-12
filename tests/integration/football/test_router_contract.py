"""HTTP workflow captured before direct entity-service router integration."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres


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
