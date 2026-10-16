"""Scenario response inheritance and serialization without service orchestration."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.scenario import ScenarioCreate, ScenarioResponse, ScenariosResponse


@pytest.fixture
def scenario_response_data(scenario_body):
    return {
        **scenario_body,
        "scenario_id": 4,
        "created_at": "2026-01-01T00:00:00Z",
        "team1_name": "Alpha",
        "team2_name": "Beta",
    }


@pytest.mark.parametrize("match_id", [None, 7])
def test_inherited_fields_optional_reference_and_json_roundtrip(scenario_response_data, match_id):
    model = ScenarioResponse(**{**scenario_response_data, "match_id": match_id, "title": None})
    assert isinstance(model, ScenarioCreate)
    assert model.match_id == match_id and model.title is None
    assert model.team1_fifa_rank is None and model.team2_fifa_rank is None
    assert model.team1_name == "Alpha" and model.team2_name == "Beta"
    assert model.prediction_ready is True
    assert model.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    payload = model.model_dump(mode="json")
    assert payload["created_at"] == "2026-01-01T00:00:00Z"
    assert payload["team1_modifier_total"] == 0
    wrapper = ScenariosResponse([model])
    assert wrapper.model_dump(mode="json") == [payload]
    assert ScenariosResponse.model_validate_json(wrapper.model_dump_json()) == wrapper


@pytest.mark.parametrize(
    "missing", ["scenario_id", "created_at", "team1_name", "team2_name", "team1_offense"]
)
def test_required_response_and_inherited_fields(scenario_response_data, missing):
    del scenario_response_data[missing]
    with pytest.raises(ValidationError) as caught:
        ScenarioResponse(**scenario_response_data)
    assert any(e["loc"] == (missing,) and e["type"] == "missing" for e in caught.value.errors())


@pytest.mark.parametrize(
    "change",
    [
        {"created_at": "invalid"},
        {"team1_name": None},
        {"prediction_ready": False},
        {"team2_id": 1},
        {"match_id": 0},
        {"team1_goals": "1"},
        {"team1_possession": 60},
        {"unexpected": True},
    ],
)
def test_response_preserves_inherited_and_response_validation(scenario_response_data, change):
    with pytest.raises(ValidationError):
        ScenarioResponse(**{**scenario_response_data, **change})
