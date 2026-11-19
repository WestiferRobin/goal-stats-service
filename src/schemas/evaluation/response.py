"""Validated evaluation manifest and per-case evidence; no persistence contracts."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from schemas.common import Contract
from schemas.evaluation.request import Assumption, Digest, Mode, PredictionModel

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class CaseResult(Contract):
    match_id: int = Field(gt=0)
    match_key: Digest
    match_date: date
    cutoff: date
    home_team_id: int = Field(gt=0)
    away_team_id: int = Field(gt=0)
    status: Literal["eligible", "excluded"]
    exclusion_reasons: list[str]
    warnings: list[str] = Field(default_factory=list)
    ranking_provenance: list[dict[str, object]] = Field(default_factory=list, max_length=2)
    rating_reconstruction: Literal["not_attempted", "complete", "insufficient", "unavailable"] = (
        "not_attempted"
    )
    probabilities: tuple[Probability, Probability, Probability] | None = None
    outcome: Literal["home_win", "draw", "away_win"] | None = None
    input_manifest: dict[str, object] | None = None
    label_provenance: dict[str, object] | None = None
    edition: int | None = None
    regulation_minutes: Literal[80, 90] = 90
    evaluation_protocol: str = "pregame-regulation-90-v1"
    evidence_record: dict[str, object] | None = None
    rating_evidence: dict[str, object] | None = None

    @model_validator(mode="after")
    def consistent_case(self) -> Self:
        if self.cutoff >= self.match_date:
            raise ValueError("Cutoff must predate the match")
        if self.status == "eligible":
            if self.regulation_minutes != 90:
                raise ValueError("The current model is not validated for 80-minute cases")
            if (
                self.exclusion_reasons
                or self.probabilities is None
                or self.outcome is None
                or self.input_manifest is None
                or self.label_provenance is None
            ):
                raise ValueError("Eligible cases require complete evidence and predictions")
            if abs(sum(self.probabilities) - 1) > 1e-9:
                raise ValueError("Probabilities must sum to one")
        elif (
            not self.exclusion_reasons or self.probabilities is not None or self.outcome is not None
        ):
            raise ValueError("Excluded cases cannot publish predictions or outcomes")
        return self


class BacktestResponse(Contract):
    mode: Mode
    status: Literal["available", "unavailable"]
    interpretation: str
    protocol_version: Literal["pregame-regulation-v1", "edition-regulation-v1"] = (
        "pregame-regulation-v1"
    )
    prediction_model_version: PredictionModel = "road-to-the-final-heuristic-v2"
    rating_model_version: str
    recovery_package_id: Literal["international-results-recovery-v1"] | None = None
    dataset_id: str
    dataset_hash: Digest
    package_hash: Digest
    source_hash: Digest
    manifest_hash: Digest
    evidence_kind: Literal["historical", "synthetic"]
    prediction_horizon: Literal[
        "pregame_90_minutes_no_extra_time_or_shootouts",
        "edition_specific_80_and_90_minutes",
        "pregame_80_minutes_model_unvalidated",
    ] = "pregame_90_minutes_no_extra_time_or_shootouts"
    cutoff_policy: Literal["strictly_before_match_day_previous_calendar_day_inclusive"] = (
        "strictly_before_match_day_previous_calendar_day_inclusive"
    )
    class_order: tuple[Literal["home_win"], Literal["draw"], Literal["away_win"]] = (
        "home_win",
        "draw",
        "away_win",
    )
    dataset_match_count: int = Field(ge=0, le=348)
    cohort_match_count: int = Field(ge=0, le=348)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=348)
    total_candidate_matches: int = Field(ge=0, le=348)
    eligible_matches: int = Field(ge=0, le=348)
    excluded_matches: int = Field(ge=0, le=348)
    exclusion_reasons: dict[str, int]
    accuracy: Probability | None
    log_loss: float | None = Field(ge=0, allow_inf_nan=False)
    brier_score: float | None = Field(ge=0, le=2, allow_inf_nan=False)
    confusion_matrix: list[list[Annotated[int, Field(strict=True, ge=0)]]] | None
    assumptions: list[Assumption]
    assumption_package_id: str | None
    cases: list[CaseResult] = Field(max_length=348)
    edition: int | None = None
    edition_summaries: list[dict[str, object]] = Field(default_factory=list)
    protocol_summaries: list[dict[str, object]] = Field(default_factory=list)
    metrics_horizon_minutes: Literal[90] = 90
    limitations: list[str]
    research_validation: dict[str, object] | None = None

    @model_validator(mode="after")
    def consistent_counts(self) -> Self:
        research = self.prediction_model_version != "road-to-the-final-heuristic-v2"
        if self.mode == "retrospective_replay" and not research:
            raise ValueError("Replay requires a research model")
        if research and (
            self.mode == "retrospective_assumptions"
            or (self.eligible_matches > 0 and self.mode != "retrospective_replay")
            or self.research_validation is None
            or self.research_validation.get("production_eligible") is not False
        ):
            raise ValueError("Research scoring requires explicit retrospective classification")
        if (
            self.cohort_match_count > self.dataset_match_count
            or self.total_candidate_matches
            != min(self.limit, max(0, self.cohort_match_count - self.offset))
        ):
            raise ValueError("Inconsistent cohort pagination")
        if self.total_candidate_matches != len(
            self.cases
        ) or self.eligible_matches + self.excluded_matches != len(self.cases):
            raise ValueError("Inconsistent evaluation counts")
        if self.eligible_matches != sum(c.status == "eligible" for c in self.cases):
            raise ValueError("Inconsistent eligible count")
        values = [self.accuracy, self.log_loss, self.brier_score, self.confusion_matrix]
        if (
            self.eligible_matches == 0
            and (self.status != "unavailable" or any(v is not None for v in values))
        ) or (
            self.eligible_matches > 0
            and (self.status != "available" or any(v is None for v in values))
        ):
            raise ValueError("Metrics availability must match eligible cases")
        if self.confusion_matrix is not None:
            matrix = self.confusion_matrix
            if (
                len(matrix) != 3
                or any(len(row) != 3 for row in matrix)
                or sum(sum(row) for row in matrix) != self.eligible_matches
            ):
                raise ValueError("Confusion matrix must account for all eligible cases")
            expected_accuracy = sum(matrix[i][i] for i in range(3)) / self.eligible_matches
            if self.accuracy is None or abs(self.accuracy - expected_accuracy) > 1e-9:
                raise ValueError("Accuracy must agree with the confusion matrix")
        return self
