"""Saved-input translation independently of PredictionService orchestration."""

from datetime import UTC, datetime

import pytest

from football import scenario_prediction as adapter
from football.report import report
from schemas.engine import TeamStats
from schemas.prediction import PredictionInputs


@pytest.fixture
def adapter_inputs(scenario_body):
    return PredictionInputs(
        **{
            **scenario_body,
            "scenario_id": 7,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "team1_name": "Alpha",
            "team2_name": "Beta",
            "team1_modifier_total": -7,
            "team2_modifier_total": 0,
            "team1_shots": 1,
            "team1_shots_on_target": 3,
        }
    )


def test_adapter_translates_all_team_fields_and_preserves_report(monkeypatch, adapter_inputs):
    observed = []
    expected = {"probabilities": {"team1": 0.4, "draw": 0.3, "team2": 0.3}, "model": "reference"}

    def inspect_match(match):
        observed.append(match)
        for side, team in enumerate((match.team1, match.team2), 1):
            prefix = f"team{side}_"
            for field in (
                "name",
                "offense",
                "defense",
                "form",
                "star_power",
                "clutch",
                "fifa_rank",
            ):
                assert getattr(team, field) == getattr(adapter_inputs, prefix + field)
            for field in TeamStats.model_fields:
                if field != "modifiers":
                    assert getattr(team, field) == getattr(adapter_inputs, prefix + field)
        assert match.team1.modifiers == [("Saved scenario modifier total", -7.0)]
        assert match.team2.modifiers == []
        assert match.match_minute == 65
        assert match.match_extra_minute == 0 and match.match_status_short == ""
        return expected

    original = adapter_inputs.model_dump()
    monkeypatch.setattr(adapter, "report", inspect_match)
    assert adapter.predict_inputs(adapter_inputs) is expected
    assert len(observed) == 1
    # The adapter copies validated inputs; service normalization is not repeated here.
    assert adapter_inputs.model_dump() == original


@pytest.mark.parametrize("minute,total", [(0, -3000), (120, 3000)])
def test_boundary_inputs_keep_real_engine_probabilities_and_metadata(
    adapter_inputs, minute, total, monkeypatch
):
    inputs = PredictionInputs.model_validate(
        {**adapter_inputs.model_dump(), "match_minute": minute, "team1_modifier_total": total}
    )
    reports = []

    def measured(match):
        output = report(match)
        reports.append(output)
        return output

    monkeypatch.setattr(adapter, "report", measured)
    output = adapter.predict_inputs(inputs)
    assert output is reports[0]
    assert output["model"] == "road-to-the-final-heuristic-v1"
    assert sum(output["probabilities"].values()) == pytest.approx(1, abs=1e-9)
    assert all(0 <= p <= 1 for p in output["probabilities"].values())
    assert output["team1"] == "Alpha" and output["team2"] == "Beta"


def test_engine_failure_propagates_without_mutating_inputs(monkeypatch, adapter_inputs):
    before = adapter_inputs.model_dump()

    def fail(match):
        raise RuntimeError("engine unavailable")

    monkeypatch.setattr(adapter, "report", fail)
    with pytest.raises(RuntimeError, match="engine unavailable"):
        adapter.predict_inputs(adapter_inputs)
    assert adapter_inputs.model_dump() == before
