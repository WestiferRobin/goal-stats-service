"""Capture once, calculate outside a DB transaction, then append one saved result."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Conflict, HTTPException, NotFound

from exceptions.base import DomainError, PredictionGenerationError
from football.scenario_prediction import predict_inputs, predict_state
from infra.repositories.prediction import PredictionRepository
from models.prediction import Prediction
from schemas.prediction import (
    PredictionHistoryQuery,
    PredictionInputs,
    SavedEngineOutput,
    SavedPredictionResponse,
)
from schemas.prediction.request import PredictionPreview
from services.scenario import ScenarioService
from services.team import TeamService


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
    def __init__(
        self,
        *,
        repo: PredictionRepository,
        scenario_service: ScenarioService,
        team_service: TeamService,
    ) -> None:
        if (
            repo.database is not scenario_service.database
            or repo.database is not team_service.database
        ):
            raise ValueError("Repositories must share the same Database instance")
        self.repo = repo
        self.scenario_service = scenario_service
        self.team_service = team_service

    def _load_scenario(self, scenario_id: int) -> dict[str, Any]:
        with self.repo.transaction() as session:
            return dict(
                self.scenario_service.capture_state_in_transaction(
                    session=session, scenario_id=scenario_id
                )
            )

    @staticmethod
    def _capture(values: dict[str, Any]) -> PredictionInputs:
        try:
            inputs = PredictionInputs.model_validate(values)
        except ValidationError as error:
            raise ScenarioNotReady(error) from None
        # Preserve reference shot normalization without mutating the saved scenario.
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
        try:
            return self._generate(scenario_id)
        except (DomainError, HTTPException):
            raise
        except Exception:
            raise PredictionGenerationError() from None

    def _generate(self, scenario_id: int) -> dict[str, Any]:
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
            with self.repo.transaction() as session:
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
                self.repo.add(session, row)
                result = self._response(row)
            return result
        except IntegrityError:
            # A concurrent external deletion may remove the FK after the read transaction.
            raise Conflict() from None

    def get(self, prediction_id: int) -> dict[str, Any]:
        with self.repo.transaction() as session:
            row = self.repo.get_by_id(session, prediction_id)
            if row is None:
                raise NotFound()
            return self._response(row)

    def history(self, scenario_id: int, query: PredictionHistoryQuery) -> list[dict[str, Any]]:
        with self.repo.transaction() as session:
            self.scenario_service.require_exists_in_transaction(
                session=session, scenario_id=scenario_id
            )
            rows = self.repo.history(session, scenario_id, limit=query.limit, offset=query.offset)
            return [self._response(row) for row in rows]

    def preview(self, body: PredictionPreview) -> dict[str, Any]:
        with self.repo.transaction() as session:
            names = self.team_service.capture_names_in_transaction(
                session=session, team_ids=(body.team1_id, body.team2_id)
            )
        values = body.model_dump()
        for side in (1, 2):
            values[f"team{side}_name"] = names[values[f"team{side}_id"]]
            values[f"team{side}_shots"] = max(
                values[f"team{side}_shots"], values[f"team{side}_shots_on_target"]
            )
        return SavedEngineOutput.model_validate(
            predict_state(values, extra_minute=body.extra_minute, status=body.status.upper())
        ).model_dump(mode="json")
