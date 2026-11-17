"""Bounded package selection; caller input can only be labeled assumptions."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from schemas.common import Contract
from schemas.scenario.base import BodyID, Rating

PILOT_DATASET = "womens-world-cup-2023-opening-pilot-v1"
FULL_DATASET = "womens-world-cup-full-v1"
DatasetID = Literal[
    "womens-world-cup-recorded-v1",
    "womens-world-cup-2023-opening-pilot-v1",
    "womens-world-cup-full-v1",
]
Mode = Literal["strict_historical", "retrospective_assumptions", "retrospective_replay"]
PredictionModel = Literal[
    "road-to-the-final-heuristic-v2",
    "odf-reweighted-poisson-research-v1",
    "odf-cross-goal-rate-research-v1",
    "odf-temperature-research-v1",
]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]


class Assumption(Contract):
    match_key: Digest
    team_id: BodyID
    star_power: Rating
    clutch: Rating


class BacktestRequest(Contract):
    dataset_id: DatasetID
    prediction_model_version: PredictionModel = "road-to-the-final-heuristic-v2"
    recovery_package_id: Literal["international-results-recovery-v1"] | None = None
    research_model_version: Literal["odf-exposure-80-evidence-blocked-v1"] | None = None
    mode: Mode = "strict_historical"
    edition: Literal[1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023] | None = None
    offset: int = Field(default=0, strict=True, ge=0, le=347)
    limit: int = Field(default=16, strict=True, ge=1, le=348)
    assumption_package_id: str | None = Field(default=None, min_length=1, max_length=80)
    assumptions: list[Assumption] = Field(default_factory=list, max_length=696)

    @model_validator(mode="after")
    def assumption_policy(self) -> Self:
        research = self.prediction_model_version != "road-to-the-final-heuristic-v2"
        if research and (
            self.dataset_id != FULL_DATASET
            or self.recovery_package_id != "international-results-recovery-v1"
            or self.mode == "retrospective_assumptions"
            or self.assumptions
            or self.assumption_package_id
        ):
            raise ValueError(
                "Research replay requires full recovered evidence and no assumed inputs"
            )
        if self.mode == "retrospective_replay" and not research:
            raise ValueError("Retrospective replay requires an explicit three-input research model")
        if self.research_model_version is not None and (
            self.dataset_id != FULL_DATASET or self.edition not in (None, 1991)
        ):
            raise ValueError("80-minute research selection requires the full package and 1991/all")
        if self.dataset_id != FULL_DATASET and (
            self.edition is not None
            or self.recovery_package_id is not None
            or self.limit > 16
            or len(self.assumptions) > 32
        ):
            raise ValueError("Full-cohort options require the full evidence package")
        if self.mode == "strict_historical" and (self.assumptions or self.assumption_package_id):
            raise ValueError("Strict mode does not accept hypothetical ratings")
        if self.mode == "retrospective_assumptions" and (
            (not self.assumptions and self.dataset_id not in (PILOT_DATASET, FULL_DATASET))
            or not self.assumption_package_id
            or not self.assumption_package_id.strip()
        ):
            raise ValueError("Explicit named assumptions are required")
        keys = [(a.match_key, a.team_id) for a in self.assumptions]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate assumptions")
        return self
