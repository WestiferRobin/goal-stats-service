"""Offline feasibility inventory. Approved observations are not special ratings."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from football import team_ratings
from research.special_ratings import SPEC, Observation, Source, clutch, digest, star_power
from services import evaluation_full, evaluation_recovery

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "data/research/historical-special-ratings-v1"


def build() -> dict[str, Any]:
    original, registry, before = evaluation_full.assets()
    raw = (
        ROOT
        / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv"
    )
    recovery, after, _ = evaluation_recovery.assets(
        team_ratings.read_results(raw.read_bytes()), set(before["populations"])
    )
    observations = []
    for record in registry["records"]:
        if record["regulation_minutes"] != 90 or record["stage"] == "third_place":
            continue
        source = Source(
            url=record["source_url"],
            publisher="RSSSF",
            revision=record["source_revision"],
            sha256=record["source_sha256"],
            retrieved_on=date(2026, 11, 16),
            rights_basis="Previously approved attributed archive in womens-world-cup-full-v1",
            published_on=None,
            publication_verified=False,
        )
        for side, other, index in [("home", "away", 0), ("away", "home", 1)]:
            observations.append(
                Observation(
                    match_key=record["match_key"],
                    day=date.fromisoformat(record["date"]),
                    edition=record["edition"],
                    team=record[side],
                    opponent=record[other],
                    stage=record["stage"],
                    context_known_on=None,
                    regulation_minutes=90,
                    goals_for=record["regulation_score"][index],
                    goals_against=record["regulation_score"][1 - index],
                    source=source,
                )
            )
    cases = []
    for record in registry["records"]:
        cutoff = date.fromisoformat(record["date"]) - timedelta(days=1)
        participants = []
        for side in ["home", "away"]:
            team = record[side]
            estimate = clutch(team, cutoff, tuple(observations))
            participants.append(
                {
                    "team": team,
                    "team_id": record[side + "_team_id"],
                    "star": star_power(team, cutoff, None, None),
                    "clutch": estimate,
                    "retrospective_context_sample_ready": not any(
                        r in estimate["reasons"]
                        for r in [
                            "insufficient_pressure_control_or_edition_sample",
                            "no_recent_pressure_observation",
                        ]
                    ),
                }
            )

        def complete(
            populations: dict[str, Any], cutoff: date = cutoff, record: dict[str, Any] = record
        ) -> bool:
            population = populations["populations"][cutoff.isoformat()]["ratings"]
            return all(
                population.get(record[s], {}).get(field) is not None
                for s in ["home", "away"]
                for field in ["offense", "defense", "form"]
            )

        cases.append(
            {
                "match_id": record["match_id"],
                "match_key": record["match_key"],
                "edition": record["edition"],
                "date": record["date"],
                "cutoff": cutoff.isoformat(),
                "participants": participants,
                "original_odf_complete": complete(before),
                "recovered_odf_complete": complete(after),
                "both_computable": False,
                "production_eligible": False,
            }
        )
    editions = []
    for year in sorted({c["edition"] for c in cases}):
        subset = [c for c in cases if c["edition"] == year]
        participants = [p for c in subset for p in c["participants"]]
        editions.append(
            {
                "edition": year,
                "matches": len(subset),
                "teams": len({p["team"] for p in participants}),
                "teams_with_sufficient_star_evidence": [],
                "teams_with_sufficient_clutch_evidence": [],
                "star_computable_cases": 0,
                "clutch_computable_cases": 0,
                "both_computable_cases": 0,
                "missing_star_team_cases": len(participants),
                "missing_clutch_team_cases": len(participants),
                "uncertain_numeric_estimates": 0,
                "retrospective_context_sample_ready_team_cases": sum(
                    p["retrospective_context_sample_ready"] for p in participants
                ),
                "retrospective_context_sample_ready_matches": sum(
                    all(p["retrospective_context_sample_ready"] for p in c["participants"])
                    for c in subset
                ),
                "original_odf_complete": sum(c["original_odf_complete"] for c in subset),
                "recovered_odf_complete": sum(c["recovered_odf_complete"] for c in subset),
                "limitations": [
                    "no_verified_roster_availability_and_role_impact_reference",
                    "no_independent_90_minute_baseline_or_verified_context_publication",
                ],
            }
        )
    return {
        "package_id": "historical-special-ratings-v1",
        "method_hash": digest(SPEC),
        "original_manifest_sha256": evaluation_full.MANIFEST_SHA256,
        "recovery_manifest_sha256": evaluation_recovery.MANIFEST_SHA256,
        "original_registry_sha256": original["registry_sha256"],
        "recovery_merged_source_hash": recovery["merged_source_hash"],
        "approved_recovery_additional_special_observations": 0,
        "observation_kind": (
            "direct_archived_regulation_results_with_unverified_historical_publication"
        ),
        "derived_numeric_estimates": 0,
        "hypothetical_assumptions": 0,
        "total_cases": len(cases),
        "editions": editions,
        "cases": cases,
    }
