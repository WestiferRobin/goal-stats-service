"""Frontend-independent football request contracts."""

from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(ge=0, le=1000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Modifier(Contract):
    reason: str = Field(min_length=1, max_length=200)
    value: float = Field(ge=-100, le=100)


class TeamStats(Contract):
    goals: Count = 0
    possession: float = Field(default=50, ge=0, le=100)
    shots: Count = 0
    shots_on_target: Count = 0
    big_chances: Count = 0
    defender_blocks: Count = 0
    goalkeeper_saves: Count = 0
    corners: Count = 0
    yellow_cards: Count = 0
    red_cards: int = Field(default=0, ge=0, le=11)
    modifiers: list[Modifier] = Field(default_factory=list, max_length=30)


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
        if abs(self.team1_stats.possession + self.team2_stats.possession - 100) > 0.01:
            raise ValueError("Possession must total 100")
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


class HistoryQuery(Contract):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class SnapshotQuery(Matchup, HistoryQuery):
    pass


class Pair(Contract):
    team1: float
    team2: float


class OutcomeProbabilities(Pair):
    draw: float


class Scoreline(Contract):
    team1_goals: int
    team2_goals: int
    probability: float


class Confidence(Contract):
    percent: float
    label: str


class PredictionResponse(Contract):
    team1: str
    team2: str
    minute: int
    status: str
    probabilities: OutcomeProbabilities
    advancement: Pair
    expected_goals_remaining: Pair
    momentum_percent: Pair
    most_likely_score: list[int]
    top_scorelines: list[Scoreline]
    confidence: Confidence
    reasoning: list[str]
    model: str
