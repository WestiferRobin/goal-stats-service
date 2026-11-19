"""Reproducible inventory for the evidence-blocked 80-minute interface."""

from datetime import date, timedelta
from typing import Any

from football.duration_research import SPEC, inspect_case
from services import evaluation_full, evaluation_recovery
from services.evaluation import approved_source, digest


def build() -> dict[str, Any]:
    original, registry, old = evaluation_full.assets()
    recovery, ratings, rows = evaluation_recovery.assets(approved_source(), set(old["populations"]))
    cases = []
    for record in registry["records"]:
        if record["edition"] != 1991:
            continue
        cutoff = date.fromisoformat(record["date"]) - timedelta(days=1)
        population = ratings["populations"][str(cutoff)]
        participants = {n: population["ratings"].get(n) for n in (record["home"], record["away"])}
        complete = all(
            r is not None and all(r[k] is not None for k in ("offense", "defense", "form"))
            for r in participants.values()
        )
        cases.append(
            {
                "record": record,
                "research": inspect_case(record, cutoff, complete),
                "rating_evidence": {
                    "participants": participants,
                    "source_population_hash": population["source_population_hash"],
                    "source_rows": population["source_rows"],
                    "source_hash": recovery["merged_source_hash"],
                },
            }
        )
    if len(cases) != 26 or len(registry["records"]) != 348:
        raise ValueError("Historical inventory mismatch")
    prior = [r for r in rows if r.day < date(1991, 11, 16)]
    training = [r for r in prior if r.day < date(1990, 1, 1)]
    calibration = [r for r in prior if r.day >= date(1990, 1, 1)]
    return {
        "protocol": SPEC,
        "protocol_hash": digest(SPEC),
        "full_inventory": {
            str(y): sum(r["edition"] == y for r in registry["records"])
            for y in range(1991, 2024, 4)
        },
        "source_manifest_hashes": {"original": digest(original), "recovery": digest(recovery)},
        "pre_tournament_recorded_score_candidates": len(prior),
        "training_candidates": len(training),
        "calibration_candidates": len(calibration),
        "training_candidate_hash": digest([r.__dict__ for r in training]),
        "calibration_candidate_hash": digest([r.__dict__ for r in calibration]),
        "qualified_training": 0,
        "qualified_calibration": 0,
        "shortfall": (
            "Every candidate lacks jointly verified nominal duration, regulation-only score "
            "and historical publication timing in the approved training schema. No candidate "
            "is promoted to a training observation. No parameters estimated or accuracy scored."
        ),
        "rating_complete": sum(c["research"]["rating_complete"] for c in cases),
        "eligible": 0,
        "excluded": len(cases),
        "cases": cases,
    }
