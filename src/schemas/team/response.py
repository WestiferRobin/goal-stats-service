"""Team response contracts; existing validation and serialization preserved."""

from datetime import date
from typing import Literal, Self

from pydantic import Field, RootModel, model_validator

from schemas.common import CatalogID, Contract
from schemas.team.request import TeamSummaryQuery


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
        description=(
            "Historical catalog membership alone does not supply complete prediction "
            "ratings; provide explicit scenario assumptions."
        ),
    )


class CatalogTeamsResponse(RootModel[list[CatalogTeamResponse]]):
    pass


class TeamSummaryResponse(Contract):
    """Provisional recorded-score semantics pending Mehla's confirmation.

    Scores include extra time and exclude shootout goals; ties count as draws.
    Appearances represent filtered World Cup editions. Available imported records
    do not establish complete historical coverage.
    """

    team_id: CatalogID
    name: str = Field(min_length=1)
    matches_played: int = Field(strict=True, ge=0)
    wins: int = Field(strict=True, ge=0)
    draws: int = Field(strict=True, ge=0)
    losses: int = Field(strict=True, ge=0)
    goals_for: int = Field(strict=True, ge=0)
    goals_against: int = Field(strict=True, ge=0)
    goal_difference: int = Field(strict=True)
    tournament_appearances: int = Field(strict=True, ge=0)
    filters: TeamSummaryQuery
    score_basis: Literal["including_extra_time_no_shootout"] | None
    result_definition: Literal["recorded_final_score"]
    coverage_status: Literal["available_records_only", "no_matching_records"]

    @model_validator(mode="after")
    def consistent_totals(self) -> Self:
        if self.wins + self.draws + self.losses != self.matches_played:
            raise ValueError("Results must total matches_played")
        if self.goal_difference != self.goals_for - self.goals_against:
            raise ValueError("goal_difference must equal goals_for minus goals_against")
        if self.tournament_appearances > self.matches_played:
            raise ValueError("Tournament appearances cannot exceed matches_played")
        if self.matches_played == 0:
            if self.goals_for or self.goals_against:
                raise ValueError("No matching records require zero goal totals")
            if self.score_basis is not None or self.coverage_status != "no_matching_records":
                raise ValueError("No matching records require null score basis and empty coverage")
        elif (
            self.tournament_appearances == 0
            or self.score_basis != "including_extra_time_no_shootout"
            or self.coverage_status != "available_records_only"
        ):
            raise ValueError("Matching records require appearances, supported scores and coverage")
        return self
