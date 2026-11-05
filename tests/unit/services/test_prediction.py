import json
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from werkzeug.exceptions import NotFound

from football.scenario_prediction import predict_inputs
from models.prediction import Prediction
from schemas.prediction import PredictionHistoryQuery
from services import prediction

# Frozen pre-v2 HTTP response, captured before updating router_contract.json.
# Only nondeterministic timestamps were replaced; never calculate this fixture.
FROZEN_V1_PREDICTION = json.loads("""
{
  "generated_at": "2026-01-01T00:00:00Z",
  "input_snapshot": {
    "adapter_version": "scenario-v1",
    "created_at": "2026-01-01T00:00:00Z",
    "extra_minute": 0,
    "match_id": null,
    "match_minute": 65,
    "prediction_ready": true,
    "scenario_id": 1,
    "status": "",
    "team1_big_chances": 0,
    "team1_clutch": 70,
    "team1_corners": 0,
    "team1_defender_blocks": 0,
    "team1_defense": 70,
    "team1_fifa_rank": null,
    "team1_form": 70,
    "team1_goalkeeper_saves": 0,
    "team1_goals": 0,
    "team1_id": 1,
    "team1_modifier_total": 0,
    "team1_name": "First",
    "team1_offense": 70,
    "team1_possession": 50,
    "team1_red_cards": 0,
    "team1_shots": 0,
    "team1_shots_on_target": 0,
    "team1_star_power": 70,
    "team1_yellow_cards": 0,
    "team2_big_chances": 0,
    "team2_clutch": 70,
    "team2_corners": 0,
    "team2_defender_blocks": 0,
    "team2_defense": 70,
    "team2_fifa_rank": null,
    "team2_form": 70,
    "team2_goalkeeper_saves": 0,
    "team2_goals": 0,
    "team2_id": 2,
    "team2_modifier_total": 0,
    "team2_name": "Second",
    "team2_offense": 70,
    "team2_possession": 50,
    "team2_red_cards": 0,
    "team2_shots": 0,
    "team2_shots_on_target": 0,
    "team2_star_power": 70,
    "team2_yellow_cards": 0,
    "title": "Synthetic scenario fixture"
  },
  "model_version": "road-to-the-final-heuristic-v1",
  "output": {
    "advancement": {
      "team1": 0.5,
      "team2": 0.5
    },
    "confidence": {
      "label": "Medium",
      "percent": 40.83102401748909
    },
    "expected_goals_remaining": {
      "team1": 0.36111111111111116,
      "team2": 0.36111111111111116
    },
    "minute": 65,
    "model": "road-to-the-final-heuristic-v1",
    "momentum_percent": {
      "team1": 50,
      "team2": 50
    },
    "most_likely_score": [
      0,
      0
    ],
    "probabilities": {
      "draw": 0.5510987947599418,
      "team1": 0.22445060262002908,
      "team2": 0.22445060262002908
    },
    "reasoning": [
      "The model is calculating remaining goals from minute 65."
    ],
    "status": "",
    "team1": "First",
    "team2": "Second",
    "top_scorelines": [
      {
        "probability": 0.4856717852479504,
        "team1_goals": 0,
        "team2_goals": 0
      },
      {
        "probability": 0.17538147800620432,
        "team1_goals": 0,
        "team2_goals": 1
      },
      {
        "probability": 0.17538147800620432,
        "team1_goals": 1,
        "team2_goals": 0
      },
      {
        "probability": 0.06333220039112934,
        "team1_goals": 1,
        "team2_goals": 1
      },
      {
        "probability": 0.03166610019556467,
        "team1_goals": 0,
        "team2_goals": 2
      }
    ]
  },
  "prediction_id": 1,
  "scenario_id": 1
}
""")


def frozen_v1_row(scenario_id):
    """Build an old stored row without invoking any prediction calculation."""
    expected = deepcopy(FROZEN_V1_PREDICTION)
    expected["scenario_id"] = expected["input_snapshot"]["scenario_id"] = scenario_id
    output = expected["output"]
    excluded = {
        "team1",
        "team2",
        "minute",
        "status",
        "model",
        "probabilities",
        "expected_goals_remaining",
        "most_likely_score",
    }
    row = Prediction(
        scenario_id=scenario_id,
        generated_at=datetime.fromisoformat(expected["generated_at"]),
        model_version=expected["model_version"],
        input_snapshot=deepcopy(expected["input_snapshot"]),
        details={key: deepcopy(value) for key, value in output.items() if key not in excluded},
        team1_win_probability=output["probabilities"]["team1"],
        draw_probability=output["probabilities"]["draw"],
        team2_win_probability=output["probabilities"]["team2"],
        team1_expected_remaining_goals=output["expected_goals_remaining"]["team1"],
        team2_expected_remaining_goals=output["expected_goals_remaining"]["team2"],
        most_likely_team1_score=output["most_likely_score"][0],
        most_likely_team2_score=output["most_likely_score"][1],
    )
    return expected, row


def setup(context, projection):
    saved = []

    def require_exists(*, scenario_id):
        if scenario_id != 7:
            raise NotFound()

    def capture(*, scenario_id):
        require_exists(scenario_id=scenario_id)
        return {
            **{
                column.name: getattr(projection.scenario, column.name)
                for column in projection.scenario.__table__.columns
            },
            "team1_name": projection.team1_name,
            "team2_name": projection.team2_name,
        }

    context.service(
        "ScenarioService",
        SimpleNamespace(
            capture_state_in_transaction=capture,
            require_exists_in_transaction=require_exists,
        ),
    )

    def add(row):
        row.prediction_id = len(saved) + 1
        row.generated_at = projection.scenario.created_at
        saved.append(row)

    history = Mock(
        side_effect=lambda identity, **kw: list(reversed(saved))[
            kw["offset"] : kw["offset"] + kw["limit"]
        ]
    )
    context.repository(
        "PredictionRepository",
        SimpleNamespace(
            add=add,
            get_by_id=lambda identity: next(
                (r for r in saved if r.prediction_id == identity), None
            ),
            history=history,
        ),
    )
    return (
        prediction.PredictionService(
            repo=context.repositories["PredictionRepository"],
            scenario_service=context.services["ScenarioService"],
            team_service=SimpleNamespace(
                database=context.repositories["PredictionRepository"].database
            ),
        ),
        saved,
        history,
    )


def test_prediction_capture_compute_append_and_saved_retrieval(
    service_context, scenario_projection, monkeypatch
):
    service, saved, history = setup(service_context, scenario_projection)
    scenario_projection.scenario.team1_shots = 0
    scenario_projection.scenario.team1_shots_on_target = 3
    outputs = []

    def compute(inputs):
        assert not service_context.state.active
        assert service_context.events[-1] == "commit"
        assert inputs.team1_shots == 3
        assert scenario_projection.scenario.team1_shots == 0
        output = predict_inputs(inputs)
        outputs.append(output)
        return output

    monkeypatch.setattr(prediction, "predict_inputs", compute)
    result = service.generate(7)
    assert result["output"] == outputs[0]
    assert service_context.events == ["begin", "commit", "begin", "commit"]
    original = deepcopy(result)
    scenario_projection.scenario.team1_offense = 99
    result2 = service.generate(7)
    assert result2["prediction_id"] != result["prediction_id"]

    def forbidden(inputs):
        pytest.fail("Retrieval recalculated a prediction")

    monkeypatch.setattr(prediction, "predict_inputs", forbidden)
    assert service.get(1) == original
    assert saved[0].input_snapshot["team1_offense"] == 70
    assert service.history(7, PredictionHistoryQuery(limit=1, offset=1)) == [original]
    history.assert_called_once_with(7, limit=1, offset=1)
    with pytest.raises(NotFound):
        service.get(999)
    with pytest.raises(NotFound):
        service.history(999, PredictionHistoryQuery())


@pytest.mark.parametrize("failure", ["invalid", "identity", "engine"])
def test_prediction_failure_never_opens_write_transaction(
    service_context, scenario_projection, monkeypatch, failure
):
    service, saved, _ = setup(service_context, scenario_projection)

    def compute(inputs):
        assert not service_context.state.active
        if failure == "engine":
            raise RuntimeError("calculation failed")
        output = predict_inputs(inputs)
        if failure == "invalid":
            output["probabilities"]["team1"] = 2
        else:
            output["team1"] = "different team"
        return output

    monkeypatch.setattr(prediction, "predict_inputs", compute)
    with pytest.raises(prediction.PredictionGenerationError):
        service.generate(7)
    assert saved == []
    assert service_context.events == ["begin", "commit"]


def test_frozen_v1_and_v2_coexist_without_recalculation(
    service_context, scenario_projection, monkeypatch
):
    service, saved, _ = setup(service_context, scenario_projection)
    expected, row = frozen_v1_row(7)
    row.prediction_id = expected["prediction_id"]
    saved.append(row)
    generated = service.generate(7)
    assert generated["prediction_id"] == 2
    assert (
        generated["model_version"]
        == generated["output"]["model"]
        == ("road-to-the-final-heuristic-v2")
    )
    assert generated["input_snapshot"]["adapter_version"] == "scenario-v1"
    assert generated["input_snapshot"]["extra_minute"] == 0
    assert generated["input_snapshot"]["status"] == ""

    def forbidden(*args, **kwargs):
        pytest.fail("Reading old or new predictions must not invoke the engine")

    monkeypatch.setattr(prediction, "predict_inputs", forbidden)
    monkeypatch.setattr(prediction, "predict_state", forbidden)
    monkeypatch.setattr("football.engine.Match.calculate_probabilities", forbidden)
    assert service.get(1) == expected
    assert service.get(2) == generated
    assert service.history(7, PredictionHistoryQuery()) == [generated, expected]
    assert service.history(7, PredictionHistoryQuery(limit=1, offset=1)) == [expected]
    assert row.input_snapshot == expected["input_snapshot"]


@pytest.mark.parametrize("minute", [0, 45, 89, 90, 91, 105, 120])
def test_preview_generation_v2_parity_without_scenario_mutation(
    service_context, scenario_projection, scenario_body, minute
):
    from schemas.prediction.request import PredictionPreview

    service, saved, _ = setup(service_context, scenario_projection)
    service.team_service.capture_names_in_transaction = lambda **kwargs: {1: "First", 2: "Second"}
    scenario_projection.scenario.match_minute = minute
    scenario_projection.scenario.team1_shots_on_target = 4
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    body.update(match_minute=minute, team1_shots_on_target=4)
    preview = service.preview(PredictionPreview(**body))
    assert saved == []
    generated = service.generate(7)
    assert len(saved) == 1
    assert generated["output"] == preview
    assert preview["model"] == "road-to-the-final-heuristic-v2"
    assert preview["minute"] == minute
    assert generated["input_snapshot"]["team1_shots"] == 4
    assert scenario_projection.scenario.team1_shots == 0
    if minute >= 90:
        assert preview["expected_goals_remaining"] == {"team1": 0, "team2": 0}
        assert preview["probabilities"] == {"team1": 0, "draw": 1, "team2": 0}


def test_prediction_missing_or_invalid_scenario(service_context, scenario_projection):
    service, saved, _ = setup(service_context, scenario_projection)
    with pytest.raises(NotFound):
        service.generate(999)
    scenario_projection.scenario.team1_offense = None
    with pytest.raises(prediction.ScenarioNotReady):
        service.generate(7)
    assert saved == []


def test_prediction_rejects_mismatched_database_dependencies():
    with pytest.raises(ValueError, match="same Database"):
        prediction.PredictionService(
            repo=SimpleNamespace(database=object()),
            scenario_service=SimpleNamespace(database=object()),
            team_service=SimpleNamespace(database=object()),
        )


def test_preview_captures_ids_then_computes_without_writes(
    service_context, scenario_projection, scenario_body, monkeypatch
):
    from football.scenario_prediction import predict_state
    from schemas.prediction.request import PredictionPreview

    service, saved, _ = setup(service_context, scenario_projection)

    def names(*, session, team_ids):
        assert service_context.state.active and team_ids == (1, 2)
        return {1: "Spain", 2: "England"}

    service.team_service.capture_names_in_transaction = names

    def calculate(values, **kwargs):
        assert not service_context.state.active
        assert values["team1_name"] == "Spain"
        assert values["team1_shots"] == 4
        return predict_state(values, **kwargs)

    monkeypatch.setattr(prediction, "predict_state", calculate)
    body = {k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}}
    body["team1_shots_on_target"] = 4
    result = service.preview(PredictionPreview(**body))
    assert result["team1"] == "Spain" and saved == []
    assert service_context.events == ["begin", "commit"]
