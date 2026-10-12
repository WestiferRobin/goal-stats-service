"""PostgreSQL scenario operations using the application's existing unit of work."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from infra.repositories.match import MatchRepository
from infra.repositories.scenario import ScenarioProjection, ScenarioRepository
from infra.repositories.team import TeamRepository
from infra.resources.db import Database
from models.scenario import Scenario
from schemas.scenario import (
    ScenarioCreate,
    ScenarioPatch,
    ScenarioQuery,
    ScenarioResponse,
    ScenarioState,
)


class ScenarioService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _response(row: ScenarioProjection) -> dict[str, Any]:
        values = {
            column.name: getattr(row.scenario, column.name) for column in Scenario.__table__.columns
        }
        values.update(team1_name=row.team1_name, team2_name=row.team2_name)
        return ScenarioResponse.model_validate(values).model_dump(mode="json")

    def _get(self, session: Session, scenario_id: int) -> dict[str, Any]:
        row = ScenarioRepository(session).get_projection(scenario_id)
        if row is None:
            raise NotFound()
        return self._response(row)

    def create(self, body: ScenarioCreate) -> dict[str, Any]:
        try:
            with self.database.transaction() as session:
                # Hold key-share locks until commit so references cannot disappear after validation.
                teams = TeamRepository(session).get_participants(
                    [body.team1_id, body.team2_id], for_key_share=True
                )
                if len(teams) != 2:
                    raise NotFound()
                if body.match_id is not None:
                    match = MatchRepository(session).get_by_id(body.match_id, for_share=True)
                    if match is None:
                        raise NotFound()
                    if {match.home_team_id, match.away_team_id} != {body.team1_id, body.team2_id}:
                        raise BadRequest()
                # Explicit caller snapshots only. No lookup/copy of prototype or catalog ratings.
                row = Scenario(**body.model_dump())
                ScenarioRepository(session).add(row)
                result = self._get(session, row.scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None

    def get(self, scenario_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            return self._get(session, scenario_id)

    def list(self, query: ScenarioQuery) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            return [
                self._response(row)
                for row in ScenarioRepository(session).list(**query.model_dump())
            ]

    def update(self, scenario_id: int, body: ScenarioPatch) -> dict[str, Any]:
        try:
            with self.database.transaction() as session:
                row = ScenarioRepository(session).get_by_id(scenario_id, for_update=True)
                if row is None:
                    raise NotFound()
                values = {name: getattr(row, name) for name in ScenarioState.model_fields}
                values.update(body.model_dump(exclude_unset=True))
                try:
                    state = ScenarioState.model_validate(values)
                except ValidationError:
                    raise BadRequest() from None
                for name, value in state.model_dump().items():
                    setattr(row, name, value)
                ScenarioRepository(session).flush()
                result = self._get(session, scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None
