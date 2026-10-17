"""Scenario response contracts; existing validation and serialization preserved."""

from datetime import datetime
from typing import Literal

from pydantic import Field, RootModel

from schemas.scenario.base import SCENARIO_EXAMPLE, ScenarioConfig
from schemas.scenario.request import ScenarioCreate


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
