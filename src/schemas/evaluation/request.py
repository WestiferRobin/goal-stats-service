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
Mode = Literal["strict_historical", "retrospective_assumptions"]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]


class Assumption(Contract):
    match_key: Digest
    team_id: BodyID
    star_power: Rating
    clutch: Rating


class BacktestRequest(Contract):
    dataset_id: DatasetID
    mode: Mode = "strict_historical"
    edition: Literal[1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023] | None = None
    offset: int = Field(default=0, strict=True, ge=0, le=347)
    limit: int = Field(default=16, strict=True, ge=1, le=348)
    assumption_package_id: str | None = Field(default=None, min_length=1, max_length=80)
    assumptions: list[Assumption] = Field(default_factory=list, max_length=696)

    @model_validator(mode="after")
    def assumption_policy(self) -> Self:
        if self.dataset_id != FULL_DATASET and (
            self.edition is not None or self.limit > 16 or len(self.assumptions) > 32
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
