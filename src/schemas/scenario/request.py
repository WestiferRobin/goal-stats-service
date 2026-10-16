"""Scenario request contracts; existing validation and serialization preserved."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from schemas.common import CatalogID, Contract, HistoryQuery
from schemas.scenario.base import (
    SCENARIO_EXAMPLE,
    BodyID,
    ModifierTotal,
    Percentage,
    Rating,
    ScenarioConfig,
    ScenarioState,
    StrictCount,
)


class ScenarioPath(Contract):
    scenario_id: CatalogID


class ScenarioQuery(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)
    team_id: CatalogID | None = None


class ScenarioCreate(ScenarioState):
    model_config = ScenarioConfig(
        json_schema_extra={"examples": [SCENARIO_EXAMPLE]},
        openapi_extra={"example": SCENARIO_EXAMPLE},
    )
    title: str | None = Field(default=None, min_length=1, max_length=120)
    team1_id: BodyID
    team2_id: BodyID
    match_id: BodyID | None = None
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


class ScenarioPatch(Contract):
    """Omitted fields remain unchanged; explicit null and empty patches are rejected."""

    model_config = ScenarioConfig(openapi_extra={"example": {"match_minute": 70, "team1_goals": 1}})

    match_minute: Annotated[int, Field(strict=True, ge=0, le=120)] | None = None
    team1_goals: StrictCount | None = None
    team1_shots: StrictCount | None = None
    team1_shots_on_target: StrictCount | None = None
    team1_big_chances: StrictCount | None = None
    team1_defender_blocks: StrictCount | None = None
    team1_goalkeeper_saves: StrictCount | None = None
    team1_corners: StrictCount | None = None
    team1_yellow_cards: StrictCount | None = None
    team1_red_cards: Annotated[int, Field(strict=True, ge=0, le=11)] | None = None
    team1_possession: Percentage | None = None
    team1_modifier_total: ModifierTotal | None = None
    team2_goals: StrictCount | None = None
    team2_shots: StrictCount | None = None
    team2_shots_on_target: StrictCount | None = None
    team2_big_chances: StrictCount | None = None
    team2_defender_blocks: StrictCount | None = None
    team2_goalkeeper_saves: StrictCount | None = None
    team2_corners: StrictCount | None = None
    team2_yellow_cards: StrictCount | None = None
    team2_red_cards: Annotated[int, Field(strict=True, ge=0, le=11)] | None = None
    team2_possession: Percentage | None = None
    team2_modifier_total: ModifierTotal | None = None

    @model_validator(mode="after")
    def nonempty_nonnull(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Supply at least one non-null match-state field")
        return self
