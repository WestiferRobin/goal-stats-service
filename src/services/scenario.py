"""PostgreSQL scenario operations using the application's existing unit of work."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from infra.repositories.scenario import ScenarioProjection, ScenarioRepository
from infra.resources.db import Database
from models.scenario import Scenario
from schemas.scenario import (
    ScenarioCreate,
    ScenarioPatch,
    ScenarioQuery,
    ScenarioResponse,
    ScenarioState,
)
from services.match import MatchService
from services.team import TeamService


class ScenarioService:
    def __init__(
        self, *, repo: ScenarioRepository, team_service: TeamService, match_service: MatchService
    ) -> None:
        if (
            repo.database is not team_service.database
            or repo.database is not match_service.database
        ):
            raise ValueError("Repositories must share the same Database instance")
        self.repo = repo
        self.team_service = team_service
        self.match_service = match_service

    @property
    def database(self) -> Database:
        """Application resource identity; no operation session is retained."""
        return self.repo.database

    @staticmethod
    def _response(row: ScenarioProjection) -> dict[str, Any]:
        values = {
            column.name: getattr(row.scenario, column.name) for column in Scenario.__table__.columns
        }
        values.update(team1_name=row.team1_name, team2_name=row.team2_name)
        return ScenarioResponse.model_validate(values).model_dump(mode="json")

    def _get(self, session: Session, scenario_id: int) -> dict[str, Any]:
        row = self.repo.get_projection(session, scenario_id)
        if row is None:
            raise NotFound()
        return self._response(row)

    def create(self, body: ScenarioCreate) -> dict[str, Any]:
        try:
            with self.repo.transaction() as session:
                participants = (body.team1_id, body.team2_id)
                self.team_service.require_participants_in_transaction(
                    session=session, team_ids=participants
                )
                if body.match_id is not None:
                    self.match_service.require_match_participants_in_transaction(
                        session=session, match_id=body.match_id, team_ids=participants
                    )
                # Explicit caller snapshots only. No lookup/copy of prototype or catalog ratings.
                row = Scenario(**body.model_dump())
                self.repo.add(session, row)
                result = self._get(session, row.scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None

    def get(self, scenario_id: int) -> dict[str, Any]:
        with self.repo.transaction() as session:
            return self._get(session, scenario_id)

    def list(self, query: ScenarioQuery) -> list[dict[str, Any]]:
        with self.repo.transaction() as session:
            return [self._response(row) for row in self.repo.list(session, **query.model_dump())]

    def update(self, scenario_id: int, body: ScenarioPatch) -> dict[str, Any]:
        try:
            with self.repo.transaction() as session:
                row = self.repo.get_by_id(session, scenario_id, for_update=True)
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
                self.repo.flush(session)
                result = self._get(session, scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None

    def capture_state_in_transaction(
        self, *, session: Session, scenario_id: int
    ) -> Mapping[str, Any]:
        """Copy authoritative scalar state without validating prediction readiness."""
        row = self.repo.get_projection(session, scenario_id)
        if row is None:
            raise NotFound()
        values = {
            column.name: getattr(row.scenario, column.name) for column in Scenario.__table__.columns
        }
        values.update(team1_name=row.team1_name, team2_name=row.team2_name)
        return MappingProxyType(values)

    def require_exists_in_transaction(self, *, session: Session, scenario_id: int) -> None:
        """Check existence in the caller's transaction without returning ORM state."""
        if not self.repo.exists(session, scenario_id):
            raise NotFound()
