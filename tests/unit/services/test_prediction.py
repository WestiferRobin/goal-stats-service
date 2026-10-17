from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from werkzeug.exceptions import NotFound

from football.scenario_prediction import predict_inputs
from schemas.prediction import PredictionHistoryQuery
from services import prediction


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
