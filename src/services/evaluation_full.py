"""Content-pinned full evidence package and offline calculator outputs; no network or DB writes."""

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from football import team_ratings
from football.backtesting_evidence import validate_inventory
from schemas.evaluation.request import FULL_DATASET
from services.evaluation import REVISION, EvaluationPackage, RegulationEvidence, digest
from services.evaluation_pilot import load_pilot, verified_json

ROOT = Path(__file__).resolve().parents[2] / "data/evaluation" / FULL_DATASET
MANIFEST_SHA256 = "47c947db3f117a14761930da3c0dcfa3b68b50e94b6e12904b9bf7ddc75a0a28"


def assets() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = verified_json(ROOT / "manifest.json", MANIFEST_SHA256)
    registry = verified_json(ROOT / "registry.json", manifest["registry_sha256"])
    ratings = verified_json(ROOT / "ratings.json", manifest["ratings_sha256"])
    rules = verified_json(ROOT / "rules.json", manifest["rules_sha256"])
    if (
        manifest["dataset_id"] != FULL_DATASET
        or manifest["expected_catalog_matches"] != 348
        or manifest["source_sha256"] != team_ratings.SOURCE_SHA
        or manifest["source_revision"] != REVISION
        or manifest["historical_availability_verified"] is not False
        or ratings["model"] != team_ratings.MODEL
        or ratings["source_sha256"] != team_ratings.SOURCE_SHA
        or manifest["rules"] != rules
    ):
        raise ValueError("Incompatible full evidence package")
    validate_inventory(registry["records"])
    for source in registry["sources"]:
        path = ROOT / source["filename"]
        if (
            path.parent != ROOT / "sources"
            or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
        ):
            raise ValueError("Archive checksum mismatch")
    for cutoff, population in ratings["populations"].items():
        if (
            population["cutoff"] != cutoff
            or population["latest_source_day"] > cutoff
            or digest(population["ratings"]) != population["population_hash"]
        ):
            raise ValueError("Historical population integrity mismatch")
    return manifest, registry, ratings


def load_full() -> EvaluationPackage:
    manifest, registry, _ = assets()
    labels = {}
    for record in registry["records"]:
        if record["verification_status"] != "verified_attributed_archive":
            continue
        if record["completion_status"] != "completed" or record["regulation_minutes"] != (
            80 if record["edition"] == 1991 else 90
        ):
            raise ValueError("Incompatible outcome evidence")
        home, away = record["regulation_score"]
        if record["extra_time_played"] and home != away:
            raise ValueError("Extra time requires a tied regulation score")
        labels[record["match_key"]] = RegulationEvidence(
            day=date.fromisoformat(record["date"]),
            home=record["home"],
            away=record["away"],
            home_score=home,
            away_score=away,
            source=record["source_url"],
            source_hash=record["source_sha256"],
            regulation_minutes=record["regulation_minutes"],
            completion_status=record["completion_status"],
            provenance=record,
        )
    # Preserve priority of the two already-reviewed official report labels.
    for key, label in load_pilot().labels.items():
        if (labels[key].home_score, labels[key].away_score) != (label.home_score, label.away_score):
            raise ValueError("Official/archive outcome conflict")
        labels[key] = label
    return EvaluationPackage(
        dataset_id=FULL_DATASET,
        labels=labels,
        match_keys=tuple(r["match_key"] for r in registry["records"]),
        provenance={"manifest_sha256": MANIFEST_SHA256, **manifest},
    )
