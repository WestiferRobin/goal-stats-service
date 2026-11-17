import pytest
from pydantic import ValidationError

from schemas.prediction import PredictionHistoryQuery
from schemas.prediction.request import PredictionPreview


def test_history_defaults():
    assert PredictionHistoryQuery().model_dump() == {"limit": 50, "offset": 0}


def test_preview_requires_explicit_ratings_and_distinct_ids(scenario_body):
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    assert PredictionPreview(**body).team1_offense == 70
    for changes in [
        {"team2_id": 1},
        {"team1_id": "1"},
        {"team1_offense": None},
        {"team1_offense": 101},
        {"team1_possession": 60},
    ]:
        with pytest.raises(ValidationError):
            PredictionPreview(**{**body, **changes})
    del body["team1_offense"]
    with pytest.raises(ValidationError):
        PredictionPreview(**body)


@pytest.mark.parametrize("minute", [0, 45, 89, 90, 91, 105, 120])
def test_preview_preserves_time_metadata_and_shot_normalization_compatibility(
    scenario_body, minute
):
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    request = PredictionPreview(
        **{
            **body,
            "match_minute": minute,
            "extra_minute": 30,
            "status": "arbitrary",
            "team1_shots": 0,
            "team1_shots_on_target": 4,
        }
    )
    assert (request.match_minute, request.extra_minute, request.status) == (minute, 30, "arbitrary")
    # Request validation still accepts this combination; computation normalizes a copy.
    assert request.team1_shots == 0 and request.team1_shots_on_target == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"match_minute": -1},
        {"match_minute": 121},
        {"match_minute": 1.5},
        {"extra_minute": 31},
        {"status": "x" * 11},
        {"unknown": 1},
    ],
)
def test_preview_preserves_invalid_input_rejections(scenario_body, changes):
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    with pytest.raises(ValidationError):
        PredictionPreview(**{**body, **changes})
