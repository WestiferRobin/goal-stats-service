from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from werkzeug.exceptions import NotFound

from football.scenario_prediction import predict_inputs
from schemas.prediction import PredictionHistoryQuery
from services import prediction


def setup(context, projection):
    saved = []
    context.bind(
        prediction,
        "ScenarioRepository",
        SimpleNamespace(
            get_projection=lambda identity: projection if identity == 7 else None,
            exists=lambda identity: identity == 7,
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
    context.bind(
        prediction,
        "PredictionRepository",
        SimpleNamespace(
            add=add,
            get_by_id=lambda identity: next(
                (r for r in saved if r.prediction_id == identity), None
            ),
            history=history,
        ),
    )
    return prediction.PredictionService(context.database), saved, history


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
    with pytest.raises((ValidationError, ValueError, RuntimeError)):
        service.generate(7)
    assert saved == []
    assert service_context.events == ["begin", "commit"]


def test_prediction_missing_or_invalid_scenario(service_context, scenario_projection):
    service, saved, _ = setup(service_context, scenario_projection)
    with pytest.raises(NotFound):
        service.generate(999)
    scenario_projection.scenario.team1_offense = None
    with pytest.raises(prediction.ScenarioNotReady):
        service.generate(7)
    assert saved == []
