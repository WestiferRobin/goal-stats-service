"""Match response contracts; existing validation and serialization preserved."""

from datetime import date
from typing import Literal

from pydantic import Field, RootModel

from schemas.common import Contract


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


class CatalogMatchesResponse(RootModel[list[CatalogMatchResponse]]):
    pass


class HistoricalInsights(Contract):
    source: Literal["approved_historical_results"] = "approved_historical_results"
    team1_id: int
    team2_id: int
    team1_name: str
    team2_name: str
    head_to_head: list[CatalogMatchResponse]
    team1_history: list[CatalogMatchResponse]
    team2_history: list[CatalogMatchResponse]
    limit: int
    offset: int
    order: Literal["match_date_asc_match_id_asc"] = "match_date_asc_match_id_asc"
