"""PostgreSQL scenario operations using the application's existing unit of work."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from werkzeug.exceptions import BadRequest, Conflict, NotFound

from infra.resources.db import Database
from models.catalog import Match, Team
from models.scenario import Scenario
from schemas.scenarios import (
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
    def _query() -> Select[Any]:
        first, second = aliased(Team), aliased(Team)
        return (
            select(
                *Scenario.__table__.c,
                first.name.label("team1_name"),
                second.name.label("team2_name"),
            )
            .join(first, Scenario.team1_id == first.team_id)
            .join(second, Scenario.team2_id == second.team_id)
        )

    def _get(self, session: Session, scenario_id: int) -> dict[str, Any]:
        row = (
            session.execute(self._query().where(Scenario.scenario_id == scenario_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFound()
        return ScenarioResponse.model_validate(row).model_dump(mode="json")

    def create(self, body: ScenarioCreate) -> dict[str, Any]:
        try:
            with self.database.transaction() as session:
                # Hold key-share locks until commit so references cannot disappear after validation.
                teams = list(
                    session.scalars(
                        select(Team)
                        .where(Team.team_id.in_([body.team1_id, body.team2_id]))
                        .order_by(Team.team_id)
                        .with_for_update(read=True, key_share=True)
                    )
                )
                if len(teams) != 2:
                    raise NotFound()
                if body.match_id is not None:
                    match = session.scalar(
                        select(Match)
                        .where(Match.match_id == body.match_id)
                        .with_for_update(read=True)
                    )
                    if match is None:
                        raise NotFound()
                    if {match.home_team_id, match.away_team_id} != {body.team1_id, body.team2_id}:
                        raise BadRequest()
                # Explicit caller snapshots only. No lookup/copy of prototype or catalog ratings.
                row = Scenario(**body.model_dump())
                session.add(row)
                session.flush()
                result = self._get(session, row.scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None

    def get(self, scenario_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            return self._get(session, scenario_id)

    def list(self, query: ScenarioQuery) -> list[dict[str, Any]]:
        statement = self._query()
        if query.team_id is not None:
            statement = statement.where(
                or_(Scenario.team1_id == query.team_id, Scenario.team2_id == query.team_id)
            )
        statement = (
            statement.order_by(Scenario.created_at.desc(), Scenario.scenario_id.desc())
            .limit(query.limit)
            .offset(query.offset)
        )
        with self.database.transaction() as session:
            return [
                ScenarioResponse.model_validate(row).model_dump(mode="json")
                for row in session.execute(statement).mappings()
            ]

    def update(self, scenario_id: int, body: ScenarioPatch) -> dict[str, Any]:
        try:
            with self.database.transaction() as session:
                row = session.scalar(
                    select(Scenario).where(Scenario.scenario_id == scenario_id).with_for_update()
                )
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
                session.flush()
                result = self._get(session, scenario_id)
            return result
        except IntegrityError:
            raise Conflict() from None
