"""Competition contracts; external fields and validation preserved."""

from pydantic import Field, RootModel

from schemas.common import Contract


class CatalogCompetitionResponse(Contract):
    competition_id: int = Field(examples=[1])
    name: str = Field(examples=["FIFA Women's World Cup"])
    edition_label: str = Field(examples=["2023"])
    category: str = Field(examples=["women_senior_national"])


class CatalogCompetitionsResponse(RootModel[list[CatalogCompetitionResponse]]):
    pass
