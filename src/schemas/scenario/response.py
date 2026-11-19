"""Scenario response contracts; existing validation and serialization preserved."""

from datetime import datetime
from typing import Literal

from pydantic import Field, RootModel, ValidationInfo, field_validator

from schemas.scenario.base import SCENARIO_EXAMPLE, ScenarioConfig
from schemas.scenario.request import ScenarioCreate


class ScenarioResponse(ScenarioCreate):
    @field_validator("team1_shots_on_target", "team2_shots_on_target")
    @classmethod
    def consistent_shots(cls, value: int, info: ValidationInfo) -> int:
        """Read legacy persisted inputs without imposing new write-time relationships."""
        return value

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
