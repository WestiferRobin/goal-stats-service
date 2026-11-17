"""Opt-in, content-pinned recovery; catalog identity and evidence gates stay unchanged."""

from datetime import date
from typing import Any

from football import team_ratings
from football.results_recovery import (
    OVERLAY_SHA256,
    RECOVERY_ID,
    ROOT,
    checked_json,
    load_overlay,
    merge_results,
)
from services.evaluation import digest
from services.evaluation_full import MANIFEST_SHA256 as ORIGINAL_MANIFEST_SHA256

MANIFEST_SHA256 = "45593e9139180f48ec931846d6316f62dfc975386c28c58167c0e737f42ce31b"


def assets(
    base: list[team_ratings.Result], expected_cutoffs: set[str]
) -> tuple[dict[str, Any], dict[str, Any], list[team_ratings.Result]]:
    manifest = checked_json(ROOT / "manifest.json", MANIFEST_SHA256)
    ratings = checked_json(ROOT / "ratings.json", manifest["ratings_sha256"])
    rows = merge_results(base, load_overlay())
    if (
        manifest["package_id"] != RECOVERY_ID
        or manifest["original_manifest_sha256"] != ORIGINAL_MANIFEST_SHA256
        or manifest["overlay_sha256"] != OVERLAY_SHA256
        or manifest["original_source_sha256"] != team_ratings.SOURCE_SHA
        or manifest["historical_availability_verified"] is not False
        or manifest["model"] != team_ratings.MODEL
        or manifest["expected_cases"] != 348
        or manifest["expected_cutoffs"] != len(expected_cutoffs)
        or manifest["merged_source_hash"] != digest([r.__dict__ for r in rows])
        or ratings["model"] != team_ratings.MODEL
        or ratings["overlay_sha256"] != OVERLAY_SHA256
        or ratings["original_source_sha256"] != team_ratings.SOURCE_SHA
        or set(ratings["populations"]) != expected_cutoffs
    ):
        raise ValueError("Incompatible recovered evidence package")
    for key, population in ratings["populations"].items():
        earlier = [r for r in rows if r.day <= date.fromisoformat(key)]
        if (
            population["cutoff"] != key
            or population["latest_source_day"] != max(r.day for r in earlier).isoformat()
            or population["source_rows"] != len(earlier)
            or population["source_population_hash"] != digest([r.__dict__ for r in earlier])
            or population["population_hash"] != digest(population["ratings"])
            or population["recovery_package_id"] != RECOVERY_ID
            or population["overlay_sha256"] != OVERLAY_SHA256
        ):
            raise ValueError("Recovered reference population mismatch")
    return manifest, ratings, rows
