"""Historical match projections and participant lookups; no historical writes."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, aliased

from infra.resources.db import Database
from models.competition import Competition
from models.match import Match
from models.team import Team


@dataclass(frozen=True)
class MatchProjection:
    match_id: int
    match_date: date
    competition_id: int
    competition_name: str
    edition_label: str
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_score: int
    away_score: int
    score_basis: str
    neutral: bool | None
    city: str | None
    country: str | None


class MatchRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    @staticmethod
    def _projection_query() -> Select[Any]:
        home, away = aliased(Team), aliased(Team)
        return (
            select(
                Match.match_id,
                Match.match_date,
                Match.competition_id,
                Competition.name.label("competition_name"),
                Competition.edition_label,
                Match.home_team_id,
                home.name.label("home_team_name"),
                Match.away_team_id,
                away.name.label("away_team_name"),
                Match.home_score,
                Match.away_score,
                Match.score_basis,
                Match.neutral,
                Match.city,
                Match.country,
            )
            .join(Competition, Match.competition_id == Competition.competition_id)
            .join(home, Match.home_team_id == home.team_id)
            .join(away, Match.away_team_id == away.team_id)
        )

    def list(
        self,
        session: Session,
        *,
        team_id: int | None = None,
        opponent_team_id: int | None = None,
        competition_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MatchProjection]:
        statement = self._projection_query()
        if team_id is not None:
            statement = statement.where(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
            )
        if opponent_team_id is not None:
            statement = statement.where(
                or_(
                    and_(Match.home_team_id == team_id, Match.away_team_id == opponent_team_id),
                    and_(Match.away_team_id == team_id, Match.home_team_id == opponent_team_id),
                )
            )
        if competition_id is not None:
            statement = statement.where(Match.competition_id == competition_id)
        if date_from is not None:
            statement = statement.where(Match.match_date >= date_from)
        if date_to is not None:
            statement = statement.where(Match.match_date <= date_to)
        statement = statement.order_by(Match.match_date, Match.match_id).limit(limit).offset(offset)
        return [MatchProjection(**row) for row in session.execute(statement).mappings()]

    def get_projection(self, session: Session, match_id: int) -> MatchProjection | None:
        row = (
            session.execute(self._projection_query().where(Match.match_id == match_id))
            .mappings()
            .one_or_none()
        )
        return MatchProjection(**row) if row is not None else None

    def get_by_id(
        self, session: Session, match_id: int, *, for_share: bool = False
    ) -> Match | None:
        statement = select(Match).where(Match.match_id == match_id)
        if for_share:
            statement = statement.with_for_update(read=True)
        return session.scalar(statement)
