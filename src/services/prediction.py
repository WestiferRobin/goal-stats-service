"""Capture once, calculate outside a DB transaction, then append one saved result."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, NotFound

from exceptions.base import DomainError
from football.scenario_prediction import predict_inputs
from infra.repositories.prediction import PredictionRepository
from infra.repositories.scenario import ScenarioRepository
from infra.resources.db import Database
from models.prediction import Prediction
from models.scenario import Scenario
from schemas.prediction import (
    PredictionHistoryQuery,
    PredictionInputs,
    SavedEngineOutput,
    SavedPredictionResponse,
)


class ScenarioNotReady(DomainError):
    def __init__(self, error: ValidationError) -> None:
        # Only known schema field names are public; rejected values/details remain private.
        fields = sorted(
            {
                str(e["loc"][0])
                for e in error.errors()
                if e["loc"] and e["loc"][0] in PredictionInputs.model_fields
            }
        )
        self.public_detail = (
            "Scenario is not prediction-ready. Missing or invalid inputs: "
            + (", ".join(fields) if fields else "scenario state")
            + "."
        )
        super().__init__(self.public_detail)


class PredictionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _load_scenario(self, scenario_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            row = ScenarioRepository(session).get_projection(scenario_id)
            if row is None:
                raise NotFound()
            values = {
                column.name: getattr(row.scenario, column.name)
                for column in Scenario.__table__.columns
            }
            values.update(team1_name=row.team1_name, team2_name=row.team2_name)
            return values

    @staticmethod
    def _capture(values: dict[str, Any]) -> PredictionInputs:
        try:
            inputs = PredictionInputs.model_validate(values)
        except ValidationError as error:
            raise ScenarioNotReady(error) from None
        # Match the existing FootballService.match() adapter, without mutating the scenario.
        inputs.team1_shots = max(inputs.team1_shots, inputs.team1_shots_on_target)
        inputs.team2_shots = max(inputs.team2_shots, inputs.team2_shots_on_target)
        return inputs

    @staticmethod
    def _response(row: Prediction) -> dict[str, Any]:
        snapshot = row.input_snapshot
        output = {
            **row.details,
            "team1": snapshot["team1_name"],
            "team2": snapshot["team2_name"],
            "minute": snapshot["match_minute"],
            "status": snapshot["status"],
            "model": row.model_version,
            "probabilities": {
                "team1": row.team1_win_probability,
                "draw": row.draw_probability,
                "team2": row.team2_win_probability,
            },
            "expected_goals_remaining": {
                "team1": row.team1_expected_remaining_goals,
                "team2": row.team2_expected_remaining_goals,
            },
            "most_likely_score": [row.most_likely_team1_score, row.most_likely_team2_score],
        }
        return SavedPredictionResponse(
            prediction_id=row.prediction_id,
            scenario_id=row.scenario_id,
            generated_at=row.generated_at,
            model_version=row.model_version,
            input_snapshot=PredictionInputs.model_validate(snapshot),
            output=SavedEngineOutput.model_validate(output),
        ).model_dump(mode="json")

    def generate(self, scenario_id: int) -> dict[str, Any]:
        inputs = self._capture(self._load_scenario(scenario_id))
        # The SELECT transaction has ended. No locks/connections are held during computation.
        output = SavedEngineOutput.model_validate(predict_inputs(inputs))
        if (output.team1, output.team2, output.minute, output.status) != (
            inputs.team1_name,
            inputs.team2_name,
            inputs.match_minute,
            inputs.status,
        ):
            raise ValueError("Engine output does not match captured inputs")
        details = output.model_dump(
            mode="json",
            exclude={
                "team1",
                "team2",
                "minute",
                "status",
                "model",
                "probabilities",
                "expected_goals_remaining",
                "most_likely_score",
            },
        )
        try:
            with self.database.transaction() as session:
                row = Prediction(
                    scenario_id=scenario_id,
                    model_version=output.model,
                    team1_win_probability=output.probabilities.team1,
                    draw_probability=output.probabilities.draw,
                    team2_win_probability=output.probabilities.team2,
                    team1_expected_remaining_goals=output.expected_goals_remaining.team1,
                    team2_expected_remaining_goals=output.expected_goals_remaining.team2,
                    most_likely_team1_score=output.most_likely_score[0],
                    most_likely_team2_score=output.most_likely_score[1],
                    input_snapshot=inputs.model_dump(mode="json"),
                    details=details,
                )
                PredictionRepository(session).add(row)
                result = self._response(row)
            return result
        except IntegrityError:
            # A concurrent external deletion may remove the FK after the read transaction.
            raise Conflict() from None

    def get(self, prediction_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            row = PredictionRepository(session).get_by_id(prediction_id)
            if row is None:
                raise NotFound()
            return self._response(row)

    def history(self, scenario_id: int, query: PredictionHistoryQuery) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            if not ScenarioRepository(session).exists(scenario_id):
                raise NotFound()
            rows = PredictionRepository(session).history(
                scenario_id, limit=query.limit, offset=query.offset
            )
            return [self._response(row) for row in rows]
