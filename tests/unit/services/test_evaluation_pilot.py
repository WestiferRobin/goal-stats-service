"""Evidence and fail-closed boundaries; numerical assumptions below are test-only."""

import hashlib
import json
from dataclasses import asdict, replace
from datetime import date

import pytest
from pydantic import ValidationError

from exceptions.base import EvaluationAssetUnavailable
from schemas.evaluation.request import PILOT_DATASET, BacktestRequest
from services.evaluation import EvaluationError, EvaluationPackage, EvaluationService, digest
from services.evaluation_pilot import MANIFEST_SHA256, ROOT, load_pilot, verified_json
from tests.unit.services.test_evaluation import CASE, LABEL, FakeRepository, package, request


def test_official_evidence_identity_and_hash_chain():
    pilot = load_pilot()
    assert pilot.expected_matches == 348 and len(pilot.match_keys) == 2
    assert pilot.strengths == {} and not pilot.historical_availability_verified
    assert pilot.provenance["manifest_sha256"] == MANIFEST_SHA256
    assert hashlib.sha256((ROOT / "manifest.json").read_bytes()).hexdigest() == MANIFEST_SHA256
    assert [
        (label.day, label.home, label.away, label.home_score, label.away_score)
        for label in pilot.labels.values()
    ] == [
        (date(2023, 7, 20), "New Zealand", "Norway", 1, 0),
        (date(2023, 7, 20), "Australia", "Republic of Ireland", 1, 0),
    ]
    for number, label in enumerate(pilot.labels.values(), 1):
        assert label.regulation_minutes == 90 and label.completion_status == "completed"
        assert label.provenance["fifa_match_number"] == number
        assert label.provenance["stage"] == "group"
        assert label.provenance["extra_time_played"] is False
        assert label.provenance["penalty_shootout_played"] is False
        assert label.source_hash == label.provenance["source_sha256"]
    assert load_pilot().hash == pilot.hash
    assert (
        EvaluationPackage().hash
        == "d54d4ec50a8f110a4babba9365316093887974a17fd2199d26ecb2bfb05f7d82"
    )


@pytest.mark.parametrize(
    "filename", ["manifest.json", "regulations-evidence.json", "rating-reconstruction.json"]
)
def test_tampered_evidence_fails_closed(tmp_path, monkeypatch, filename):
    for path in ROOT.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    with (tmp_path / filename).open("ab") as output:
        output.write(b" ")
    monkeypatch.setattr("services.evaluation_pilot.ROOT", tmp_path)
    with pytest.raises(EvaluationAssetUnavailable):
        EvaluationService(FakeRepository()).evaluate(BacktestRequest(dataset_id=PILOT_DATASET))


def test_evidence_requires_object(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        verified_json(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"regulation_minutes": 80}, "regulation_duration_incompatible"),
        ({"regulation_minutes": None}, "regulation_duration_incompatible"),
        ({"completion_status": "abandoned"}, "match_completion_unverified"),
        ({"completion_status": None}, "match_completion_unverified"),
    ],
)
def test_duration_and_completion_exclude_before_calculation(changes, reason):
    result = EvaluationService(FakeRepository(), package())
    # Construct directly because the shared helper already supplies labels.
    result.package = replace(package(), labels={"a" * 64: replace(LABEL, **changes)})
    assert reason in result.evaluate(request())["exclusion_reasons"]


def pilot_catalog():
    pilot = load_pilot()
    cases = [
        replace(
            CASE,
            match_id=i + 1,
            match_key=f"{i:064x}",
            source_version="1855e313ae8bcd0330426e62c8e4cf15ce45077c",
        )
        for i in range(348)
    ]
    for index, (key, label) in enumerate(pilot.labels.items()):
        cases[index] = replace(
            cases[index],
            match_key=key,
            day=label.day,
            home=label.home,
            away=label.away,
            source_home=label.home,
            source_away=label.away,
        )
    projection = [
        {k: v for k, v in asdict(c).items() if k not in {"match_id", "home_id", "away_id"}}
        for c in cases
    ]
    # Synthetic catalog fixture explicitly replaces only the catalog fingerprint.
    return cases, replace(
        pilot, provenance={**pilot.provenance, "expected_dataset_hash": digest(projection)}
    )


def test_pilot_cohort_is_selected_after_full_catalog_validation():
    cases, pilot = pilot_catalog()
    service = EvaluationService(FakeRepository(cases), pilot)
    body = BacktestRequest(dataset_id=PILOT_DATASET, limit=2)
    strict = service.evaluate(body)
    assert strict["dataset_match_count"] == 348 and strict["cohort_match_count"] == 2
    assert strict["total_candidate_matches"] == 2 and strict["eligible_matches"] == 0
    assert strict["exclusion_reasons"] == {
        "historical_star_power_clutch_evidence_missing": 2,
        "historical_source_availability_unverified": 2,
    }
    retrospective = service.evaluate(
        BacktestRequest(
            dataset_id=PILOT_DATASET,
            limit=2,
            mode="retrospective_assumptions",
            assumption_package_id="test-only-empty",
        )
    )
    assert retrospective["exclusion_reasons"] == {
        "explicit_star_power_clutch_assumptions_missing": 2
    }
    assert retrospective["accuracy"] is None
    empty = service.evaluate(BacktestRequest(dataset_id=PILOT_DATASET, offset=2))
    assert empty["cases"] == [] and empty["dataset_match_count"] == 348
    for bad in [
        cases[:-1],
        [*cases, CASE],
        [cases[0]] * 348,
        [replace(cases[0], match_key="f" * 64), *cases[1:]],
        [*cases[:-1], replace(cases[-1], source_hash="f" * 64)],
        [*cases[:-1], replace(cases[-1], recorded_home=999)],
    ]:
        with pytest.raises(EvaluationError):
            EvaluationService(FakeRepository(bad), pilot).evaluate(body)


@pytest.mark.parametrize(
    "changes",
    [
        {"star_power": float("nan")},
        {"star_power": float("inf")},
        {"clutch": -1},
        {"clutch": 101},
        {"star_power": None},
    ],
)
def test_pilot_assumptions_reject_invalid_values(changes):
    with pytest.raises(ValidationError):
        BacktestRequest(
            dataset_id=PILOT_DATASET,
            mode="retrospective_assumptions",
            assumption_package_id="test-only",
            assumptions=[
                {"match_key": "a" * 64, "team_id": 1, "star_power": 0, "clutch": 25, **changes}
            ],
        )


def test_unsupported_package_and_pilot_requires_named_assumptions():
    from services.evaluation import approved_package

    with pytest.raises(EvaluationError):
        approved_package("unapproved")
    with pytest.raises(ValidationError):
        BacktestRequest(dataset_id=PILOT_DATASET, mode="retrospective_assumptions")


def test_reviewed_rating_artifact_has_no_special_assumptions():
    artifact = json.loads((ROOT / "rating-reconstruction.json").read_text())
    assert artifact["cutoff"] == "2023-07-19"
    assert artifact["source_rows_before_cutoff"] == 9416
    assert artifact["latest_source_day"] < "2023-07-20"
    for rating in artifact["ratings"].values():
        assert "star_power" not in rating and "clutch" not in rating
