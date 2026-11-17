"""Pinned research replay approval boundary, scoring gates and provenance."""

import shutil
from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from football.evaluation import CLASSES, metrics
from schemas.evaluation.request import FULL_DATASET, BacktestRequest
from services import evaluation_research as research
from services.evaluation import EvaluationError, EvaluationService
from tests.unit.services.test_evaluation_full import repository


def request(**changes):
    return BacktestRequest.model_validate(
        {
            "dataset_id": FULL_DATASET,
            "recovery_package_id": "international-results-recovery-v1",
            "prediction_model_version": research.MODELS[1],
            "mode": "retrospective_replay",
            "limit": 348,
            **changes,
        }
    )


@pytest.mark.parametrize("model,count", list(zip(research.MODELS, (320, 320, 200), strict=True)))
def test_real_pinned_replay_matches_offline_research(model, count):
    data, rows, reports = research.assets()
    result = EvaluationService(repository()).evaluate(request(prediction_model_version=model))
    assert result["eligible_matches"] == count
    assert len(result["cases"]) == 348
    assert result["prediction_model_version"] == model
    assert result["metrics_horizon_minutes"] == 90
    scored = [
        (r["predictions"][model], CLASSES[r["truth"]])
        for r in data["cases"]
        if model in r["predictions"]
    ]
    for key, value in metrics(scored).items():
        assert result[key] == value
    for case in result["cases"]:
        row = rows[case["match_key"]]
        if case["status"] == "eligible":
            assert case["probabilities"] == pytest.approx(row["predictions"][model], abs=1e-15)
            assert case["input_manifest"]["production_eligible"] is False
        else:
            assert case["probabilities"] is None
    assert result["research_validation"]["comparisons"] == reports["results"]["all_exploratory"]
    assert [s["total"] for s in result["edition_summaries"]] == [26, 26, 32, 32, 32, 32, 52, 52, 64]


def test_strict_research_stays_excluded_without_publishing_replay_metrics():
    result = EvaluationService(repository()).evaluate(request(mode="strict_historical"))
    assert result["eligible_matches"] == 0 and result["accuracy"] is None
    assert result["exclusion_reasons"]["historical_source_availability_unverified"] == 348
    assert result["research_validation"]["comparisons"] == {}
    assert result["research_validation"]["period_comparisons"] == {}
    assert "historical_star_power_clutch_evidence_missing" not in result["exclusion_reasons"]


@pytest.mark.parametrize(
    "changes",
    [
        {"recovery_package_id": None},
        {"dataset_id": "womens-world-cup-recorded-v1"},
        {"mode": "retrospective_assumptions", "assumption_package_id": "fake"},
        {"prediction_model_version": "unknown"},
        {"prediction_model_version": "road-to-the-final-heuristic-v2"},
        {"assumption_package_id": "fake"},
    ],
)
def test_invalid_research_selection(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_unavailable_and_corrupt_sources_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "ROOT", tmp_path)
    with pytest.raises(EvaluationError):
        EvaluationService(repository()).evaluate(request())
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest checksum"):
        research.assets()


def test_pinned_artifact_tampering_rejected(tmp_path, monkeypatch):
    shutil.copytree(research.ROOT, tmp_path / "research")
    monkeypatch.setattr(research, "ROOT", tmp_path / "research")
    (research.ROOT / "predictions.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact checksum"):
        research.assets()


@pytest.mark.parametrize(
    "field,value",
    [("cutoff", "2099-01-01"), ("home", "other"), ("source_population_hash", "0" * 64)],
)
def test_service_rejects_mismatched_case_provenance(field, value, monkeypatch):
    data, rows, results = research.assets()
    rows = deepcopy(rows)
    next(iter(rows.values()))[field] = value
    monkeypatch.setattr(research, "assets", lambda: (data, rows, results))
    with pytest.raises(EvaluationError, match="provenance"):
        EvaluationService(repository()).evaluate(request())


def test_future_rank_cannot_rescue_or_score_research():
    repo = repository()
    repo.rank_day = date(2099, 1, 1)
    result = EvaluationService(repo).evaluate(request(edition=2023, limit=1))
    assert result["eligible_matches"] == 0
    assert "ranking_cutoff_violation" in result["cases"][0]["exclusion_reasons"]


def test_duration_and_calibration_boundaries():
    service = EvaluationService(repository())
    r = service.evaluate(
        request(edition=1991, research_model_version="odf-exposure-80-evidence-blocked-v1")
    )
    assert r["excluded_matches"] == 26 and r["accuracy"] is None
    assert r["research_validation"]["calibration"] is None
    assert all(c["evidence_record"]["research"]["eligible"] is False for c in r["cases"])
    r = service.evaluate(request(edition=2007, prediction_model_version=research.MODELS[2]))
    assert r["excluded_matches"] == 32
    assert r["exclusion_reasons"]["calibration_not_available_before_match"] == 32


@pytest.mark.parametrize(
    "corruption", ["duplicate", "cutoff", "production", "horizon", "calibration", "truth"]
)
def test_research_semantic_guards_even_after_approval_boundary(corruption, monkeypatch):
    import json

    original = json.loads

    def load(raw):
        value = original(raw)
        if isinstance(value.get("cases"), list):
            row = next(r for r in value["cases"] if research.MODELS[2] in r["predictions"])
            if corruption == "duplicate":
                value["cases"].append(value["cases"][0])
            elif corruption == "cutoff":
                row["cutoff"] = row["date"]
            elif corruption == "production":
                row["production_eligible"] = True
            elif corruption == "horizon":
                row["horizon_minutes"] = 80
            elif corruption == "calibration":
                row["edition"] = 2007
            else:
                row["truth"] = 5
        return value

    monkeypatch.setattr(research.json, "loads", load)
    with pytest.raises(ValueError):
        research.assets()
