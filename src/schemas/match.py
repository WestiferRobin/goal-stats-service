"""Match contracts; external fields and validation preserved."""

import re
from datetime import date
from typing import Self

from pydantic import Field, RootModel, field_validator, model_validator

from schemas.common import CatalogID, Contract, HistoryQuery


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
