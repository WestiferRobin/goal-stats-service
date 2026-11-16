"""Synthetic observations only; no real historical performance is claimed."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta

import pytest

from football import team_ratings
from infra.repositories.evaluation import HistoricalCase
from schemas.evaluation.request import BacktestRequest
from services.evaluation import (
    EvaluationError,
    EvaluationPackage,
    EvaluationService,
    ObservedStrength,
    RegulationEvidence,
    digest,
)

DAY = date(2020, 6, 10)
KEY = "a" * 64
CASE = HistoricalCase(
    1,
    KEY,
    DAY,
    1,
    2,
    "Alpha",
    "Beta",
    "Alpha",
    "Beta",
    9,
    8,
    "including_extra_time_no_shootout",
    team_ratings.SOURCE_SHA,
    "synthetic",
)
LABEL = RegulationEvidence(DAY, "Alpha", "Beta", 0, 0, "synthetic://regulation", "b" * 64)


class FakeRepository:
    def __init__(self, cases=None):
        self.cases = cases or [CASE]
        self.in_transaction = False
        self.rank_day = None

    @contextmanager
    def transaction(self):
        self.in_transaction = True
        try:
            yield None
        finally:
            self.in_transaction = False

    def candidates(self, session):
        return self.cases

    def ranking(self, session, identity, day):
        assert self.in_transaction
        return {
            "rank": None,
            "reason": "no_pre_match_ranking_release",
            **({"published_on": self.rank_day.isoformat()} if self.rank_day else {}),
        }


def package(**changes):
    return EvaluationPackage(
        evidence_kind="synthetic", expected_matches=1, labels={KEY: LABEL}, **changes
    )


def request(**changes):
    data = dict(
        dataset_id="womens-world-cup-recorded-v1",
        mode="retrospective_assumptions",
        assumption_package_id="synthetic-test-v1",
        assumptions=[dict(match_key=KEY, team_id=i, star_power=0, clutch=25) for i in (1, 2)],
    )
    return BacktestRequest.model_validate({**data, **changes})


@pytest.fixture
def reconstructed(monkeypatch):
    rows = [
        team_ratings.Result(DAY - timedelta(days=n), "Alpha", "Beta", 1, 0, True)
        for n in range(1, 31)
    ]
    rows += [
        team_ratings.Result(DAY, "Alpha", "Beta", 999, 999, True),
        team_ratings.Result(DAY + timedelta(days=1), "Alpha", "Beta", 999, 999, True),
    ]
    monkeypatch.setattr("services.evaluation.approved_source", lambda: rows)
    calls = []

    def calculate(earlier, cutoff):
        assert cutoff == DAY - timedelta(days=1)
        assert all(r.day < DAY for r in earlier)
        calls.append(earlier)
        return {
            n: dict(offense=60, defense=70, form=80, evidence={"matches": 30})
            for n in ["Alpha", "Beta"]
        }

    monkeypatch.setattr(team_ratings, "calculate", calculate)
    return calls


def test_assumptions_evaluate_with_pure_existing_adapter_no_final_state(reconstructed, monkeypatch):
    repo = FakeRepository()
    from services.evaluation import predict_state

    def predict(values):
        assert not repo.in_transaction
        assert values["match_minute"] == 0
        for side in (1, 2):
            assert values[f"team{side}_goals"] == 0
            assert values[f"team{side}_shots"] == 0
            assert values[f"team{side}_possession"] == 50
            assert values[f"team{side}_star_power"] == 0
        return predict_state(values)

    monkeypatch.setattr("services.evaluation.predict_state", predict)
    service = EvaluationService(repo, package())
    result = service.evaluate(request())
    assert result["eligible_matches"] == 1
    assert result["cases"][0]["outcome"] == "draw"  # Recorded 9-8 is never the label.
    assert result["evidence_kind"] == "synthetic"
    assert result["cases"][0]["input_manifest"]["latest_source_day"] == "2020-06-09"
    assert result["prediction_model_version"] == "road-to-the-final-heuristic-v2"
    assert result == service.evaluate(request())
    assert len(reconstructed) == 2


def test_strict_excludes_missing_observations_and_unverified_availability(reconstructed):
    result = EvaluationService(FakeRepository(), package()).evaluate(
        BacktestRequest(dataset_id="womens-world-cup-recorded-v1")
    )
    assert result["eligible_matches"] == 0
    assert result["accuracy"] is None and result["confusion_matrix"] is None
    assert result["exclusion_reasons"] == {
        "historical_source_availability_unverified": 1,
        "historical_star_power_clutch_evidence_missing": 1,
    }
    assert not reconstructed


def test_strict_positive_requires_trusted_evidence(reconstructed):
    observed = ObservedStrength(0, 25, DAY - timedelta(days=1), "synthetic://strength", "c" * 64)
    result = EvaluationService(
        FakeRepository(),
        package(historical_availability_verified=True, strengths={KEY: {1: observed, 2: observed}}),
    ).evaluate(BacktestRequest(dataset_id="womens-world-cup-recorded-v1"))
    assert result["eligible_matches"] == 1 and result["evidence_kind"] == "synthetic"


@pytest.mark.parametrize(
    "label",
    [
        None,
        replace(LABEL, day=DAY + timedelta(days=1)),
        replace(LABEL, home_score=-1),
        replace(LABEL, definition="recorded_final"),
    ],
)
def test_regulation_evidence_cannot_be_inferred_from_final_score(reconstructed, label):
    p = replace(package(), labels={} if label is None else {KEY: label})
    result = EvaluationService(FakeRepository(), p).evaluate(request())
    assert result["eligible_matches"] == 0
    assert result["cases"][0]["probabilities"] is None
    assert not reconstructed


def test_missing_assumptions_future_ranking_and_insufficient_ratings(reconstructed, monkeypatch):
    repo = FakeRepository()
    service = EvaluationService(repo, package())
    result = service.evaluate(request(assumptions=[request().assumptions[0].model_dump()]))
    assert result["exclusion_reasons"] == {"explicit_star_power_clutch_assumptions_missing": 1}
    repo.rank_day = DAY
    assert "ranking_cutoff_violation" in service.evaluate(request())["exclusion_reasons"]
    repo.rank_day = None
    monkeypatch.setattr(team_ratings, "calculate", lambda *args: {})
    assert service.evaluate(request())["exclusion_reasons"] == {
        "historical_ratings_insufficient": 1
    }


def test_unsupported_source_model_and_invalid_probabilities(reconstructed, monkeypatch):
    service = EvaluationService(FakeRepository(), package())
    monkeypatch.setattr("services.evaluation.predict_state", lambda values: {"model": "obsolete"})
    assert service.evaluate(request())["exclusion_reasons"] == {"prediction_model_incompatible": 1}
    monkeypatch.setattr(
        "services.evaluation.predict_state",
        lambda values: {
            "model": "road-to-the-final-heuristic-v2",
            "probabilities": dict(team1=0.5, draw=0.5, team2=0.5),
        },
    )
    assert service.evaluate(request())["eligible_matches"] == 0
    monkeypatch.setattr(
        "services.evaluation.approved_source",
        lambda: (_ for _ in ()).throw(ValueError("private path")),
    )
    result = service.evaluate(request())
    assert "private path" not in str(result)
    assert result["exclusion_reasons"] == {"historical_reconstruction_unavailable": 1}


def test_dataset_and_manifest_identity(reconstructed):
    first = EvaluationService(FakeRepository(), package()).evaluate(request())
    moved = replace(CASE, match_id=999)
    second = EvaluationService(FakeRepository([moved]), package()).evaluate(request())
    assert first["dataset_hash"] == second["dataset_hash"]
    changed = request(assumption_package_id="explicit-v2")
    assert (
        EvaluationService(FakeRepository(), package()).evaluate(changed)["manifest_hash"]
        != first["manifest_hash"]
    )
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    with pytest.raises(EvaluationError):
        EvaluationService(FakeRepository(), replace(package(), expected_matches=2)).evaluate(
            request()
        )


def test_real_rating_logic_filters_future_rows_and_is_repeatable(monkeypatch):
    rows = [
        team_ratings.Result(
            DAY - timedelta(days=n),
            "Alpha" if n % 2 else "Beta",
            "Beta" if n % 2 else "Alpha",
            n % 3,
            1,
            True,
        )
        for n in range(1, 801)
    ]
    monkeypatch.setattr("services.evaluation.approved_source", lambda: rows)
    service = EvaluationService(FakeRepository(), package())
    before = service.evaluate(request())
    assert before["eligible_matches"] == 1
    rows.extend(
        [
            team_ratings.Result(DAY, "Alpha", "Beta", 999, 0, True),
            team_ratings.Result(DAY + timedelta(days=1), "Alpha", "Beta", 999, 0, True),
        ]
    )
    assert service.evaluate(request()) == before


@pytest.mark.parametrize("offset", [0, 1])
def test_strict_observed_strength_must_predate_match(reconstructed, offset):
    observed = ObservedStrength(
        0, 25, DAY + timedelta(days=offset), "synthetic://strength", "c" * 64
    )
    result = EvaluationService(
        FakeRepository(),
        package(historical_availability_verified=True, strengths={KEY: {1: observed, 2: observed}}),
    ).evaluate(BacktestRequest(dataset_id="womens-world-cup-recorded-v1"))
    assert result["eligible_matches"] == 0
    assert result["exclusion_reasons"] == {"historical_star_power_clutch_evidence_missing": 1}


def test_response_rejects_inconsistent_case_and_metrics(reconstructed):
    from copy import deepcopy

    from pydantic import ValidationError

    from schemas.evaluation.response import BacktestResponse

    result = EvaluationService(FakeRepository(), package()).evaluate(request())
    for patch in [
        {"eligible_matches": 0},
        {"accuracy": None},
        {"confusion_matrix": [[0]]},
        {"class_order": ["away_win", "draw", "home_win"]},
    ]:
        with pytest.raises(ValidationError):
            BacktestResponse.model_validate({**result, **patch})
    for patch in [
        {"cutoff": DAY.isoformat()},
        {"probabilities": [0.6, 0.6, 0]},
        {"outcome": None},
        {"exclusion_reasons": ["missing"]},
    ]:
        invalid = deepcopy(result)
        invalid["cases"][0].update(patch)
        with pytest.raises(ValidationError):
            BacktestResponse.model_validate(invalid)
