"""Read-only adapter for the pinned Prompt 3 research replay; never fits a model."""

import hashlib
import json
from pathlib import Path
from typing import Any

from football.evaluation import CLASSES, probabilities

ROOT = Path(__file__).resolve().parents[2] / "data/research/three-input-validation-v1"
MANIFEST_SHA = "560e625cb74c453c76952f57937e33307fe946ceada04c687baf3f4028a70bed"
MODELS = (
    "odf-reweighted-poisson-research-v1",
    "odf-cross-goal-rate-research-v1",
    "odf-temperature-research-v1",
)


def assets() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw = (ROOT / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError("Research manifest checksum mismatch")
    manifest = json.loads(raw)
    loaded = {}
    for name, expected in manifest["files"].items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Research artifact checksum mismatch")
        loaded[name] = json.loads(raw)
    data, results = loaded["predictions.json"], loaded["results.json"]
    cases = {r["match_key"]: r for r in data["cases"]}
    if len(cases) != 348 or len(data["cases"]) != 348:
        raise ValueError("Incomplete research inventory")
    for row in cases.values():
        if row["cutoff"] >= row["date"] or row["production_eligible"]:
            raise ValueError("Invalid research cutoff/classification")
        for model, p in row["predictions"].items():
            probabilities(p)
            if row["horizon_minutes"] != 90 or not row["rating_complete"]:
                raise ValueError("Invalid research prediction eligibility")
            if model == MODELS[2] and (
                row["edition"] <= 2007 or data["calibration"]["through"] >= row["date"]
            ):
                raise ValueError("Future calibration leakage")
        if row["truth"] not in range(len(CLASSES)):
            raise ValueError("Invalid research outcome")
    return data, cases, results


def diagnostics(
    data: dict[str, Any], results: dict[str, Any], edition: int | None
) -> dict[str, Any]:
    return {
        "classification": "research_only",
        "interpretation": "Retrospective replay; not strict historical or prospective forecasts",
        "independently_validated": False,
        "production_eligible": False,
        "package_id": "three-input-validation-v1",
        "manifest_sha256": MANIFEST_SHA,
        "protocol_hash": data["protocol_hash"],
        "data_hash": results["data_hash"],
        "scope": "Selected edition or full cohort, independent of page; paired common cohorts only",
        "protocol": results["protocol"],
        "calibration": data["calibration"] if edition is None or edition > 2007 else None,
        "comparisons": results["results"][str(edition) if edition else "all_exploratory"],
        "period_comparisons": {
            k: results["results"][k]
            for k in ("development", "calibration", "validation", "retrospective_holdout")
        }
        if edition is None
        else {},
    }
