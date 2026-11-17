import pytest

from football.engine import Match, Team
from football.report import report
from tests.fixtures.calculations import REFERENCE_TEAMS


def test_probabilities_normalized_and_modifiers_capped():
    teams = REFERENCE_TEAMS
    match = Match(Team(**teams[0]), Team(**teams[1]))
    baseline = report(match)
    assert baseline["model"] == "road-to-the-final-heuristic-v1"
    assert baseline["reasoning"] == match.reasoning_summary()
    assert sum(baseline["probabilities"].values()) == pytest.approx(1)
    assert sum(baseline["advancement"].values()) == pytest.approx(1)
    assert sum(baseline["momentum_percent"].values()) == pytest.approx(100)
    match.team1.add_modifier("injury", -100)
    assert match.team1.event_score() == -20
    assert report(match)["probabilities"]["team1"] < baseline["probabilities"]["team1"]


@pytest.mark.parametrize("minute", [0, 45, 89, 90, 91, 105, 120])
@pytest.mark.parametrize("score", [(2, 1), (1, 2), (1, 1)])
def test_v2_report_shape_explanations_and_horizon(minute, score):
    from schemas.prediction import SavedEngineOutput

    a, b = Team("A", 70, 70, 70, 70, 70), Team("B", 70, 70, 70, 70, 70)
    a.goals, b.goals = score
    match = Match(a, b, minute, regulation_horizon=True)
    output = report(match)
    assert set(output) == set(SavedEngineOutput.model_fields)
    assert SavedEngineOutput.model_validate(output).model_dump() == output
    assert output["model"] == "road-to-the-final-heuristic-v2"
    assert output["minute"] == minute
    text = " ".join(output["reasoning"])
    for explanation in (
        "user-provided hypothetical inputs",
        "Historical browsing does not automatically supply these ratings",
        "calculated estimates, not recorded historical match results",
        "Stoppage time, extra time, and penalty shootouts are not forecast",
        "do not establish match completion",
        "margin between the two leading outcome probabilities",
        "not measured prediction accuracy",
        "hypothetical clutch-weighted tiebreak assumption",
        "not a recorded shootout outcome",
        "total shots are normalized upward",
    ):
        assert explanation in text
    assert "Saved scenario" not in text
    if minute >= 90:
        assert "No future match period is modeled" in text
        assert "summarizes the supplied current score" in text
        assert "does not confirm an actual final result or reconstruct the minute-90 score" in text
        assert "calculating remaining goals from minute" not in text
        assert output["expected_goals_remaining"] == {"team1": 0, "team2": 0}
        assert output["most_likely_score"] == list(score)
        assert output["probabilities"] == {
            "team1": int(score[0] > score[1]),
            "draw": int(score[0] == score[1]),
            "team2": int(score[0] < score[1]),
        }
    else:
        assert f"from minute {minute} through the nominal 90-minute horizon" in text
    assert output["advancement"] == dict(
        zip(
            ("team1", "team2"),
            match.advancement_probabilities(
                tuple(output["probabilities"][key] for key in ("team1", "draw", "team2"))
            ),
            strict=True,
        )
    )
    assert sum(output["momentum_percent"].values()) == pytest.approx(100)
    assert 0 <= output["confidence"]["percent"] <= 100
