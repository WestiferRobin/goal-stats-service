import pytest

from football.engine import Match, Team
from football.report import report
from tests.fixtures.calculations import REFERENCE_TEAMS


def test_probabilities_normalized_and_modifiers_capped():
    teams = REFERENCE_TEAMS
    match = Match(Team(**teams[0]), Team(**teams[1]))
    baseline = report(match)
    assert sum(baseline["probabilities"].values()) == pytest.approx(1)
    assert sum(baseline["advancement"].values()) == pytest.approx(1)
    assert sum(baseline["momentum_percent"].values()) == pytest.approx(100)
    match.team1.add_modifier("injury", -100)
    assert match.team1.event_score() == -20
    assert report(match)["probabilities"]["team1"] < baseline["probabilities"]["team1"]
