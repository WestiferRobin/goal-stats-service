import pytest
from pydantic import ValidationError

from schemas.engine import Modifier, TeamStats
from schemas.football import PredictionRequest, TournamentRequest


def test_engine_defaults_are_independent_and_prototype_request_compatible():
    first, second = TeamStats(), TeamStats()
    first.modifiers.append(Modifier(reason="fixture", value=10))
    assert second.modifiers == []
    request = PredictionRequest(team1="First", team2="Second")
    assert request.team1_stats.possession == request.team2_stats.possession == 50
    with pytest.raises(ValidationError):
        PredictionRequest(team1="First", team2=" first ")
    with pytest.raises(ValidationError):
        PredictionRequest(team1="First", team2="Second", team1_stats={"possession": 60})
    with pytest.raises(ValidationError):
        TournamentRequest(teams=["a", "b", "c", "c"])


@pytest.mark.parametrize(
    "values", [{"shots": -1}, {"red_cards": 12}, {"possession": 101}, {"extra": 1}]
)
def test_engine_stats_rejections(values):
    with pytest.raises(ValidationError):
        TeamStats(**values)
