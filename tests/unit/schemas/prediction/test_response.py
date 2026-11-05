from copy import deepcopy

import pytest
from pydantic import ValidationError

from schemas.prediction import ExpectedGoals, ValidProbabilities
from schemas.prediction.response import SavedPredictionResponse
from tests.unit.services.test_prediction import FROZEN_V1_PREDICTION


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


@pytest.mark.parametrize(
    "version", ["road-to-the-final-heuristic-v1", "road-to-the-final-heuristic-v2"]
)
def test_saved_response_accepts_versions_with_unchanged_snapshot_contract(version):
    # Change only a synthetic identifier to test the schema, not numerical correctness.
    value = deepcopy(FROZEN_V1_PREDICTION)
    value["model_version"] = value["output"]["model"] = version
    response = SavedPredictionResponse.model_validate(value).model_dump(mode="json")
    assert response == value
    assert response["input_snapshot"]["adapter_version"] == "scenario-v1"
    assert response["input_snapshot"]["status"] == ""
    assert response["input_snapshot"]["extra_minute"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"adapter_version": "scenario-v2"},
        {"status": "FT"},
        {"extra_minute": 1},
    ],
)
def test_saved_snapshot_defaults_are_not_expanded(changes):
    value = deepcopy(FROZEN_V1_PREDICTION)
    value["input_snapshot"].update(changes)
    with pytest.raises(ValidationError):
        SavedPredictionResponse.model_validate(value)
