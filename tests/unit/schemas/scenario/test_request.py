import pytest
from pydantic import ValidationError

from schemas.scenario import ScenarioPatch


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"team1_goals": None},
        {"team1_id": 2},
        {"team1_offense": 80},
        {"team1_goals": "1"},
        {"match_minute": 121},
    ],
)
def test_patch_rejects_null_empty_immutable_and_out_of_range(values):
    with pytest.raises(ValidationError):
        ScenarioPatch(**values)
