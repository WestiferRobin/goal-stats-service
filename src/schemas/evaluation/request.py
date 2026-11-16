"""Bounded package selection; caller input can only be labeled assumptions."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from schemas.common import Contract
from schemas.scenario.base import BodyID, Rating

DatasetID = Literal["womens-world-cup-recorded-v1"]
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
    offset: int = Field(default=0, strict=True, ge=0, le=347)
    limit: int = Field(default=16, strict=True, ge=1, le=16)
    assumption_package_id: str | None = Field(default=None, min_length=1, max_length=80)
    assumptions: list[Assumption] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def assumption_policy(self) -> Self:
        if self.mode == "strict_historical" and (self.assumptions or self.assumption_package_id):
            raise ValueError("Strict mode does not accept hypothetical ratings")
        if self.mode == "retrospective_assumptions" and (
            not self.assumptions
            or not self.assumption_package_id
            or not self.assumption_package_id.strip()
        ):
            raise ValueError("Explicit named assumptions are required")
        keys = [(a.match_key, a.team_id) for a in self.assumptions]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate assumptions")
        return self
