"""Pinned, reviewed facts only. No network, database writes or invented strengths."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from football import team_ratings
from schemas.evaluation.request import PILOT_DATASET
from services.evaluation import (
    DATASET,
    PREDICTION_MODEL,
    PROTOCOL,
    REVISION,
    EvaluationPackage,
    RegulationEvidence,
)

ROOT = Path(__file__).resolve().parents[2] / "data/evaluation" / PILOT_DATASET
MANIFEST_SHA256 = "77df72e5d74263c40ca5e4db96f6594551334272270ea9748f3818c79df0f23d"


def verified_json(path: Path, expected_hash: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("Evaluation evidence checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected an evidence object")
    return value


def load_pilot() -> EvaluationPackage:
    manifest = verified_json(ROOT / "manifest.json", MANIFEST_SHA256)
    regulations = verified_json(
        ROOT / "regulations-evidence.json", manifest["regulations_evidence_sha256"]
    )
    verified_json(ROOT / "rating-reconstruction.json", manifest["rating_reconstruction_sha256"])
    if (
        manifest["dataset_id"] != PILOT_DATASET
        or manifest["catalog_dataset_id"] != DATASET
        or manifest["expected_catalog_matches"] != 348
        or manifest["source_revision"] != REVISION
        or manifest["source_sha256"] != team_ratings.SOURCE_SHA
        or manifest["protocol_version"] != PROTOCOL
        or manifest["prediction_model_version"] != PREDICTION_MODEL
        or manifest["rating_model_version"] != team_ratings.MODEL
        or manifest["historical_availability_verified"] is not False
        or regulations["reviewed_facts"]["regulation_minutes"] != 90
    ):
        raise ValueError("Incompatible pilot manifest")
    labels = {}
    for label in manifest["labels"]:
        if (
            label["regulation_minutes"] != 90
            or label["completion_status"] != "completed"
            or label["extra_time_played"] is not False
            or label["penalty_shootout_played"] is not False
            or label["stage"] != "group"
            or label["verification_status"] != "approved_official_report_and_regulations"
            or label["regulations_evidence_sha256"] != manifest["regulations_evidence_sha256"]
        ):
            raise ValueError("Uncertified pilot outcome")
        labels[label["match_key"]] = RegulationEvidence(
            day=date.fromisoformat(label["date"]),
            home=label["home"],
            away=label["away"],
            home_score=label["home_score"],
            away_score=label["away_score"],
            source=label["source_url"],
            source_hash=label["source_sha256"],
            definition=label["definition"],
            regulation_minutes=label["regulation_minutes"],
            completion_status=label["completion_status"],
            provenance={**label, "regulations": regulations},
        )
    if len(labels) != 2 or len(manifest["labels"]) != 2:
        raise ValueError("Expected exactly two distinct pilot identities")
    return EvaluationPackage(
        dataset_id=PILOT_DATASET,
        labels=labels,
        match_keys=tuple(labels),
        provenance={"manifest_sha256": MANIFEST_SHA256, **manifest},
    )
