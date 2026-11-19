"""Real evidence inventory, deterministic protocol boundaries, and adversarial source checks."""

import json
import shutil
from dataclasses import replace
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from exceptions.base import EvaluationAssetUnavailable
from football.backtesting_evidence import EDITION_COUNTS, reconcile, validate_inventory
from infra.repositories.evaluation import HistoricalCase
from schemas.evaluation.request import FULL_DATASET, BacktestRequest
from services.evaluation import EvaluationError, EvaluationService, digest
from services.evaluation_full import ROOT, assets, load_full
from tests.unit.services.test_evaluation import FakeRepository


def catalog():
    _, registry, _ = assets()
    return [
        dict(
            match_date=r["date"],
            source_home_team=r["home"],
            source_away_team=r["away"],
            home_score=r["final_score"][0],
            away_score=r["final_score"][1],
            source_record_key=r["match_key"],
        )
        for r in registry["records"]
    ]


def repository():
    _, registry, _ = assets()
    return FakeRepository(
        [
            HistoricalCase(
                r["match_id"],
                r["match_key"],
                date.fromisoformat(r["date"]),
                r["home_team_id"],
                r["away_team_id"],
                r["home"],
                r["away"],
                r["home"],
                r["away"],
                *r["final_score"],
                "including_extra_time_no_shootout",
                r["catalog_source_sha256"],
                r["catalog_revision"],
            )
            for r in registry["records"]
        ]
    )


@pytest.mark.parametrize("edition", EDITION_COUNTS)
def test_all_editions_reconcile_unique_identity_orientation_and_rules(edition):
    _, registry, _ = assets()
    source = next(s for s in registry["sources"] if s["id"] == f"rsssf-{edition}")
    parsed = reconcile((ROOT / source["filename"]).read_bytes(), edition, catalog())
    assert len(parsed) == EDITION_COUNTS[edition]
    for row in registry["records"]:
        if row["edition"] == edition:
            assert all(row[k] == v for k, v in parsed[row["match_key"]].items())
            assert row["regulation_minutes"] == (80 if edition == 1991 else 90)
            if row["extra_time_played"]:
                assert row["regulation_score"][0] == row["regulation_score"][1]
                assert row["extra_time_score"] == row["final_score"]
            elif row["shootout_score"]:
                assert edition == 1999 and row["stage"] == "third_place"
            else:
                assert row["regulation_score"] == row["final_score"]


@pytest.mark.parametrize("corruption", ["permission", "score", "missing", "duplicate", "identity"])
def test_archive_reconciliation_rejects_corruption(corruption):
    raw = (ROOT / "sources/wwc91f.html").read_bytes()
    if corruption == "permission":
        raw = raw.replace(b"You are free to copy this document", b"No permission")
    if corruption == "score":
        raw = raw.replace(b"4-0 Norway", b"5-0 Norway")
    if corruption == "identity":
        raw = raw.replace(b"4-0 Norway", b"4-0 Unknown")
    if corruption == "missing":
        raw = raw.replace(b"16 Nov Guangzhou", b"XX Nov Guangzhou")
    if corruption == "duplicate":
        raw += b"\n16 Nov Guangzhou    China        4-0 Norway\n"
    with pytest.raises(ValueError):
        reconcile(raw, 1991, catalog())


def test_inventory_golden_goal_and_shootout_separation():
    _, r, _ = assets()
    records = r["records"]
    validate_inventory(records)
    with pytest.raises(ValueError):
        validate_inventory(records[:-1])
    with pytest.raises(ValueError):
        validate_inventory([records[0]] * 348)
    with pytest.raises(ValueError):
        validate_inventory([{**r, "edition": 2023} for r in records])
    golden = [r for r in records if r["golden_goal_rule"] and r["shootout_score"] is None]
    assert [(r["edition"], r["regulation_score"], r["extra_time_score"]) for r in golden] == [
        (1999, [3, 3], [4, 3]),
        (2003, [1, 1], [2, 1]),
    ]
    assert all(r["discrepancies"] for r in golden)
    assert len([r for r in records if r["extra_time_played"]]) == 19
    assert len(load_full().labels) == 348


@pytest.mark.parametrize(
    "filename", ["registry.json", "ratings.json", "rules.json", "sources/wwc91f.html"]
)
def test_full_package_checksums_fail_closed(filename, tmp_path, monkeypatch):
    shutil.copytree(ROOT, tmp_path / "package")
    path = tmp_path / "package" / filename
    path.write_bytes(path.read_bytes() + b" ")
    monkeypatch.setattr("services.evaluation_full.ROOT", tmp_path / "package")
    with pytest.raises(EvaluationAssetUnavailable):
        EvaluationService(FakeRepository()).evaluate(BacktestRequest(dataset_id=FULL_DATASET))


@pytest.mark.parametrize("edition", [None, *EDITION_COUNTS])
def test_full_and_edition_selection_account_for_every_match_without_assumptions(edition):
    result = EvaluationService(repository()).evaluate(
        BacktestRequest(dataset_id=FULL_DATASET, edition=edition, limit=348)
    )
    assert result["dataset_match_count"] == 348
    assert result["cohort_match_count"] == (348 if edition is None else EDITION_COUNTS[edition])
    assert result["eligible_matches"] == 0 and result["accuracy"] is None
    assert result["total_candidate_matches"] == result["cohort_match_count"]
    assert all(c["edition"] == edition for c in result["cases"]) if edition else True
    assert all(c["label_provenance"] is not None for c in result["cases"])
    for c in result["cases"]:
        assert "historical_star_power_clutch_evidence_missing" in c["exclusion_reasons"]
        if c["edition"] == 1991:
            assert "model_80_minute_horizon_unvalidated" in c["exclusion_reasons"]
    assert sum(s["total"] for s in result["edition_summaries"]) == len(result["cases"])
    assert sum(s["total"] for s in result["protocol_summaries"]) == len(result["cases"])


def test_retrospective_missing_and_catalog_corruption():
    repo = repository()
    service = EvaluationService(repo)
    body = BacktestRequest(
        dataset_id=FULL_DATASET,
        mode="retrospective_assumptions",
        assumption_package_id="test-only-no-values-v1",
        limit=348,
    )
    result = service.evaluate(body)
    assert result["exclusion_reasons"]["explicit_star_power_clutch_assumptions_missing"] == 348
    assert result["excluded_matches"] == 348
    assert sum(c["rating_reconstruction"] == "complete" for c in result["cases"]) == 320
    assert result == service.evaluate(body)
    for bad in [
        repo.cases[:-1],
        [repo.cases[0]] * 348,
        [*repo.cases[:-1], replace(repo.cases[-1], recorded_home=999)],
        [*repo.cases[:-1], replace(repo.cases[-1], source_hash="f" * 64)],
    ]:
        with pytest.raises(EvaluationError):
            EvaluationService(FakeRepository(bad)).evaluate(body)
    empty = service.evaluate(BacktestRequest(dataset_id=FULL_DATASET, edition=1991, offset=26))
    assert empty["cases"] == [] and empty["cohort_match_count"] == 26


@pytest.mark.parametrize(
    "changes",
    [
        {"edition": 1992},
        {"limit": 349},
        {"limit": 0},
        {"assumptions": [{"match_key": "a" * 64, "team_id": 1, "star_power": None, "clutch": 25}]},
        {"assumptions": [{"match_key": "a" * 64, "team_id": 1, "star_power": 101, "clutch": 25}]},
    ],
)
def test_full_contract_rejects_invalid_input(changes):
    with pytest.raises(ValidationError):
        BacktestRequest(dataset_id=FULL_DATASET, **changes)


@pytest.mark.pinned_source
def test_cached_reference_populations_are_cutoff_safe_and_reproducible(pinned_source):
    from football.team_ratings import read_results

    rows = read_results(pinned_source.read_bytes())
    _, registry, artifact = assets()
    for cutoff, p in artifact["populations"].items():
        earlier = [r for r in rows if r.day <= date.fromisoformat(cutoff)]
        assert p["source_population_hash"] == digest([r.__dict__ for r in earlier])
        assert p["source_rows"] == len(earlier)
        assert p["population_hash"] == digest(p["ratings"])
    for record in registry["records"]:
        cutoff = date.fromisoformat(record["date"]) - timedelta(days=1)
        assert cutoff.isoformat() in artifact["populations"]


@pytest.mark.parametrize(
    "change",
    [
        "manifest",
        "model",
        "population_hash",
        "population_date",
        "duration",
        "completion",
        "extra_time",
    ],
)
def test_reviewed_package_semantics_reject_incompatible_artifacts(change, monkeypatch):
    import copy

    import services.evaluation_full as full

    manifest, registry, ratings = assets()
    rules = json.loads((ROOT / "rules.json").read_text())
    values = {
        "manifest.json": manifest,
        "registry.json": registry,
        "ratings.json": ratings,
        "rules.json": rules,
    }
    values = copy.deepcopy(values)
    if change == "manifest":
        values["manifest.json"]["expected_catalog_matches"] = 2
    elif change == "model":
        values["ratings.json"]["model"] = "wrong"
    elif change.startswith("population"):
        population = next(iter(values["ratings.json"]["populations"].values()))
        population["population_hash" if change == "population_hash" else "latest_source_day"] = (
            "wrong"
        )
    elif change == "duration":
        values["registry.json"]["records"][0]["regulation_minutes"] = 90
    elif change == "completion":
        values["registry.json"]["records"][0]["completion_status"] = "abandoned"
    else:
        record = next(r for r in values["registry.json"]["records"] if r["extra_time_played"])
        record["regulation_score"] = [2, 1]
    monkeypatch.setattr(full, "verified_json", lambda path, expected: values[path.name])
    with pytest.raises(ValueError):
        full.load_full()


def test_unapproved_label_remains_excluded_and_80_minute_predictions_are_rejected(monkeypatch):
    from schemas.evaluation.response import CaseResult

    package = load_full()
    repo = repository()
    key = repo.cases[-1].match_key
    service = EvaluationService(
        repo, replace(package, labels={k: v for k, v in package.labels.items() if k != key})
    )
    result = service.evaluate(
        BacktestRequest(dataset_id=FULL_DATASET, edition=2023, offset=63, limit=1)
    )
    assert result["exclusion_reasons"]["regulation_outcome_evidence_missing"] == 1
    case = result["cases"][0]
    with pytest.raises(ValidationError):
        CaseResult.model_validate({**case, "regulation_minutes": 80, "status": "eligible"})
