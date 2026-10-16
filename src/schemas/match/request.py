"""Match request contracts; existing validation and serialization preserved."""

import re
from datetime import date
from typing import Self

from pydantic import Field, field_validator, model_validator

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


class HistoricalComparison(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)
    team1_id: CatalogID
    team2_id: CatalogID

    @model_validator(mode="after")
    def distinct(self) -> Self:
        if self.team1_id == self.team2_id:
            raise ValueError("Choose two different teams")
        return self
