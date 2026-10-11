"""Frontend-independent football request contracts."""

import re
from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

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


def validate_possession(first: float, second: float) -> None:
    if abs(first + second - 100) > 0.01:
        raise ValueError("Possession must total 100")


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


# Normalized historical catalog; separate from prototype prediction inputs.
CatalogID = Annotated[int, Field(ge=1, le=2147483647)]


class CatalogTeamPath(Contract):
    team_id: CatalogID


class CatalogMatchPath(Contract):
    match_id: CatalogID


class CatalogMatchQuery(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)
    team_id: CatalogID | None = Field(default=None, description="Home or away participant")
    competition_id: CatalogID | None = None
    date_from: date | None = Field(default=None, description="Inclusive date, YYYY-MM-DD")
    date_to: date | None = Field(default=None, description="Inclusive date, YYYY-MM-DD")

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def calendar_date(cls, value: object) -> object:
        if isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not follow date_to")
        return self


class CatalogTeamResponse(Contract):
    team_id: int = Field(examples=[1])
    name: str = Field(examples=["New Zealand"])
    category: str = Field(examples=["women_senior_national"])
    offense: float | None = Field(examples=[None])
    defense: float | None = Field(examples=[None])
    form: float | None = Field(examples=[None])
    star_power: float | None = Field(examples=[None])
    clutch: float | None = Field(examples=[None])
    fifa_rank: int | None = Field(examples=[None])
    ranking_date: date | None = Field(examples=[None])
    prediction_ready: Literal[False] = Field(
        default=False,
        description="No supported prediction input path exists for normalized catalog IDs.",
    )


class CatalogCompetitionResponse(Contract):
    competition_id: int = Field(examples=[1])
    name: str = Field(examples=["FIFA Women's World Cup"])
    edition_label: str = Field(examples=["2023"])
    category: str = Field(examples=["women_senior_national"])


class CatalogMatchResponse(Contract):
    match_id: int = Field(examples=[1])
    match_date: date = Field(examples=["2023-07-20"])
    competition_id: int = Field(examples=[1])
    competition_name: str = Field(examples=["FIFA Women's World Cup"])
    edition_label: str = Field(examples=["2023"])
    home_team_id: int = Field(examples=[1])
    home_team_name: str = Field(examples=["New Zealand"])
    away_team_id: int = Field(examples=[2])
    away_team_name: str = Field(examples=["Norway"])
    home_score: int = Field(examples=[1])
    away_score: int = Field(examples=[0])
    score_basis: str = Field(examples=["including_extra_time_no_shootout"])
    neutral: bool | None = Field(examples=[False])
    city: str | None = Field(examples=["Auckland"])
    country: str | None = Field(examples=["New Zealand"])


class CatalogTeamsResponse(RootModel[list[CatalogTeamResponse]]):
    pass


class CatalogCompetitionsResponse(RootModel[list[CatalogCompetitionResponse]]):
    pass


class CatalogMatchesResponse(RootModel[list[CatalogMatchResponse]]):
    pass
