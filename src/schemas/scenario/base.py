"""Scenario base contracts; existing validation and serialization preserved."""

from typing import Annotated, Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

from schemas.common import CatalogID, Contract, Count, validate_possession


class ScenarioConfig(ConfigDict, total=False):
    """Typed flask-openapi3 extension for media-level examples."""

    openapi_extra: dict[str, JsonValue]


StrictCount = Annotated[Count, Field(strict=True)]


Percentage = Annotated[float, Field(strict=True, ge=0, le=100)]


ModifierTotal = Annotated[float, Field(strict=True, ge=-3000, le=3000)]


Rating = Annotated[float, Field(strict=True, ge=0, le=100)]


BodyID = Annotated[CatalogID, Field(strict=True)]


class ScenarioState(Contract):
    match_minute: Annotated[int, Field(strict=True, ge=0, le=120)]
    team1_goals: StrictCount
    team1_shots: StrictCount
    team1_shots_on_target: StrictCount
    team1_big_chances: StrictCount
    team1_defender_blocks: StrictCount
    team1_goalkeeper_saves: StrictCount
    team1_corners: StrictCount
    team1_yellow_cards: StrictCount
    team1_red_cards: Annotated[int, Field(strict=True, ge=0, le=11)]
    team1_possession: Percentage
    team1_modifier_total: ModifierTotal = 0
    team2_goals: StrictCount
    team2_shots: StrictCount
    team2_shots_on_target: StrictCount
    team2_big_chances: StrictCount
    team2_defender_blocks: StrictCount
    team2_goalkeeper_saves: StrictCount
    team2_corners: StrictCount
    team2_yellow_cards: StrictCount
    team2_red_cards: Annotated[int, Field(strict=True, ge=0, le=11)]
    team2_possession: Percentage
    team2_modifier_total: ModifierTotal = 0

    @model_validator(mode="after")
    def consistent_possession(self) -> Self:
        validate_possession(self.team1_possession, self.team2_possession)
        return self


SCENARIO_EXAMPLE: dict[str, JsonValue] = {
    "title": "Documentation example — synthetic inputs",
    "team1_id": 1,
    "team2_id": 2,
    "match_id": None,
    "match_minute": 65,
    "team1_goals": 0,
    "team1_shots": 0,
    "team1_shots_on_target": 0,
    "team1_big_chances": 0,
    "team1_defender_blocks": 0,
    "team1_goalkeeper_saves": 0,
    "team1_corners": 0,
    "team1_yellow_cards": 0,
    "team1_red_cards": 0,
    "team1_possession": 50,
    "team1_offense": 70,
    "team1_defense": 70,
    "team1_form": 70,
    "team1_star_power": 70,
    "team1_clutch": 70,
    "team1_fifa_rank": None,
    "team1_modifier_total": 0,
    "team2_goals": 0,
    "team2_shots": 0,
    "team2_shots_on_target": 0,
    "team2_big_chances": 0,
    "team2_defender_blocks": 0,
    "team2_goalkeeper_saves": 0,
    "team2_corners": 0,
    "team2_yellow_cards": 0,
    "team2_red_cards": 0,
    "team2_possession": 50,
    "team2_offense": 70,
    "team2_defense": 70,
    "team2_form": 70,
    "team2_star_power": 70,
    "team2_clutch": 70,
    "team2_fifa_rank": None,
    "team2_modifier_total": 0,
}
