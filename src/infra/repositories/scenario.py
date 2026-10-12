"""Scenario persistence and the shared scenario/team projection."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.orm import Session, aliased

from models.scenario import Scenario
from models.team import Team


@dataclass(frozen=True)
class ScenarioProjection:
    """Loaded scenario and names; callers capture inputs before leaving their transaction."""

    scenario: Scenario
    team1_name: str
    team2_name: str


class ScenarioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, scenario: Scenario) -> None:
        self.session.add(scenario)
        self.session.flush()

    def flush(self) -> None:
        """Persist caller-validated changes on tracked scenarios without committing."""
        self.session.flush()

    def get_by_id(self, scenario_id: int, *, for_update: bool = False) -> Scenario | None:
        statement = select(Scenario).where(Scenario.scenario_id == scenario_id)
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def exists(self, scenario_id: int) -> bool:
        return bool(
            self.session.scalar(select(exists().where(Scenario.scenario_id == scenario_id)))
        )

    @staticmethod
    def _projection_query() -> Select[Any]:
        first, second = aliased(Team), aliased(Team)
        return (
            select(Scenario, first.name.label("team1_name"), second.name.label("team2_name"))
            .join(first, Scenario.team1_id == first.team_id)
            .join(second, Scenario.team2_id == second.team_id)
        )

    def get_projection(self, scenario_id: int) -> ScenarioProjection | None:
        row = self.session.execute(
            self._projection_query().where(Scenario.scenario_id == scenario_id)
        ).one_or_none()
        return ScenarioProjection(*row) if row is not None else None

    def list(
        self, *, team_id: int | None = None, limit: int = 50, offset: int = 0
    ) -> list[ScenarioProjection]:
        statement = self._projection_query()
        if team_id is not None:
            statement = statement.where(
                or_(Scenario.team1_id == team_id, Scenario.team2_id == team_id)
            )
        statement = (
            statement.order_by(Scenario.created_at.desc(), Scenario.scenario_id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [ScenarioProjection(*row) for row in self.session.execute(statement)]
