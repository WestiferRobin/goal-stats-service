"""Read-only evaluation of trusted packages. Observations never come from HTTP input."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from exceptions.base import DomainError
from football import team_ratings
from football.evaluation import metrics, outcome, probabilities
from football.scenario_prediction import predict_state
from infra.repositories.evaluation import EvaluationRepository, HistoricalCase
from schemas.engine import TeamStats
from schemas.evaluation.request import BacktestRequest
from schemas.evaluation.response import BacktestResponse, CaseResult
from schemas.prediction.request import PredictionPreview

PROTOCOL = "pregame-regulation-v1"
PREDICTION_MODEL = "road-to-the-final-heuristic-v2"
DATASET = "womens-world-cup-recorded-v1"
REVISION = "1855e313ae8bcd0330426e62c8e4cf15ce45077c"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class RegulationEvidence:
    day: date
    home: str
    away: str
    home_score: int
    away_score: int
    source: str
    source_hash: str
    definition: str = "observed_score_at_end_of_regulation"


@dataclass(frozen=True)
class ObservedStrength:
    star_power: float
    clutch: float
    available_on: date
    source: str
    source_hash: str


@dataclass(frozen=True)
class EvaluationPackage:
    """Server-owned approval boundary, never deserialized from a request.

    New evidence requires a reviewed, versioned package and a new dataset ID.
    Synthetic packages are injected only by tests and remain explicitly labeled.
    """

    dataset_id: str = DATASET
    evidence_kind: str = "historical"
    source_hash: str = team_ratings.SOURCE_SHA
    expected_matches: int = 348
    labels: dict[str, RegulationEvidence] = field(default_factory=dict)
    strengths: dict[str, dict[int, ObservedStrength]] = field(default_factory=dict)
    historical_availability_verified: bool = False

    @property
    def hash(self) -> str:
        return digest(asdict(self))


def approved_source() -> list[team_ratings.Result]:
    root = Path(__file__).resolve().parents[2]
    locations = [
        root / "data/raw/martj42-womens-results" / REVISION / "results.csv",
        root / "data/bootstrap/results.csv",
    ]
    for path in locations:
        if path.is_file() and path.stat().st_size <= 5_000_000:
            return team_ratings.read_results(path.read_bytes())
    raise ValueError("Approved rating source unavailable")


def pregame(
    case: HistoricalCase,
    ratings: dict[str, dict[str, Any]],
    ranks: list[dict[str, object]],
    special: list[dict[str, float]],
) -> dict[str, Any]:
    """Fixed 50/50 possession convention; all accumulated events zero, never final state."""
    values: dict[str, Any] = {"match_minute": 0, "extra_minute": 0, "status": ""}
    for side, name in enumerate((case.source_home, case.source_away), 1):
        prefix = f"team{side}_"
        values[prefix + "id"] = case.home_id if side == 1 else case.away_id
        values[prefix + "name"] = case.home if side == 1 else case.away
        for event in TeamStats.model_fields:
            if event != "modifiers":
                values[prefix + event] = 50 if event == "possession" else 0
        values[prefix + "modifier_total"] = 0
        values[prefix + "fifa_rank"] = ranks[side - 1]["rank"]
        for rating in ("offense", "defense", "form"):
            values[prefix + rating] = ratings[name][rating]
        values.update({prefix + key: value for key, value in special[side - 1].items()})
    # Validate the existing adapter's input contract without introducing storage.
    PredictionPreview.model_validate(
        {key: value for key, value in values.items() if not key.endswith("_name")}
    )
    return values


class EvaluationError(DomainError):
    public_detail = "The approved evaluation package is unavailable or inconsistent."


class EvaluationService:
    def __init__(
        self, repo: EvaluationRepository, package: EvaluationPackage | None = None
    ) -> None:
        self.repo = repo
        self.package = package or EvaluationPackage()

    def evaluate(self, body: BacktestRequest) -> dict[str, Any]:
        package = self.package
        if package.dataset_id != body.dataset_id:
            raise EvaluationError("Dataset identity mismatch")
        with self.repo.transaction() as session:
            candidates = self.repo.candidates(session)
            if (
                len(candidates) != package.expected_matches
                or len(candidates) > 348
                or len({c.match_key for c in candidates}) != len(candidates)
            ):
                raise EvaluationError("Incomplete or duplicate dataset")
            selected = candidates[body.offset : body.offset + body.limit]
            ranks = {
                c.match_key: [
                    self.repo.ranking(session, c.home_id, c.day),
                    self.repo.ranking(session, c.away_id, c.day),
                ]
                for c in selected
            }
        # No database connection remains open during fitting or prediction.
        dataset_hash = digest(
            [
                {k: v for k, v in asdict(c).items() if k not in {"match_id", "home_id", "away_id"}}
                for c in candidates
            ]
        )
        permitted = {
            (c.match_key, identity) for c in selected for identity in (c.home_id, c.away_id)
        }
        if any((a.match_key, a.team_id) not in permitted for a in body.assumptions):
            raise EvaluationError("Assumptions must reference the selected cohort")
        assumption_map = {(a.match_key, a.team_id): a for a in body.assumptions}
        cases: list[CaseResult] = []
        fitted: dict[date, dict[str, dict[str, Any]]] = {}
        source: list[team_ratings.Result] | None = None
        scored: list[tuple[tuple[float, float, float], str]] = []
        for case in selected:
            cutoff = case.day - timedelta(days=1)
            result = CaseResult.model_construct(
                match_id=case.match_id,
                match_key=case.match_key,
                match_date=case.day,
                cutoff=cutoff,
                home_team_id=case.home_id,
                away_team_id=case.away_id,
                status="excluded",
                exclusion_reasons=[],
            )
            reasons = result.exclusion_reasons
            label = package.labels.get(case.match_key)
            if case.source_hash != package.source_hash or (
                package.evidence_kind == "historical" and case.source_version != REVISION
            ):
                reasons.append("dataset_source_mismatch")
            if label is None:
                reasons.append("regulation_outcome_evidence_missing")
            elif (
                (label.day, label.home, label.away)
                != (case.day, case.source_home, case.source_away)
                or not label.source
                or not re.fullmatch(r"[a-f0-9]{64}", label.source_hash)
                or label.definition != "observed_score_at_end_of_regulation"
            ):
                reasons.append("regulation_outcome_evidence_invalid")
            else:
                try:
                    outcome(label.home_score, label.away_score)
                    result.label_provenance = asdict(label)
                except ValueError:
                    reasons.append("regulation_outcome_evidence_invalid")
            special = []
            special_provenance: list[dict[str, object]] = []
            for identity in (case.home_id, case.away_id):
                if body.mode == "retrospective_assumptions":
                    assumption = assumption_map.get((case.match_key, identity))
                    if assumption is None:
                        reasons.append("explicit_star_power_clutch_assumptions_missing")
                        continue
                    special.append(
                        {"star_power": assumption.star_power, "clutch": assumption.clutch}
                    )
                    special_provenance.append(
                        {"kind": "hypothetical_assumption", **assumption.model_dump()}
                    )
                else:
                    observed = package.strengths.get(case.match_key, {}).get(identity)
                    if (
                        observed is None
                        or observed.available_on >= case.day
                        or not observed.source
                        or not re.fullmatch(r"[a-f0-9]{64}", observed.source_hash)
                    ):
                        reasons.append("historical_star_power_clutch_evidence_missing")
                        continue
                    special.append({"star_power": observed.star_power, "clutch": observed.clutch})
                    special_provenance.append(
                        {"kind": "historical_observation", **asdict(observed)}
                    )
            if body.mode == "strict_historical" and not package.historical_availability_verified:
                reasons.append("historical_source_availability_unverified")
            rank_evidence = ranks[case.match_key]
            result.ranking_provenance = rank_evidence
            for rank in rank_evidence:
                if rank["rank"] is None:
                    result.warnings.append(str(rank["reason"]))
                if (
                    rank.get("published_on")
                    and date.fromisoformat(str(rank["published_on"])) >= case.day
                ):
                    reasons.append("ranking_cutoff_violation")
            # Excluded evidence cannot be rescued by a numerical result or user assumptions.
            if not reasons:
                result.rating_reconstruction = "unavailable"
                try:
                    if source is None:
                        source = approved_source()
                    earlier = [r for r in source if r.day <= cutoff]
                    if cutoff not in fitted:
                        fitted[cutoff] = team_ratings.calculate(earlier, cutoff)
                    ratings = fitted[cutoff]
                    if any(
                        name not in ratings
                        or any(ratings[name][f] is None for f in ("offense", "defense", "form"))
                        for name in (case.source_home, case.source_away)
                    ):
                        result.rating_reconstruction = "insufficient"
                        reasons.append("historical_ratings_insufficient")
                    else:
                        result.rating_reconstruction = "complete"
                        values = pregame(case, ratings, rank_evidence, special)
                        prediction = predict_state(values)
                        if prediction["model"] != PREDICTION_MODEL:
                            reasons.append("prediction_model_incompatible")
                        else:
                            p = probabilities(
                                [prediction["probabilities"][k] for k in ("team1", "draw", "team2")]
                            )
                            assert label is not None
                            actual = outcome(label.home_score, label.away_score)
                            result.status, result.probabilities, result.outcome = (
                                "eligible",
                                p,
                                actual,
                            )
                            result.input_manifest = {
                                "inputs": values,
                                "ratings": {
                                    n: ratings[n] for n in (case.source_home, case.source_away)
                                },
                                "ranking_evidence": rank_evidence,
                                "special_ratings": special_provenance,
                                "rating_source_hash": package.source_hash,
                                "cutoff": cutoff.isoformat(),
                                "source_rows_before_cutoff": len(earlier),
                                "latest_source_day": max(
                                    (r.day.isoformat() for r in earlier), default=None
                                ),
                                "possession_convention": "50_percent_each_no_observed_possession",
                                "publication_timing": "verified"
                                if package.historical_availability_verified
                                else "match_dates_only_retrospective",
                            }
                            scored.append((p, actual))
                except (ValueError, OSError):
                    reasons.append("historical_reconstruction_unavailable")
            result.exclusion_reasons = sorted(set(reasons))
            result.warnings = sorted(set(result.warnings))
            cases.append(CaseResult.model_validate(result.model_dump()))
        counts = Counter(reason for c in cases for reason in c.exclusion_reasons)
        result_body = {
            "mode": body.mode,
            "status": "available" if scored else "unavailable",
            "interpretation": (
                "Assumption-based retrospective analysis, "
                "not genuine historical forecasting evidence."
            )
            if body.mode == "retrospective_assumptions"
            else "Strict evidence-gated historical evaluation; unavailable cases are never scored.",
            "rating_model_version": team_ratings.MODEL,
            "dataset_id": package.dataset_id,
            "dataset_hash": dataset_hash,
            "package_hash": package.hash,
            "source_hash": package.source_hash,
            "manifest_hash": digest(
                {
                    "protocol": PROTOCOL,
                    "prediction_model": PREDICTION_MODEL,
                    "rating_model": team_ratings.MODEL,
                    "dataset_hash": dataset_hash,
                    "package_hash": package.hash,
                    "request": body.model_dump(mode="json"),
                    "cases": [c.model_dump(mode="json") for c in cases],
                }
            ),
            "evidence_kind": package.evidence_kind,
            "dataset_match_count": len(candidates),
            "offset": body.offset,
            "limit": body.limit,
            "total_candidate_matches": len(selected),
            "eligible_matches": len(scored),
            "excluded_matches": len(selected) - len(scored),
            "exclusion_reasons": dict(sorted(counts.items())),
            **metrics(scored),
            "assumptions": body.assumptions,
            "assumption_package_id": body.assumption_package_id,
            "cases": cases,
            "limitations": [
                "Metrics cover this page only; combine page metrics using eligible-case weights.",
                "Rankings are optional; missing observations never borrow from older releases.",
                "Experimental ratings use recorded scores including extra time; "
                "they are not calibrated regulation forecasts.",
                "Recorded historical final scores alone do not establish regulation outcomes.",
                "Regulation labels and observed strengths require reviewed package evidence.",
            ],
        }
        return BacktestResponse.model_validate(result_body).model_dump(mode="json")
