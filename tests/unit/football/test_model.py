import math
from copy import deepcopy

import pytest
from pydantic import ValidationError

from football.datasets import read_datasets
from football.engine import Match, Team, simulate_tournament
from football.historical import apply_historical_row_to_match
from football.provider import api_get
from schemas.football import PredictionRequest, TournamentRequest
from services.football import report


def test_bundled_data_and_incomplete_history():
    teams, history = read_datasets()
    assert len(teams) == 32
    assert len(history) == 16
    assert sum(bool(row["data"]["actual_winner"]) for row in history) == 13
    assert len({row["id"] for row in history}) == 16


def test_probabilities_normalized_and_modifiers_capped():
    teams, _ = read_datasets()
    match = Match(Team(**teams[0]), Team(**teams[1]))
    baseline = report(match)
    assert sum(baseline["probabilities"].values()) == pytest.approx(1)
    assert sum(baseline["advancement"].values()) == pytest.approx(1)
    assert sum(baseline["momentum_percent"].values()) == pytest.approx(100)
    match.team1.add_modifier("injury", -100)
    assert match.team1.event_score() == -20
    assert report(match)["probabilities"]["team1"] < baseline["probabilities"]["team1"]


def test_final_result_does_not_leak_into_snapshot_prediction():
    teams, history = read_datasets()
    ratings = {row["name"]: row for row in teams}
    row = deepcopy(history[0]["data"])

    def predict():
        match = Match(Team(**ratings[row["team1"]]), Team(**ratings[row["team2"]]))
        apply_historical_row_to_match(match, row)
        return report(match)

    before = predict()
    row.update(final_team1_goals="99", final_team2_goals="0", actual_winner=row["team2"])
    assert predict() == before


def test_tournament_stages_count_each_team_once():
    teams, _ = read_datasets()
    results, _, _, _ = simulate_tournament([Team(**team) for team in teams[:4]], 1000)
    assert all(row["semifinal_probability"] == 100 for row in results)
    assert sum(row["final_probability"] for row in results) == pytest.approx(200, abs=0.03)
    assert sum(row["champion_probability"] for row in results) == pytest.approx(100, abs=0.03)


@pytest.mark.parametrize(
    "extra",
    [
        {"minute": -1},
        {"minute": 121},
        {"team2": " spain "},
        {"team1_stats": {"goals": -1}},
        {"team1_stats": {"possession": math.nan}},
        {"team1_stats": {"possession": 60}},
        {"unknown": True},
    ],
)
def test_bad_prediction_requests_rejected(extra):
    with pytest.raises(ValidationError):
        PredictionRequest.model_validate({"team1": "Spain", "team2": "England", **extra})


def test_tournament_rejects_incomplete_or_duplicate_bracket():
    for names in [["Spain", "England", "France"], ["Spain", "England", "France", " spain "]]:
        with pytest.raises(ValidationError):
            TournamentRequest(teams=names)


def test_no_key_never_calls_provider(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    monkeypatch.setattr("football.provider.urlopen", lambda *a, **k: pytest.fail("network call"))
    assert api_get("/fixtures") is None


def test_prediction_matches_original_road_to_the_final_reference():
    # Independently evaluated from source app.py at 8f17bc42e30f436f5cd860f2791695421160ccd2.
    teams, _ = read_datasets()
    match = Match(Team(**teams[0]), Team(**teams[1]))
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.37074041064032975, 0.26390886112362144, 0.36535072823604886)
    )
    match.match_minute = 65
    match.team1.goals = 1
    match.team1.shots_on_target = 4
    match.team1.possession = 60
    match.team2.possession = 40
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.8136391843803665, 0.15959690743009677, 0.026763908189536657)
    )
