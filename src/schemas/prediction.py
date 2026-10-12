"""Saved prediction contracts reuse the existing engine report shape."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, RootModel, field_validator, model_validator

from schemas.common import CatalogID, Contract, HistoryQuery
from schemas.engine import Confidence, OutcomeProbabilities, Pair, PredictionResponse, Scoreline
from schemas.scenario import ScenarioResponse

Probability = Annotated[float, Field(ge=0, le=1)]
FinalScore = Annotated[int, Field(strict=True, ge=0, le=32767)]


class PredictionPath(Contract):
    prediction_id: CatalogID


class PredictionHistoryQuery(HistoryQuery):
    offset: int = Field(default=0, ge=0, le=9223372036854775807)


class PredictionInputs(ScenarioResponse):
    """Copied scenario values with effective shots normalization and fixed adapter defaults."""

    adapter_version: Literal["scenario-v1"] = "scenario-v1"
    extra_minute: Literal[0] = 0
    status: Literal[""] = ""


class ValidProbabilities(OutcomeProbabilities):
    team1: Probability
    draw: Probability
    team2: Probability

    @model_validator(mode="after")
    def sums_to_one(self) -> Self:
        if abs(self.team1 + self.draw + self.team2 - 1) > 1e-9:
            raise ValueError("Probability sum must equal 1 within 1e-9")
        return self


class ValidPair(Pair):
    team1: Probability
    team2: Probability


class ExpectedGoals(Pair):
    team1: float = Field(ge=0)
    team2: float = Field(ge=0)


class PercentPair(Pair):
    team1: float = Field(ge=0, le=100)
    team2: float = Field(ge=0, le=100)


class ValidScoreline(Scoreline):
    team1_goals: FinalScore
    team2_goals: FinalScore
    probability: Probability


class ValidConfidence(Confidence):
    percent: float = Field(ge=0, le=100)


class SavedEngineOutput(PredictionResponse):
    probabilities: ValidProbabilities = Field(
        description="Finite fractions 0–1; sum equals 1 within absolute tolerance 1e-9."
    )
    advancement: ValidPair
    expected_goals_remaining: ExpectedGoals
    momentum_percent: PercentPair
    most_likely_score: list[FinalScore] = Field(min_length=2, max_length=2)
    confidence: ValidConfidence
    model: str = Field(min_length=1, max_length=80, pattern=r"\S")

    @field_validator("top_scorelines")
    @classmethod
    def valid_scorelines(cls, value: list[Scoreline]) -> list[Scoreline]:
        return [ValidScoreline.model_validate(row.model_dump()) for row in value]


class SavedPredictionResponse(Contract):
    prediction_id: int
    scenario_id: int
    generated_at: datetime
    model_version: str
    input_snapshot: PredictionInputs = Field(
        description="Immutable effective inputs, including team names and normalized shots."
    )
    output: SavedEngineOutput = Field(
        description="Saved report: probability fractions; confidence and momentum percentages."
    )


class SavedPredictionsResponse(RootModel[list[SavedPredictionResponse]]):
    pass
