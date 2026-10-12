"""Core Goal Stats contracts over real HTTP using explicit synthetic model inputs."""

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke
BASE = "/api/v1"


def test_catalog(smoke_client):
    client = smoke_client
    teams, _ = client.request(BASE + "/catalog/teams")
    assert {team["team_id"] for team in teams} == {1, 2}
    assert all(team["offense"] is None for team in teams)
    competitions, _ = client.request(BASE + "/catalog/competitions")
    assert competitions[0]["name"] == "Synthetic smoke competition"
    matches, _ = client.request(BASE + "/catalog/matches")
    assert len(matches) == 1
    match, _ = client.request(BASE + "/catalog/matches/1")
    assert match == matches[0]
    client.request(BASE + "/catalog/teams/999999", expected=404)
    client.request(BASE + "/catalog/matches/999999", expected=404)


def test_scenario_prediction_history_and_snapshots(smoke_client, scenario_body):
    client = smoke_client
    teams, _ = client.request(BASE + "/catalog/teams")
    scenario_body.update(
        title="HTTP smoke — explicit synthetic model inputs",
        team1_id=teams[0]["team_id"],
        team2_id=teams[1]["team_id"],
    )
    scenario, headers = client.request(BASE + "/scenarios", "POST", scenario_body, 201)
    path = headers["Location"]
    assert client.request(path)[0] == scenario
    updated, _ = client.request(path, "PATCH", {"match_minute": 70})
    assert client.request(path)[0] == updated
    prediction_a, first_headers = client.request(path + "/predictions", "POST", expected=201)
    assert client.request(first_headers["Location"])[0] == prediction_a
    updated, _ = client.request(path, "PATCH", {"match_minute": 85, "team1_goals": 2})
    assert client.request(path)[0] == updated
    prediction_b, second_headers = client.request(path + "/predictions", "POST", expected=201)
    assert prediction_a["input_snapshot"]["match_minute"] == 70
    assert prediction_b["input_snapshot"]["match_minute"] == 85
    assert prediction_b["input_snapshot"]["team1_goals"] == 2
    assert client.request(first_headers["Location"])[0] == prediction_a
    assert client.request(second_headers["Location"])[0] == prediction_b
    client.request(path + "/predictions?limit=0", expected=400)
    history, _ = client.request(path + "/predictions")
    assert {p["prediction_id"] for p in history} == {
        prediction_a["prediction_id"],
        prediction_b["prediction_id"],
    }
    Path(os.environ["SMOKE_RESULTS"]).write_text(
        json.dumps(
            {
                "scenario_path": path,
                "scenario": updated,
                "predictions": {
                    first_headers["Location"]: prediction_a,
                    second_headers["Location"]: prediction_b,
                },
            }
        )
    )


@pytest.mark.parametrize(
    "path", ["/scenarios/999999", "/predictions/999999", "/scenarios/999999/predictions"]
)
def test_missing_records(smoke_client, path):
    smoke_client.request(BASE + path, expected=404)


@pytest.mark.parametrize(
    "changes", [{"team1_id": 999999}, {"team1_shots": -1}, {"team1_possession": 101}]
)
def test_invalid_scenario(smoke_client, scenario_body, changes):
    scenario_body.update(changes)
    smoke_client.request(
        BASE + "/scenarios", "POST", scenario_body, 404 if "team1_id" in changes else 400
    )


def test_missing_model_inputs(smoke_client, scenario_body):
    scenario_body.pop("team1_offense")
    smoke_client.request(BASE + "/scenarios", "POST", scenario_body, 400)


@pytest.mark.parametrize("path", ["/catalog/matches", "/scenarios"])
def test_invalid_pagination(smoke_client, path):
    smoke_client.request(BASE + path + "?limit=0", expected=400)
