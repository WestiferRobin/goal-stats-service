"""Fail-closed 1991 research interface; no production prediction dependencies.

This version specifies an exposure candidate but deliberately has no fitted
parameters or prediction operation. Recorded final scores without duration and
regulation-score provenance cannot identify a scientifically defensible fit.
"""

from datetime import date
from typing import Any

MODEL = "odf-exposure-80-evidence-blocked-v1"
BLOCKERS = (
    "duration_annotated_training_evidence_missing",
    "duration_compatible_rating_validation_missing",
    "independent_80_minute_validation_missing",
    "historical_source_availability_unverified",
    "original_1991_tournament_procedures_unverified",
)
SPEC: dict[str, Any] = {
    "model_version": MODEL,
    "regulation_minutes": 80,
    "classification": "research_only",
    "validation_status": "evidence_blocked",
    "formula_candidate": (
        "lambda_i = 80 * r_per_team_minute * exp(beta_OD*(O_i-D_j)/100 + beta_F*(F_i-F_j)/100)"
    ),
    "outcomes": ["home_win", "draw", "away_win"],
    "exposure": "Nominal regulation minutes including associated added time; exclude extra time",
    "distribution_candidate": "Independent Poisson regulation goals; not yet fitted or validated",
    "parameters": None,
    "training": "Verified regulation-only observations dated before 1990-01-01",
    "calibration": "Disjoint verified observations from 1990-01-01 through 1991-11-15",
    "evaluation": "1991-11-16 through 1991-11-30; all 26 matches retained",
    "freeze_policy": "Freeze parameters before 1991-11-16; no within-tournament updates",
    "selection": "Protocol specified without fitting or scoring the 26 evaluation labels",
    "qualified_training_observations": 0,
    "qualified_calibration_observations": 0,
    "rating_compatibility": "Unverified: existing ratings mix unknown durations and final scores",
    "fit_requirements": (
        "Source-pinned regulation goals and nominal duration per observation; historical "
        "publication and input cutoffs; pre-match O/D/F reference populations; independently "
        "reviewed identifiability, sample sufficiency and out-of-time calibration"
    ),
    "forbidden_substitutes": ["2.6 * 80/90 treated as validated", "2007 temperature parameters"],
    "uncertainty": "Not estimable from qualified evidence; no intervals or accuracy published",
    "historical_publication_verified": False,
    "production_eligible": False,
    "probabilities": None,
    "accuracy": None,
    "log_loss": None,
    "brier_score": None,
    "blockers": list(BLOCKERS),
}


def inspect_case(record: dict[str, Any], cutoff: date, rating_complete: bool) -> dict[str, Any]:
    """Observe labels only for reporting; never use them as model inputs."""
    if (
        record["edition"] != 1991
        or type(record["regulation_minutes"]) is not int
        or record["regulation_minutes"] != 80
        or not date(1991, 11, 16) <= date.fromisoformat(record["date"]) <= date(1991, 11, 30)
        or cutoff >= date.fromisoformat(record["date"])
    ):
        raise ValueError("The isolated research protocol requires a pre-match 1991/80 cutoff")
    from football.evaluation import outcome

    observed = outcome(*record["regulation_score"])
    reasons = list(BLOCKERS)
    if not rating_complete:
        reasons.append("historical_ratings_insufficient")
    if record["completion_status"] != "completed":
        reasons.append("match_completion_unverified")
    return {
        "model_version": MODEL,
        "regulation_minutes": 80,
        "classification": "research_only",
        "validation_status": "evidence_blocked",
        "rating_complete": rating_complete,
        "rating_duration_compatible": False,
        "eligible": False,
        "observed_regulation_outcome": observed,
        "probabilities": None,
        "parameter_version": None,
        "calibration_through": None,
        "training_through": None,
        "exclusion_reasons": sorted(reasons),
        "source_sha256": record["source_sha256"],
        "cutoff": cutoff.isoformat(),
    }
