import pytest
from pydantic import ValidationError

from schemas.scenario import ScenarioCreate, ScenarioPatch, ScenarioState


def test_scenario_partial_patch_combines_before_state_validation(scenario_body):
    row = ScenarioCreate(**scenario_body)
    patch = ScenarioPatch(team1_possession=60)
    assert patch.model_dump(exclude_unset=True) == {"team1_possession": 60}
    state = {name: getattr(row, name) for name in ScenarioState.model_fields}
    with pytest.raises(ValidationError):
        ScenarioState(**{**state, **patch.model_dump(exclude_unset=True)})
    assert (
        ScenarioState(**{**state, "team1_possession": 60, "team2_possession": 40}).team1_possession
        == 60
    )
