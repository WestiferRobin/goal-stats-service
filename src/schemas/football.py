"""Football contracts; external fields and validation preserved."""

from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from schemas.common import Contract, HistoryQuery, validate_possession
from schemas.engine import TeamStats


class Matchup(Contract):
    team1: str = Field(min_length=1, max_length=100)
    team2: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct(self) -> Self:
        if self.team1.strip().casefold() == self.team2.strip().casefold():
            raise ValueError("Choose two different teams")
        return self


class PredictionRequest(Matchup):
    minute: int = Field(default=0, ge=0, le=120)
    extra_minute: int = Field(default=0, ge=0, le=30)
    status: str = Field(default="", max_length=10)
    team1_stats: TeamStats = Field(default_factory=TeamStats)
    team2_stats: TeamStats = Field(default_factory=TeamStats)

    @model_validator(mode="after")
    def possession_total(self) -> Self:
        validate_possession(self.team1_stats.possession, self.team2_stats.possession)
        return self


class TournamentRequest(Contract):
    teams: list[str] = Field(min_length=4, max_length=32)
    simulations: int = Field(default=1000, ge=1000, le=2000)

    @model_validator(mode="after")
    def bracket(self) -> Self:
        if len(self.teams) not in {4, 8, 16, 32}:
            raise ValueError("Use a complete 4, 8, 16 or 32 team bracket")
        if len({name.strip().casefold() for name in self.teams}) != len(self.teams):
            raise ValueError("Teams must be unique")
        return self


class SnapshotPath(Contract):
    snapshot_id: UUID


class SnapshotQuery(Matchup, HistoryQuery):
    pass
