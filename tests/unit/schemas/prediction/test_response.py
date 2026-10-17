import pytest
from pydantic import ValidationError

from schemas.prediction import ExpectedGoals, ValidProbabilities


def test_probability_serialization():
    assert ValidProbabilities(team1=0.5, draw=0.25, team2=0.25).model_dump() == {
        "team1": 0.5,
        "draw": 0.25,
        "team2": 0.25,
    }


@pytest.mark.parametrize(
    "values",
    [
        dict(team1=0.6, draw=0.3, team2=0.3),
        dict(team1=-0.1, draw=0.5, team2=0.6),
        dict(team1=float("nan"), draw=0, team2=1),
    ],
)
def test_invalid_saved_probabilities(values):
    with pytest.raises(ValidationError):
        ValidProbabilities(**values)


def test_saved_expected_goals_reject_infinity():
    with pytest.raises(ValidationError):
        ExpectedGoals(team1=float("inf"), team2=0)
