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
