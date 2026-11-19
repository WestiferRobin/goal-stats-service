import pytest
from pydantic import ValidationError

from schemas.prediction.request import PredictionPreview
from schemas.scenario import ScenarioCreate, ScenarioPatch, ScenarioResponse


@pytest.mark.parametrize("schema", [ScenarioCreate, PredictionPreview])
@pytest.mark.parametrize("side", [1, 2])
@pytest.mark.parametrize(
    "shots,target,valid",
    [(0, 4, False), (4, 4, True), (4, 0, True), (0, 0, True), (-1, 0, False), (4, -1, False)],
)
def test_shot_relationship(schema, side, shots, target, valid, scenario_body):
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    body.update({f"team{side}_shots": shots, f"team{side}_shots_on_target": target})
    if valid:
        assert schema(**body).model_dump()[f"team{side}_shots"] == shots
    else:
        with pytest.raises(ValidationError) as caught:
            schema(**body)
        assert caught.value.errors()[0]["loc"][0].startswith(f"team{side}_")


@pytest.mark.parametrize(
    "first,second,valid", [(0, 100, True), (100, 0, True), (-1, 101, False), (101, -1, False)]
)
def test_possession_boundaries_unchanged(first, second, valid, scenario_body):
    body = {**scenario_body, "team1_possession": first, "team2_possession": second}
    if valid:
        assert ScenarioCreate(**body).team1_possession == first
    else:
        with pytest.raises(ValidationError):
            ScenarioCreate(**body)


def test_patch_only_compares_supplied_pairs_and_keeps_zero():
    assert ScenarioPatch(team1_shots=0).model_dump(exclude_unset=True) == {"team1_shots": 0}
    assert ScenarioPatch(team1_shots_on_target=4).team1_shots_on_target == 4
    with pytest.raises(ValidationError):
        ScenarioPatch(team1_shots=0, team1_shots_on_target=4)


def test_legacy_scenario_response_is_readable_without_rewriting(scenario_body):
    body = {
        **scenario_body,
        "team1_shots": 0,
        "team1_shots_on_target": 4,
        "scenario_id": 7,
        "created_at": "2026-01-01T00:00:00Z",
        "team1_name": "A",
        "team2_name": "B",
    }
    assert ScenarioResponse(**body).team1_shots == 0
