"""Team request contracts; existing validation and serialization preserved."""

import re
from datetime import date
from typing import Self

from pydantic import Field, field_validator, model_validator

from schemas.common import CatalogID, Contract


class CatalogTeamPath(Contract):
    team_id: CatalogID


class TeamSummaryQuery(Contract):
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
