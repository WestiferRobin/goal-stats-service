"""Prediction request contracts; existing validation and serialization preserved."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from schemas.common import CatalogID, Contract, HistoryQuery
from schemas.scenario.base import BodyID, Rating, ScenarioState


class PredictionPath(Contract):
    prediction_id: CatalogID


class PredictionHistoryQuery(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)


class PredictionPreview(ScenarioState):
    """Explicit hypothetical inputs; no scenario or prediction is persisted."""

    team1_id: BodyID
    team2_id: BodyID
    extra_minute: Annotated[int, Field(strict=True, ge=0, le=30)] = 0
    status: str = Field(default="", max_length=10)
    team1_offense: Rating
    team1_defense: Rating
    team1_form: Rating
    team1_star_power: Rating
    team1_clutch: Rating
    team1_fifa_rank: BodyID | None = None
    team2_offense: Rating
    team2_defense: Rating
    team2_form: Rating
    team2_star_power: Rating
    team2_clutch: Rating
    team2_fifa_rank: BodyID | None = None

    @model_validator(mode="after")
    def distinct_teams(self) -> Self:
        if self.team1_id == self.team2_id:
            raise ValueError("Choose two different teams")
        return self
