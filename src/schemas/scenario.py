"""Flat scenario contracts: all statistics and rating snapshots are caller supplied."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, RootModel, model_validator

from schemas.common import CatalogID, Contract, Count, HistoryQuery, validate_possession


class ScenarioConfig(ConfigDict, total=False):
    """Typed flask-openapi3 extension for media-level examples."""

    openapi_extra: dict[str, JsonValue]


StrictCount = Annotated[Count, Field(strict=True)]
Percentage = Annotated[float, Field(strict=True, ge=0, le=100)]
ModifierTotal = Annotated[float, Field(strict=True, ge=-3000, le=3000)]
Rating = Annotated[float, Field(strict=True, ge=0, le=100)]
BodyID = Annotated[CatalogID, Field(strict=True)]


class ScenarioPath(Contract):
    scenario_id: CatalogID


class ScenarioQuery(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)
    team_id: CatalogID | None = None


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


class ScenarioResponse(ScenarioCreate):
    model_config = ScenarioConfig(
        openapi_extra={
            "example": {
                **SCENARIO_EXAMPLE,
                "scenario_id": 1,
                "created_at": "2026-10-10T19:00:00Z",
                "team1_name": "Example Team A",
                "team2_name": "Example Team B",
                "prediction_ready": True,
            }
        }
    )
    scenario_id: int
    created_at: datetime
    team1_name: str
    team2_name: str
    prediction_ready: Literal[True] = Field(
        default=True,
        description=(
            "Explicit rating snapshots are validated and stored. "
            "Use POST /api/v1/scenarios/{scenario_id}/predictions to generate and save."
        ),
    )


class ScenariosResponse(RootModel[list[ScenarioResponse]]):
    pass
