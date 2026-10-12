"""Team contracts; external fields and validation preserved."""

from datetime import date
from typing import Literal

from pydantic import Field, RootModel

from schemas.common import CatalogID, Contract


class CatalogTeamPath(Contract):
    team_id: CatalogID


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


class CatalogTeamsResponse(RootModel[list[CatalogTeamResponse]]):
    pass
