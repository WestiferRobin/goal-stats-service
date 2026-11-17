"""Offline, provenance-pinned chronological research evaluation; never a production route."""

import hashlib
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from football.evaluation import CLASSES, metrics, outcome
from research.special_ratings import digest
from research.three_input import (
    FREQUENCY,
    POISSON,
    SPEC,
    A,
    B,
    C,
    Ratings,
    calibrate,
    period,
    poisson,
    predict,
)
from services import evaluation_full, evaluation_recovery
from services.evaluation import approved_source

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "data/research/three-input-validation-v1"
RANKING_SHA = "2ec1a17e75b3096f58274811c96e51b9bfd12f9fe0d7fa08636cd98fce1c162b"


def baseline(history: list[dict[str, Any]], edition: int) -> dict[str, Any] | None:
    rows = [
        r
        for r in history
        if r["edition"] < edition and r["edition"] <= 2003 and r["regulation_minutes"] == 90
    ]
    if any(date.fromisoformat(r["date"]).year != r["edition"] for r in rows):
        raise ValueError("Baseline observation edition/date mismatch")
    if len({r["match_key"] for r in rows}) != len(rows):
        raise ValueError("Duplicate baseline training outcomes")
    if len(rows) < 20:
        return None
    counts = [0, 0, 0]
    for row in rows:
        counts[CLASSES.index(outcome(*row["regulation_score"]))] += 1
    n = len(rows)
    rate = sum(sum(r["regulation_score"]) for r in rows) / (2 * n)
    return {
        "training_cases": n,
        "training_hash": digest(rows),
        "training_through": max(r["date"] for r in rows),
        "parameter_version": "development-only-baselines-v1",
        "goal_rate": rate,
        "predictions": {
            FREQUENCY: [(k + 1) / (n + 3) for k in counts],
            POISSON: list(poisson(rate, rate)),
        },
    }


def reconstruct() -> dict[str, Any]:
    original, registry, old = evaluation_full.assets()
    recovery, ratings, _ = evaluation_recovery.assets(approved_source(), set(old["populations"]))
    raw = (PACKAGE / "rankings.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != RANKING_SHA:
        raise ValueError("Ranking snapshot checksum mismatch")
    ranks = json.loads(raw)["cases"]
    if set(ranks) != {r["match_key"] for r in registry["records"]}:
        raise ValueError("Ranking inventory mismatch")
    cases = []
    baselines = {year: baseline(registry["records"], year) for year in range(1991, 2024, 4)}
    for record in registry["records"]:
        cutoff = date.fromisoformat(record["date"]) - timedelta(days=1)
        population = ratings["populations"][cutoff.isoformat()]
        evidence = ranks[record["match_key"]]
        for side, rank in zip(("home", "away"), evidence, strict=True):
            if rank["team_id"] != record[side + "_team_id"] or (
                rank.get("published_on") and rank["published_on"] >= record["date"]
            ):
                raise ValueError("Ranking identity/cutoff mismatch")
        inputs = [population["ratings"].get(record[side], {}) for side in ("home", "away")]
        complete = all(
            row.get(field) is not None for row in inputs for field in ("offense", "defense", "form")
        )
        reasons = []
        if record["regulation_minutes"] != 90:
            reasons.append("unsupported_80_minute_horizon")
        if not complete:
            reasons.append("missing_historical_offense_defense_or_form")
        predictions = {}
        if not reasons:
            h, a = [
                Ratings(**{k: row[k] for k in ("offense", "defense", "form")}) for row in inputs
            ]
            predictions = {model: list(predict(h, a, model)) for model in (A, B)}
            base = baselines[record["edition"]]
            if base is not None:
                predictions.update(base["predictions"])
        cases.append(
            {
                "match_id": record["match_id"],
                "match_key": record["match_key"],
                "edition": record["edition"],
                "date": record["date"],
                "cutoff": cutoff.isoformat(),
                "home": record["home"],
                "away": record["away"],
                "period": period(record["edition"]),
                "horizon_minutes": record["regulation_minutes"],
                "rating_complete": complete,
                "inputs": inputs,
                "ranking_evidence": evidence,
                "ranking_used": False,
                "source_population_hash": population["source_population_hash"],
                "rating_population_hash": population["population_hash"],
                "rating_population_size": len(population["ratings"]),
                "outcome_source_hash": record["source_sha256"],
                "truth": CLASSES.index(outcome(*record["regulation_score"])),
                "predictions": predictions,
                "exclusion_reasons": reasons,
                "five_input_eligible": False,
                "five_input_exclusion": "no_independently_approved_star_power_and_clutch",
                "baseline_training": baselines[record["edition"]],
                "production_eligible": False,
                "strict_publication_verified": False,
            }
        )
    calibration_cases = [r for r in cases if r["edition"] == 2007 and B in r["predictions"]]
    calibration = calibrate(calibration_cases, date(2011, 1, 1))
    for row in cases:
        if row["edition"] > 2007 and B in row["predictions"]:
            if calibration["through"] >= row["date"]:
                raise ValueError("Calibration leakage")
            h, a = [
                Ratings(**{k: r[k] for k in ("offense", "defense", "form")}) for r in row["inputs"]
            ]
            row["predictions"][C] = list(predict(h, a, C, temperature=calibration["temperature"]))
    return {
        "protocol_hash": digest(SPEC),
        "original_manifest_sha256": evaluation_full.MANIFEST_SHA256,
        "recovery_manifest_sha256": evaluation_recovery.MANIFEST_SHA256,
        "registry_sha256": original["registry_sha256"],
        "recovery_source_hash": recovery["merged_source_hash"],
        "ranking_snapshot_sha256": RANKING_SHA,
        "rating_model": ratings["model"],
        "calibration": calibration,
        "cases": cases,
    }


def losses(p: list[float], truth: int) -> tuple[float, float, float]:
    return (
        -math.log(max(1e-15, p[truth])),
        sum((v - int(i == truth)) ** 2 for i, v in enumerate(p)),
        float(max(range(3), key=lambda i: p[i]) == truth),
    )


def comparison(cases: list[dict[str, Any]], models: list[str]) -> dict[str, Any]:
    if len(models) != len(set(models)) or B not in models:
        raise ValueError("Comparison requires distinct models including primary B")
    rows = [r for r in cases if all(m in r["predictions"] for m in models)]
    if len({r["match_key"] for r in rows}) != len(rows):
        raise ValueError("Duplicate evaluation cases")
    n = len(rows)
    if not n:
        return {"sample_size": 0, "models": {}, "paired_differences": {}}
    values = {
        model: [losses(r["predictions"][model], r["truth"]) for r in rows] for model in models
    }
    groups = [
        [i for i, r in enumerate(rows) if r["edition"] == year]
        for year in sorted({r["edition"] for r in rows})
    ]
    rng = random.Random(SPEC["bootstrap_seed"])
    draws: dict[str, list[list[float]]] = {m: [[], [], []] for m in models}
    for _ in range(SPEC["bootstrap_replicates"]):
        indices = (
            [i for _ in groups for i in rng.choice(groups)]
            if len(groups) > 1
            else [rng.randrange(n) for _ in range(n)]
        )
        for model in models:
            for j in range(3):
                draws[model][j].append(sum(values[model][i][j] for i in indices) / len(indices))

    def interval(v: list[float]) -> list[float]:
        ordered = sorted(v)
        return [ordered[24], ordered[974]]

    output: dict[str, Any] = {}
    names = ["log_loss", "brier_score", "accuracy"]
    for model in models:
        stats = metrics([(r["predictions"][model], CLASSES[r["truth"]]) for r in rows])
        bins = []
        classes = []
        for k, label in enumerate(CLASSES):
            predicted = [max(range(3), key=lambda i: r["predictions"][model][i]) for r in rows]
            tp = sum(r["truth"] == k and p == k for r, p in zip(rows, predicted, strict=True))
            support = sum(r["truth"] == k for r in rows)
            positive = sum(p == k for p in predicted)
            classes.append(
                {
                    "class": label,
                    "support": support,
                    "recall": tp / support if support else None,
                    "precision": tp / positive if positive else None,
                }
            )
            for b in range(5):
                selected = [r for r in rows if min(4, int(r["predictions"][model][k] * 5)) == b]
                bins.append(
                    {
                        "class": label,
                        "bin": [b / 5, (b + 1) / 5],
                        "n": len(selected),
                        "mean_probability": sum(r["predictions"][model][k] for r in selected)
                        / len(selected)
                        if selected
                        else None,
                        "observed_frequency": sum(r["truth"] == k for r in selected) / len(selected)
                        if selected
                        else None,
                    }
                )
        output[model] = {
            **stats,
            "sample_size": n,
            "class_performance": classes,
            "calibration_bins": bins,
            "uncertainty_95": {name: interval(draws[model][i]) for i, name in enumerate(names)},
        }
    differences = {
        model: {
            name: {
                "mean": sum(v[i] for v in values[B]) / n - sum(v[i] for v in values[model]) / n,
                "interval_95": interval(
                    [a - b for a, b in zip(draws[B][i], draws[model][i], strict=True)]
                ),
            }
            for i, name in enumerate(names)
        }
        for model in models
        if model != B
    }
    return {
        "sample_size": n,
        "cohort_hash": digest([r["match_key"] for r in rows]),
        "match_ids": [r["match_id"] for r in rows],
        "excluded_from_supplied_group": len(cases) - n,
        "editions": sorted({r["edition"] for r in rows}),
        "models": output,
        "paired_differences": differences,
        "difference_direction": (
            "Primary B minus comparator; negative favors B for losses, positive for accuracy"
        ),
        "uncertainty_method": "edition_block" if len(groups) > 1 else "within_edition_matches",
        "independent_edition_clusters": len(groups),
        "evaluation_mode": "retrospective_reconstruction_not_prospective",
    }


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    cases = data["cases"]
    expected = {
        1991: 26,
        1995: 26,
        1999: 32,
        2003: 32,
        2007: 32,
        2011: 32,
        2015: 52,
        2019: 52,
        2023: 64,
    }
    if (
        len(cases) != 348
        or len({c["match_key"] for c in cases}) != 348
        or any(
            sum(c["edition"] == year for c in cases) != count for year, count in expected.items()
        )
    ):
        raise ValueError("Full 348-match inventory required")
    editions = []
    for year in range(1991, 2024, 4):
        rows = [c for c in cases if c["edition"] == year]
        editions.append(
            {
                "edition": year,
                "total": len(rows),
                "rating_complete": sum(r["rating_complete"] for r in rows),
                "three_input_eligible": sum(B in r["predictions"] for r in rows),
                "calibrated_eligible": sum(C in r["predictions"] for r in rows),
                "five_input_eligible": 0,
                "model_comparison_eligible": 0,
                "excluded": sum(B not in r["predictions"] for r in rows),
                "exclusion_counts": {
                    reason: sum(reason in r["exclusion_reasons"] for r in rows)
                    for reason in [
                        "unsupported_80_minute_horizon",
                        "missing_historical_offense_defense_or_form",
                    ]
                },
                "horizon": 80 if year == 1991 else 90,
                "status": period(year),
            }
        )
    groups = {"all_exploratory": cases}
    groups.update({str(y): [c for c in cases if c["edition"] == y] for y in range(1991, 2024, 4)})
    groups.update(
        {
            p: [c for c in cases if c["period"] == p]
            for p in ["development", "calibration", "validation", "retrospective_holdout"]
        }
    )
    results = {
        name: {
            cohort: comparison(rows, models)
            for cohort, models in {
                "three_input": [A, B],
                "baseline_common": [A, B, FREQUENCY, POISSON],
                "calibrated_common": [A, B, C, FREQUENCY, POISSON],
            }.items()
        }
        for name, rows in groups.items()
    }
    return {
        "protocol": SPEC,
        "protocol_hash": digest(SPEC),
        "data_hash": digest(data),
        "total_cases": len(cases),
        "editions": editions,
        "results": results,
        "five_input_status": SPEC["five_input_status"],
        "primary_comparison_sample_size": 0,
    }
