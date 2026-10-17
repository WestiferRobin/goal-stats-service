from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from football.engine import Match as EngineMatch
from football.engine import Team as EngineTeam
from football.report import report
from models.prediction import Prediction
from models.team import Team
from tests.fixtures.historical_database import count, generate, history_url


@pytest.mark.postgres
def test_engine_parity_effective_inputs_and_no_transaction_during_compute(
    scenario_client, saved_scenario, import_database, monkeypatch
):
    expected_teams = []
    for side in (1, 2):
        prefix = f"team{side}_"
        team = EngineTeam(
            saved_scenario[prefix + "name"],
            **{
                field: saved_scenario[prefix + field]
                for field in ["offense", "defense", "form", "star_power", "clutch", "fifa_rank"]
            },
        )
        for field in [
            "goals",
            "possession",
            "shots",
            "shots_on_target",
            "big_chances",
            "defender_blocks",
            "goalkeeper_saves",
            "corners",
            "yellow_cards",
            "red_cards",
        ]:
            setattr(team, field, saved_scenario[prefix + field])
        team.shots = max(team.shots, team.shots_on_target)
        total = saved_scenario[prefix + "modifier_total"]
        if total:
            team.add_modifier("Saved scenario modifier total", total)
        expected_teams.append(team)
    expected = report(EngineMatch(*expected_teams, match_minute=saved_scenario["match_minute"]))
    calls = []

    def wrapped(match):
        assert import_database.engine.pool.checkedout() == 0
        calls.append(match)
        return report(match)

    monkeypatch.setattr("football.scenario_prediction.report", wrapped)

    def forbidden(*args, **kwargs):
        raise AssertionError("No prototype lookup or network requests allowed")

    monkeypatch.setattr("football.provider.api_get", forbidden)
    response = generate(scenario_client, saved_scenario)
    saved = response.json
    assert len(calls) == 1 and saved["output"] == expected
    assert saved["model_version"] == expected["model"] == "road-to-the-final-heuristic-v1"
    assert datetime.fromisoformat(saved["generated_at"]).tzinfo is not None
    assert saved["input_snapshot"]["team1_shots"] == 4
    assert saved["input_snapshot"]["team1_modifier_total"] == -7
    assert saved["input_snapshot"]["extra_minute"] == 0
    assert saved["input_snapshot"]["status"] == ""
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json
        == saved_scenario
    )
    assert scenario_client.get(response.headers["Location"]).json == saved
    with import_database.transaction() as session:
        row = session.get(Prediction, saved["prediction_id"])
        assert row.input_snapshot == saved["input_snapshot"]
        assert row.team1_win_probability == expected["probabilities"]["team1"]
        assert row.draw_probability == expected["probabilities"]["draw"]
        assert row.team2_win_probability == expected["probabilities"]["team2"]
        assert row.team1_expected_remaining_goals == expected["expected_goals_remaining"]["team1"]
        assert row.most_likely_team1_score == expected["most_likely_score"][0]
        assert row.details["reasoning"] == expected["reasoning"]
        assert "probabilities" not in row.details


@pytest.mark.postgres
def test_recalculation_preserves_A_and_B_and_reopens_after_restart(
    scenario_client, saved_scenario, import_database, app_factory, postgres_config, monkeypatch
):
    first = generate(scenario_client, saved_scenario).json
    path = f"/api/v1/scenarios/{saved_scenario['scenario_id']}"
    assert (
        scenario_client.patch(path, json={"match_minute": 80, "team2_goals": 2}).status_code == 200
    )
    with import_database.transaction() as session:
        team = session.get(Team, saved_scenario["team1_id"])
        team.name = "Renamed team"
        team.offense, team.ratings_source = 99, "test"
    second = generate(scenario_client, saved_scenario).json
    third = generate(scenario_client, saved_scenario).json
    assert len({r["prediction_id"] for r in [first, second, third]}) == 3
    assert first["scenario_id"] == second["scenario_id"]
    assert first["input_snapshot"]["match_minute"] == 65
    assert second["input_snapshot"]["match_minute"] == 80
    assert first["input_snapshot"]["team2_goals"] == 0
    assert second["input_snapshot"]["team2_goals"] == 2
    assert second["input_snapshot"]["team1_offense"] == first["input_snapshot"]["team1_offense"]
    assert first["output"]["team1"] == "First" and second["output"]["team1"] == "Renamed team"
    assert first["output"] != second["output"]

    def forbidden(*args):
        raise AssertionError("Retrieval must not compute")

    monkeypatch.setattr("services.prediction.predict_inputs", forbidden)
    import_database.dispose()
    reopened = app_factory(postgres_config).test_client()
    for row in [first, second, third]:
        assert reopened.get(f"/api/v1/predictions/{row['prediction_id']}").json == row
    assert reopened.get(history_url(saved_scenario)).json == [third, second, first]


@pytest.mark.postgres
def test_concurrent_scenario_edit_after_capture_keeps_original_inputs(
    scenario_client, saved_scenario, monkeypatch
):
    from football.scenario_prediction import predict_inputs

    def edit_then_compute(inputs):
        patch = scenario_client.patch(
            f"/api/v1/scenarios/{saved_scenario['scenario_id']}", json={"match_minute": 90}
        )
        assert patch.status_code == 200
        return predict_inputs(inputs)

    monkeypatch.setattr("services.prediction.predict_inputs", edit_then_compute)
    saved = generate(scenario_client, saved_scenario).json
    assert saved["input_snapshot"]["match_minute"] == saved["output"]["minute"] == 65
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json[
            "match_minute"
        ]
        == 90
    )


@pytest.mark.postgres
@pytest.mark.parametrize(
    "change",
    [
        {"probabilities": {"team1": 0.5, "draw": 0.5, "team2": 0.5}},
        {"probabilities": {"team1": -1, "draw": 1, "team2": 1}},
        {"probabilities": {"team1": float("nan"), "draw": 0, "team2": 1}},
        {"expected_goals_remaining": {"team1": -1, "team2": 1}},
        {"expected_goals_remaining": {"team1": float("inf"), "team2": 1}},
        {"most_likely_score": [-1, 0]},
        {"most_likely_score": [0]},
        {"top_scorelines": [{"team1_goals": 0, "team2_goals": 0, "probability": 2}]},
        {"confidence": {"percent": float("nan"), "label": "invalid"}},
        {"team1": "wrong team"},
        {"model": " "},
    ],
)
def test_invalid_output_never_persists(
    scenario_client, saved_scenario, import_database, monkeypatch, change
):
    from football.scenario_prediction import predict_inputs

    monkeypatch.setattr(
        "services.prediction.predict_inputs", lambda inputs: {**predict_inputs(inputs), **change}
    )
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 500
    assert "Reopen the saved scenario" in response.json["detail"]
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").status_code == 200
    )
    assert count(import_database) == 0


@pytest.mark.postgres
def test_engine_failure_never_persists(
    scenario_client, saved_scenario, import_database, monkeypatch
):
    def fail(inputs):
        raise RuntimeError("secret provider credentials")

    monkeypatch.setattr("services.prediction.predict_inputs", fail)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 500 and "secret" not in response.text
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").status_code == 200
    )
    assert count(import_database) == 0


@pytest.mark.postgres
def test_database_failure_rolls_back(scenario_client, saved_scenario, import_database):
    def fail(session):
        if any(isinstance(obj, Prediction) for obj in session.identity_map.values()):
            raise OperationalError("secret SQL", {}, Exception("private"))

    event.listen(Session, "before_commit", fail)
    try:
        response = scenario_client.post(history_url(saved_scenario))
        assert response.status_code == 500 and "secret" not in response.text
    finally:
        event.remove(Session, "before_commit", fail)
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").status_code == 200
    )
    assert count(import_database) == 0
