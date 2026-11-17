"""Read-only evaluation of trusted packages. Observations never come from HTTP input."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from exceptions.base import DomainError
from football import team_ratings
from football.duration_research import MODEL as DURATION_MODEL
from football.duration_research import SPEC as DURATION_SPEC
from football.duration_research import inspect_case
from football.evaluation import metrics, outcome, probabilities
from football.scenario_prediction import predict_state
from infra.repositories.evaluation import EvaluationRepository, HistoricalCase
from schemas.engine import TeamStats
from schemas.evaluation.request import FULL_DATASET, PILOT_DATASET, BacktestRequest
from schemas.evaluation.response import BacktestResponse, CaseResult
from schemas.prediction.request import PredictionPreview
from services.evaluation_research import MANIFEST_SHA as RESEARCH_MANIFEST_SHA

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
    regulation_minutes: int | None = None
    completion_status: str | None = None
    provenance: dict[str, object] = field(default_factory=dict)


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

    Outcome evidence requires a reviewed package and dataset ID; rating-only additions
    require a separately versioned, pinned recovery package selected explicitly.
    Synthetic packages are injected only by tests and remain explicitly labeled.
    """

    dataset_id: str = DATASET
    evidence_kind: str = "historical"
    source_hash: str = team_ratings.SOURCE_SHA
    expected_matches: int = 348
    labels: dict[str, RegulationEvidence] = field(default_factory=dict)
    strengths: dict[str, dict[int, ObservedStrength]] = field(default_factory=dict)
    historical_availability_verified: bool = False
    match_keys: tuple[str, ...] = ()
    provenance: dict[str, object] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        value = asdict(self)
        # Preserve the original empty recorded-v1 package identity.
        if not self.match_keys and not self.provenance:
            del value["match_keys"], value["provenance"]
        return digest(value)


def approved_package(dataset_id: str) -> EvaluationPackage:
    if dataset_id == DATASET:
        return EvaluationPackage()
    if dataset_id not in (PILOT_DATASET, FULL_DATASET):
        raise EvaluationError("Unapproved package")
    from services.evaluation_pilot import load_pilot

    try:
        if dataset_id == FULL_DATASET:
            from services.evaluation_full import load_full

            return load_full()
        return load_pilot()
    except (ValueError, KeyError, TypeError, OSError):
        raise EvaluationError("Approved pilot evidence is unavailable") from None


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
        self.package = package

    def evaluate(self, body: BacktestRequest) -> dict[str, Any]:
        package = self.package or approved_package(body.dataset_id)
        if package.dataset_id != body.dataset_id:
            raise EvaluationError("Dataset identity mismatch")
        rating_source_hash = package.source_hash
        recovered_source: list[team_ratings.Result] | None = None
        full_records: dict[str, Any] = {}
        full_ratings: dict[str, Any] = {}
        if body.dataset_id == FULL_DATASET:
            from services.evaluation_full import assets

            try:
                _, registry, rating_artifact = assets()
                full_records = {r["match_key"]: r for r in registry["records"]}
                full_ratings = rating_artifact["populations"]
                if body.recovery_package_id is not None:
                    from services.evaluation_recovery import assets as recovery_assets

                    recovery_manifest, recovered, recovered_source = recovery_assets(
                        approved_source(), set(full_ratings)
                    )
                    full_ratings = recovered["populations"]
                    rating_source_hash = recovery_manifest["merged_source_hash"]
                    package = replace(
                        package,
                        provenance={**package.provenance, "rating_recovery": recovery_manifest},
                    )
            except (ValueError, KeyError, TypeError, OSError):
                raise EvaluationError("Full evidence assets unavailable") from None
        research_data: dict[str, Any] = {}
        research_cases: dict[str, Any] = {}
        research_results: dict[str, Any] = {}
        if body.prediction_model_version != PREDICTION_MODEL:
            from services.evaluation_research import assets as research_assets

            try:
                research_data, research_cases, research_results = research_assets()
                if set(research_cases) != set(full_records):
                    raise ValueError("Research cohort mismatch")
            except (ValueError, KeyError, TypeError, OSError):
                raise EvaluationError("Pinned research replay unavailable") from None
        with self.repo.transaction() as session:
            candidates = self.repo.candidates(session)
            if (
                len(candidates) != package.expected_matches
                or len(candidates) > 348
                or len({c.match_key for c in candidates}) != len(candidates)
            ):
                raise EvaluationError("Incomplete or duplicate dataset")
            cohort = candidates
            if package.match_keys:
                if any(
                    c.source_hash != package.source_hash or c.source_version != REVISION
                    for c in candidates
                ):
                    raise EvaluationError("Catalog source integrity mismatch")
                cohort = [c for c in candidates if c.match_key in package.match_keys]
                if len(cohort) != len(package.match_keys):
                    raise EvaluationError("Incomplete approved cohort")
            if body.edition is not None:
                cohort = [c for c in cohort if c.day.year == body.edition]
            selected = cohort[body.offset : body.offset + body.limit]
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
        if package.provenance.get("expected_dataset_hash", dataset_hash) != dataset_hash:
            raise EvaluationError("Approved catalog projection changed")
        permitted = {
            (c.match_key, identity) for c in selected for identity in (c.home_id, c.away_id)
        }
        if any((a.match_key, a.team_id) not in permitted for a in body.assumptions):
            raise EvaluationError("Assumptions must reference the selected cohort")
        assumption_map = {(a.match_key, a.team_id): a for a in body.assumptions}
        cases: list[CaseResult] = []
        fitted: dict[date, dict[str, dict[str, Any]]] = {}
        source: list[team_ratings.Result] | None = recovered_source
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
            population = full_ratings.get(cutoff.isoformat())
            if full_records:
                record = full_records[case.match_key]
                result.edition = record["edition"]
                result.regulation_minutes = record["regulation_minutes"]
                result.evaluation_protocol = f"pregame-regulation-{result.regulation_minutes}-v1"
                result.evidence_record = record
                if result.regulation_minutes == 80:
                    reasons.append("model_80_minute_horizon_unvalidated")
                if population is None:
                    result.rating_reconstruction = "unavailable"
                    reasons.append("historical_reconstruction_unavailable")
                else:
                    participants = {
                        n: population["ratings"].get(n)
                        for n in (case.source_home, case.source_away)
                    }
                    complete = all(
                        r is not None
                        and all(r[f] is not None for f in ("offense", "defense", "form"))
                        for r in participants.values()
                    )
                    result.rating_reconstruction = "complete" if complete else "insufficient"
                    result.rating_evidence = {
                        **{k: v for k, v in population.items() if k != "ratings"},
                        "participants": participants,
                        "rating_model": team_ratings.MODEL,
                        "source_hash": rating_source_hash,
                    }
                    if not complete:
                        reasons.append("historical_ratings_insufficient")
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
                if type(label.regulation_minutes) is not int or label.regulation_minutes != 90:
                    reasons.append("regulation_duration_incompatible")
                if label.completion_status != "completed":
                    reasons.append("match_completion_unverified")
            if research_cases:
                row = research_cases[case.match_key]
                if (
                    row["date"] != case.day.isoformat()
                    or row["cutoff"] != cutoff.isoformat()
                    or row["home"] != case.source_home
                    or row["away"] != case.source_away
                    or row["outcome_source_hash"] != full_records[case.match_key]["source_sha256"]
                    or population is None
                    or row["source_population_hash"] != population["source_population_hash"]
                    or row["rating_population_hash"] != population["population_hash"]
                ):
                    raise EvaluationError("Research case provenance mismatch")
                result.ranking_provenance = ranks[case.match_key]
                for rank in result.ranking_provenance:
                    if (
                        rank.get("published_on")
                        and str(rank["published_on"]) >= case.day.isoformat()
                    ):
                        reasons.append("ranking_cutoff_violation")
                if body.mode == "strict_historical":
                    reasons.append("historical_source_availability_unverified")
                if body.prediction_model_version not in row["predictions"]:
                    reasons.extend(row["exclusion_reasons"])
                    if result.regulation_minutes == 90 and row["rating_complete"]:
                        reasons.append("calibration_not_available_before_match")
                if body.research_model_version is not None and result.regulation_minutes == 80:
                    research = inspect_case(
                        full_records[case.match_key], cutoff, row["rating_complete"]
                    )
                    result.evidence_record = {**full_records[case.match_key], "research": research}
                    reasons.extend(research["exclusion_reasons"])
                if not reasons:
                    p = probabilities(row["predictions"][body.prediction_model_version])
                    assert label is not None
                    actual = outcome(label.home_score, label.away_score)
                    if actual != ("home_win", "draw", "away_win")[row["truth"]]:
                        raise EvaluationError("Research label mismatch")
                    result.status, result.probabilities, result.outcome = "eligible", p, actual
                    result.input_manifest = {
                        "classification": "research_only",
                        "publication_timing": "match_dates_only_retrospective",
                        "production_eligible": False,
                        "prediction_model_version": body.prediction_model_version,
                        "protocol_hash": research_data["protocol_hash"],
                        "research_manifest_sha256": RESEARCH_MANIFEST_SHA,
                        "period": row["period"],
                        "cutoff": row["cutoff"],
                        "inputs": row["inputs"],
                        "ranking_used": False,
                        "rating_source_hash": rating_source_hash,
                        "source_population_hash": row["source_population_hash"],
                        "rating_population_hash": row["rating_population_hash"],
                        "calibration": research_data["calibration"]
                        if body.prediction_model_version == "odf-temperature-research-v1"
                        else None,
                    }
                    scored.append((p, actual))
                result.exclusion_reasons = sorted(set(reasons))
                cases.append(CaseResult.model_validate(result.model_dump()))
                continue
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
            if body.research_model_version is not None and result.regulation_minutes == 80:
                research = inspect_case(
                    full_records[case.match_key], cutoff, result.rating_reconstruction == "complete"
                )
                result.evidence_record = {**full_records[case.match_key], "research": research}
                # This three-input interface does not require hypothetical Star/Clutch.
                reasons[:] = [
                    r
                    for r in reasons
                    if r
                    not in (
                        "historical_star_power_clutch_evidence_missing",
                        "explicit_star_power_clutch_assumptions_missing",
                        "regulation_duration_incompatible",
                        "model_80_minute_horizon_unvalidated",
                    )
                ]
                reasons.extend(research["exclusion_reasons"])
            # Excluded evidence cannot be rescued by a numerical result or user assumptions.
            if not reasons:
                result.rating_reconstruction = "unavailable"
                try:
                    if source is None:
                        source = approved_source()
                    earlier = [r for r in source if r.day <= cutoff]
                    if cutoff not in fitted:
                        fitted[cutoff] = (
                            population["ratings"]
                            if population is not None
                            else team_ratings.calculate(earlier, cutoff)
                        )
                    if population is not None and (
                        len(earlier) != population["source_rows"]
                        or digest([r.__dict__ for r in earlier])
                        != population["source_population_hash"]
                    ):
                        raise ValueError("Rating reference population changed")
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
                                "rating_source_hash": rating_source_hash,
                                "cutoff": cutoff.isoformat(),
                                "source_rows_before_cutoff": len(earlier),
                                "latest_source_day": max(
                                    (r.day.isoformat() for r in earlier), default=None
                                ),
                                "possession_convention": "50_percent_each_no_observed_possession",
                                "publication_timing": "verified"
                                if package.historical_availability_verified
                                else "match_dates_only_retrospective",
                                "evaluation_package": package.provenance,
                                "rating_reconstruction_hash": digest(
                                    {
                                        "model": team_ratings.MODEL,
                                        "source_hash": rating_source_hash,
                                        "cutoff": cutoff,
                                        "ratings": {
                                            n: ratings[n]
                                            for n in (case.source_home, case.source_away)
                                        },
                                    }
                                ),
                            }
                            scored.append((p, actual))
                except (ValueError, OSError):
                    reasons.append("historical_reconstruction_unavailable")
            result.exclusion_reasons = sorted(set(reasons))
            result.warnings = sorted(set(result.warnings))
            cases.append(CaseResult.model_validate(result.model_dump()))
        counts = Counter(reason for c in cases for reason in c.exclusion_reasons)
        result_body: dict[str, Any] = {
            "mode": body.mode,
            "prediction_model_version": body.prediction_model_version,
            "status": "available" if scored else "unavailable",
            "interpretation": (
                "Assumption-based retrospective analysis, "
                "not genuine historical forecasting evidence."
            )
            if body.mode == "retrospective_assumptions"
            else "Strict evidence-gated historical evaluation; unavailable cases are never scored.",
            "rating_model_version": team_ratings.MODEL,
            "dataset_id": package.dataset_id,
            "recovery_package_id": body.recovery_package_id,
            "dataset_hash": dataset_hash,
            "package_hash": package.hash,
            "source_hash": package.source_hash,
            "manifest_hash": digest(
                {
                    "protocol": PROTOCOL,
                    "prediction_model": body.prediction_model_version,
                    **(
                        {"research_manifest_sha256": RESEARCH_MANIFEST_SHA}
                        if research_cases
                        else {}
                    ),
                    "rating_model": team_ratings.MODEL,
                    "dataset_hash": dataset_hash,
                    "package_hash": package.hash,
                    "request": body.model_dump(
                        mode="json",
                        exclude={
                            k
                            for k in (
                                "recovery_package_id",
                                "research_model_version",
                                "prediction_model_version",
                            )
                            if getattr(body, k) is None
                            or (
                                k == "prediction_model_version"
                                and body.prediction_model_version == PREDICTION_MODEL
                            )
                        },
                    ),
                    "cases": [c.model_dump(mode="json") for c in cases],
                }
            ),
            "evidence_kind": package.evidence_kind,
            "dataset_match_count": len(candidates),
            "cohort_match_count": len(cohort),
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
                *(
                    [
                        "Two-match retrospective pilot; insufficient for meaningful model accuracy "
                        "conclusions. No prospective forecasting claim."
                    ]
                    if body.dataset_id == PILOT_DATASET
                    else []
                ),
                "Metrics cover this page only; combine eligible-case weighted pages only within "
                "the same model, horizon, mode and source versions.",
                "Rankings are optional; missing observations never borrow from older releases.",
                "Experimental ratings use recorded scores including extra time; "
                "they are not calibrated regulation forecasts.",
                "Recorded historical final scores alone do not establish regulation outcomes.",
                "Regulation labels and observed strengths require reviewed package evidence.",
            ],
        }
        if full_records:
            from football.backtesting_evidence import EDITION_COUNTS

            result_body.update(
                protocol_version="edition-regulation-v1",
                prediction_horizon="pregame_80_minutes_model_unvalidated"
                if body.edition == 1991
                else "edition_specific_80_and_90_minutes"
                if body.edition is None
                else "pregame_90_minutes_no_extra_time_or_shootouts",
                edition=body.edition,
                edition_summaries=[
                    self.summary(
                        [c for c in cases if c.edition == year], edition=year, catalog_total=total
                    )
                    for year, total in EDITION_COUNTS.items()
                    if body.edition in (None, year)
                ],
                protocol_summaries=[
                    self.summary(
                        [c for c in cases if c.regulation_minutes == minutes],
                        regulation_minutes=minutes,
                    )
                    for minutes in (80, 90)
                ],
            )
            result_body["limitations"].extend(
                [
                    "1991 uses an 80-minute protocol and is blocked pending model validation; "
                    "all published numerical metrics cover eligible 90-minute cases only.",
                    "RSSSF archive attribution and discrepancies are retained per case. "
                    "martj42 cites RSSSF; these are not independent observations.",
                    "Original regulations for 1991–2019 remain unacquired; reviewed duration "
                    "and observed knockout procedures are recorded separately.",
                ]
            )
            if body.research_model_version is not None:
                for group in result_body["protocol_summaries"]:
                    group["prediction_model_version"] = (
                        DURATION_MODEL
                        if group["regulation_minutes"] == 80
                        else body.prediction_model_version
                    )
                    if group["regulation_minutes"] == 80:
                        group["research_protocol"] = DURATION_SPEC
                result_body["limitations"].append(
                    "Selected 80-minute research interface has no defensible fitted parameters. "
                    "No 1991 probabilities or metrics are computed. Top-level model and metrics "
                    "describe only the preserved 90-minute path; protocol groups identify models."
                )
        if research_cases:
            from services.evaluation_research import diagnostics

            result_body["research_validation"] = diagnostics(
                research_data, research_results, body.edition
            )
            if body.mode == "strict_historical":
                result_body["research_validation"]["comparisons"] = {}
                result_body["research_validation"]["period_comparisons"] = {}
            result_body["interpretation"] = (
                "Research-only retrospective temporal replay; not independently validated, "
                "not strict historical accuracy or prospective forecasting."
                if body.mode == "retrospective_replay"
                else "Strict research scoring blocked: publication availability unverified."
            )
            for group in result_body["protocol_summaries"]:
                if group["regulation_minutes"] == 90:
                    group["prediction_model_version"] = body.prediction_model_version
            result_body["limitations"].append(
                "Research parameters and data are pinned to Prompt 3. Historical outcomes were "
                "previously exposed; calibration uses 2007 only, applicable from 2011 onward. "
                "Comparisons use explicitly identified common cohorts; diagnostics cover the "
                "selected cohort, while top-level metrics cover this page only."
            )
        return BacktestResponse.model_validate(result_body).model_dump(mode="json")

    @staticmethod
    def summary(cases: list[CaseResult], **identity: object) -> dict[str, Any]:
        scored = [
            (c.probabilities, c.outcome)
            for c in cases
            if c.probabilities is not None and c.outcome is not None
        ]
        return {
            **identity,
            "total": len(cases),
            "verified_labels": sum(c.label_provenance is not None for c in cases),
            "rating_complete": sum(c.rating_reconstruction == "complete" for c in cases),
            "eligible": len(scored),
            "excluded": len(cases) - len(scored),
            "exclusion_reasons": dict(
                sorted(Counter(r for c in cases for r in c.exclusion_reasons).items())
            ),
            **metrics(scored),
        }
