"""Competition response contracts; existing validation and serialization preserved."""

from typing import Literal

from pydantic import Field, RootModel

from schemas.common import Contract


class CatalogCompetitionResponse(Contract):
    competition_id: int = Field(examples=[1])
    name: str = Field(examples=["FIFA Women's World Cup"])
    edition_label: str = Field(examples=["2023"])
    category: str = Field(examples=["women_senior_national"])


class CatalogCompetitionsResponse(RootModel[list[CatalogCompetitionResponse]]):
    pass


class SimulationResult(Contract):
    team: str
    fifa_rank: int | None
    semifinal_probability: float = Field(ge=0, le=100)
    final_probability: float = Field(ge=0, le=100)
    champion_probability: float = Field(ge=0, le=100)


class SimulationFinal(Contract):
    team1: str
    team2: str
    probability: float = Field(ge=0, le=100)


class TournamentResponse(Contract):
    kind: Literal["hypothetical_knockout"] = "hypothetical_knockout"
    results: list[SimulationResult]
    predicted_champion: str
    simulations: int
    most_common_final: SimulationFinal | None
    probability_unit: Literal["percent"] = "percent"
