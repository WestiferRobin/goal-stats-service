"""Explicit assumptions for hypothetical knockout brackets."""

from typing import Self

from pydantic import Field, model_validator

from schemas.common import Contract
from schemas.scenario.base import BodyID, Rating


class SimulationTeam(Contract):
    team_id: BodyID
    offense: Rating
    defense: Rating
    form: Rating
    star_power: Rating
    clutch: Rating
    fifa_rank: BodyID | None = None


class TournamentRequest(Contract):
    teams: list[SimulationTeam] = Field(min_length=4, max_length=32)
    simulations: int = Field(default=1000, strict=True, ge=1000, le=2000)

    @model_validator(mode="after")
    def bracket(self) -> Self:
        if len(self.teams) not in {4, 8, 16, 32}:
            raise ValueError("Use a complete 4, 8, 16 or 32 team bracket")
        if len({team.team_id for team in self.teams}) != len(self.teams):
            raise ValueError("Teams must be unique")
        return self
