"""Recovery approval boundaries, original preservation, and deterministic full-cohort replay."""

import copy
import hashlib
import json
from dataclasses import replace
from datetime import date

import pytest
from pydantic import ValidationError

from football import results_recovery as recovery
from football import team_ratings
from schemas.evaluation.request import FULL_DATASET, PILOT_DATASET, BacktestRequest
from services.evaluation import EvaluationError, EvaluationService, approved_source, digest
from services.evaluation_full import assets as original_assets
from services.evaluation_recovery import assets
from tests.unit.services.test_evaluation_full import repository


def test_approved_merge_preserves_every_original_and_rejects_reverse_duplicates():
    original = approved_source()
    saved = original.copy()
    overlay = recovery.load_overlay()
    merged = recovery.merge_results(original, overlay)
    assert original == saved and len(merged) == len(original) + 69
    assert set(original) <= set(merged)
    assert merged == sorted(merged, key=lambda r: (r.day, r.home, r.away))
    assert len({f["fixture_id"] for f in overlay["fixtures"]}) == 69
    with pytest.raises(ValueError, match="Duplicate"):
        recovery.merge_results(merged, overlay)
    row = merged[0]
    fixture = copy.deepcopy(overlay["fixtures"][0])
    fixture.update(
        date=row.day.isoformat(),
        home=row.away,
        away=row.home,
        home_score=row.goals_away,
        away_score=row.goals_home,
        neutral=row.neutral,
        identity_mapping={"home": row.away, "away": row.home},
    )
    overlay["fixtures"] = [fixture]
    with pytest.raises(ValueError, match="Duplicate"):
        recovery.merge_results(original, overlay)
    fixture["home_score"] += 1
    with pytest.raises(ValueError, match="Conflicting"):
        recovery.merge_results(original, overlay)


@pytest.mark.parametrize(
    "key,value",
    [
        ("package_id", "unknown"),
        ("version", 2),
        ("version", True),
        ("original_source_sha256", "a" * 64),
        ("historical_availability_verified", True),
    ],
)
def test_package_schema(key, value):
    overlay = recovery.load_overlay()
    overlay[key] = value
    with pytest.raises(ValueError):
        recovery.merge_results(approved_source(), overlay)


@pytest.mark.parametrize(
    "key,value",
    [
        ("date", "1991-02-30"),
        ("date", "19910402"),
        ("date", "2099-01-01"),
        ("home", "Unapproved"),
        ("away", "Bulgaria"),
        ("home_score", True),
        ("away_score", -1),
        ("home_score", 1.5),
        ("status", "candidate"),
        ("classification", "youth"),
        ("score_basis", "shootout"),
        ("availability", "verified"),
        ("neutral", 0),
        ("source_ids", []),
        ("source_ids", ["missing"]),
        ("source_location", ""),
        ("competition", ""),
        ("venue_country", ""),
        ("score_semantics_review", ""),
        ("identity_mapping", {}),
        ("fixture_id", "bad"),
    ],
)
def test_fixture_schema(key, value):
    overlay = recovery.load_overlay()
    overlay["fixtures"][0][key] = value
    with pytest.raises(ValueError):
        recovery.merge_results(approved_source(), overlay)


@pytest.mark.parametrize(
    "key,value",
    [
        ("url", ""),
        ("publisher", ""),
        ("revision", ""),
        ("retrieved_on", ""),
        ("rights_basis", ""),
        ("sha256", ""),
        ("sha256", "g" * 64),
        ("retrieved_on", "not-a-date"),
    ],
)
def test_missing_source_provenance(key, value):
    overlay = recovery.load_overlay()
    overlay["sources"]["usa"][key] = value
    with pytest.raises(ValueError):
        recovery.merge_results(approved_source(), overlay)


def test_pins_and_json_types_fail_closed(tmp_path, monkeypatch):
    raw = b"[]"
    path = tmp_path / "overlay.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="object"):
        recovery.checked_json(path, hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        recovery.load_overlay()
    with pytest.raises(EvaluationError, match="assets unavailable"):
        EvaluationService(repository()).evaluate(
            BacktestRequest(dataset_id=FULL_DATASET, recovery_package_id=recovery.RECOVERY_ID)
        )


@pytest.mark.parametrize("dataset", [PILOT_DATASET, "womens-world-cup-recorded-v1"])
def test_recovery_cannot_change_pilot_or_recorded_package(dataset):
    with pytest.raises(ValidationError):
        BacktestRequest(dataset_id=dataset, recovery_package_id=recovery.RECOVERY_ID)
    with pytest.raises(ValidationError):
        BacktestRequest(dataset_id=FULL_DATASET, recovery_package_id="unapproved")


def test_recovered_cohort_retains_all_cases_and_strict_exclusions():
    service = EvaluationService(repository())
    baseline = service.evaluate(BacktestRequest(dataset_id=FULL_DATASET, limit=348))
    body = BacktestRequest(
        dataset_id=FULL_DATASET, limit=348, recovery_package_id=recovery.RECOVERY_ID
    )
    result = service.evaluate(body)
    report = json.loads((recovery.ROOT / "coverage.json").read_text())
    assert result == service.evaluate(body)
    assert result["dataset_hash"] == baseline["dataset_hash"]
    assert result["package_hash"] != baseline["package_hash"]
    assert result["source_hash"] == baseline["source_hash"] == team_ratings.SOURCE_SHA
    assert [c["match_key"] for c in result["cases"]] == [c["match_key"] for c in baseline["cases"]]
    assert result["eligible_matches"] == 0 and result["accuracy"] is None
    assert result["exclusion_reasons"]["historical_star_power_clutch_evidence_missing"] == 348
    assert result["exclusion_reasons"]["model_80_minute_horizon_unvalidated"] == 26
    assert [
        c["match_id"] for c in result["cases"] if c["rating_reconstruction"] == "insufficient"
    ] == report["remaining_match_ids"]
    assert sum(c["rating_reconstruction"] == "complete" for c in baseline["cases"]) == 320
    assert len(report["recovered_match_ids"]) >= 20
    retro = service.evaluate(
        body.model_copy(
            update={
                "mode": "retrospective_assumptions",
                "assumption_package_id": "test-only-empty-v1",
            }
        )
    )
    assert retro["exclusion_reasons"]["explicit_star_power_clutch_assumptions_missing"] == 348
    assert retro["eligible_matches"] == 0 and retro["accuracy"] is None
    assert all(c["probabilities"] is None for c in retro["cases"])


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("manifest", "package_id", "bad"),
        ("manifest", "original_manifest_sha256", "bad"),
        ("manifest", "overlay_sha256", "bad"),
        ("manifest", "original_source_sha256", "bad"),
        ("manifest", "historical_availability_verified", True),
        ("manifest", "model", "bad"),
        ("manifest", "expected_cases", 347),
        ("manifest", "expected_cutoffs", 136),
        ("manifest", "merged_source_hash", "bad"),
        ("ratings", "model", "bad"),
        ("ratings", "overlay_sha256", "bad"),
        ("ratings", "original_source_sha256", "bad"),
        ("ratings", "populations", {}),
        ("population", "cutoff", "bad"),
        ("population", "latest_source_day", "2099-01-01"),
        ("population", "source_rows", 0),
        ("population", "source_population_hash", "bad"),
        ("population", "population_hash", "bad"),
        ("population", "recovery_package_id", "bad"),
        ("population", "overlay_sha256", "bad"),
    ],
)
def test_recovered_artifact_semantics_fail_closed(target, key, value, monkeypatch):
    import services.evaluation_recovery as module

    manifest = json.loads((recovery.ROOT / "manifest.json").read_text())
    ratings = json.loads((recovery.ROOT / "ratings.json").read_text())
    cutoffs = set(ratings["populations"])
    selected = {
        "manifest": manifest,
        "ratings": ratings,
        "population": next(iter(ratings["populations"].values())),
    }[target]
    selected[key] = value
    monkeypatch.setattr(
        module,
        "checked_json",
        lambda path, sha: manifest if path.name == "manifest.json" else ratings,
    )
    with pytest.raises(ValueError):
        assets(approved_source(), cutoffs)


@pytest.mark.pinned_source
def test_all_recovered_populations_recompute_and_frozen_baselines_remain_unchanged(pinned_source):
    base = team_ratings.read_results(pinned_source.read_bytes())
    _, registry, old = original_assets()
    manifest, artifact, rows = assets(base, set(old["populations"]))
    assert len(registry["records"]) == 348 and len(artifact["populations"]) == 137
    assert len(set(r["edition"] for r in registry["records"])) == 9
    for key, population in artifact["populations"].items():
        cutoff = date.fromisoformat(key)
        earlier = [r for r in rows if r.day <= cutoff]
        assert team_ratings.calculate(earlier, cutoff) == population["ratings"]
        assert digest([r.__dict__ for r in earlier]) == population["source_population_hash"]
    report = recovery.checked_json(recovery.ROOT / "coverage.json", manifest["coverage_sha256"])
    assert sum(e["total"] for e in report["editions"].values()) == 348
    assert report["editions"]["1995"]["after"] == 26
    # A recent-only Nigerian result cannot manufacture a pre-November-1990 reference team.
    nigeria = artifact["populations"]["1991-11-16"]["ratings"]["Nigeria"]
    assert nigeria["evidence"]["form_matches"] == 0 and nigeria["form"] is None
    # Future observations have no impact on either the main or frozen-baseline fit.
    cutoff = date(1995, 6, 4)
    future = replace(rows[-1], day=date(2099, 1, 1), goals_home=999)
    assert (
        team_ratings.calculate(rows + [future], cutoff)
        == artifact["populations"]["1995-06-04"]["ratings"]
    )


@pytest.mark.parametrize(
    "key,value", [("sources", {}), ("sources", []), ("fixtures", []), ("fixtures", {})]
)
def test_empty_schema_rejected(key, value):
    overlay = recovery.load_overlay()
    overlay[key] = value
    with pytest.raises(ValueError, match="schema"):
        recovery.merge_results(approved_source(), overlay)


@pytest.mark.parametrize("corruption", ["path", "bytes"])
def test_attributed_snapshot_integrity(corruption, tmp_path, monkeypatch):
    import shutil

    shutil.copytree(recovery.ROOT, tmp_path / "package")
    overlay = recovery.load_overlay()
    if corruption == "path":
        overlay["sources"]["ghana"]["snapshot"] = "../outside"
    else:
        (tmp_path / "package/sources/ghana.html").write_bytes(b"changed")
    monkeypatch.setattr(recovery, "ROOT", tmp_path / "package")
    monkeypatch.setattr(recovery, "checked_json", lambda path, sha: overlay)
    with pytest.raises(ValueError, match="snapshot"):
        recovery.load_overlay()
