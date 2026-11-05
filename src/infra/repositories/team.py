"""Historical team reads using the caller's transaction."""

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from infra.resources.db import Database
from models.competition import Competition
from models.match import Match
from models.team import Team


@dataclass(frozen=True)
class TeamSummaryProjection:
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    tournament_appearances: int
    unsupported_score_basis_count: int


class TeamRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    def get_by_id(self, session: Session, team_id: int) -> Team | None:
        return session.get(Team, team_id)

    def get_participants(
        self, session: Session, team_ids: Sequence[int], *, for_key_share: bool = False
    ) -> list[Team]:
        statement = select(Team).where(Team.team_id.in_(team_ids)).order_by(Team.team_id)
        if for_key_share:
            statement = statement.with_for_update(read=True, key_share=True)
        return list(session.scalars(statement))

    def list(self, session: Session) -> list[Team]:
        return list(session.scalars(select(Team).order_by(Team.name, Team.team_id)))

    def summary(
        self,
        session: Session,
        *,
        team_id: int,
        competition_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> TeamSummaryProjection:
        """Aggregate available World Cup records without pagination or writes.

        Provisional pending Mehla's confirmation: compare recorded final scores,
        including extra time but excluding shootouts; tied scores remain draws.
        Unsupported score bases remain in the totals and are flagged for callers.
        """
        scored = case((Match.home_team_id == team_id, Match.home_score), else_=Match.away_score)
        conceded = case((Match.home_team_id == team_id, Match.away_score), else_=Match.home_score)
        goals_for = func.coalesce(func.sum(scored), 0)
        goals_against = func.coalesce(func.sum(conceded), 0)
        statement = (
            select(
                func.count(Match.match_id).label("matches_played"),
                func.coalesce(func.sum(case((scored > conceded, 1), else_=0)), 0).label("wins"),
                func.coalesce(func.sum(case((scored == conceded, 1), else_=0)), 0).label("draws"),
                func.coalesce(func.sum(case((scored < conceded, 1), else_=0)), 0).label("losses"),
                goals_for.label("goals_for"),
                goals_against.label("goals_against"),
                (goals_for - goals_against).label("goal_difference"),
                func.count(func.distinct(Match.competition_id)).label("tournament_appearances"),
                func.coalesce(
                    func.sum(
                        case((Match.score_basis != "including_extra_time_no_shootout", 1), else_=0)
                    ),
                    0,
                ).label("unsupported_score_basis_count"),
            )
            .select_from(Match)
            .join(Competition, Match.competition_id == Competition.competition_id)
            .where(
                or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
                Competition.name_key == "fifa women's world cup",
                Competition.category == "women_senior_national",
            )
        )
        if competition_id is not None:
            statement = statement.where(Match.competition_id == competition_id)
        if date_from is not None:
            statement = statement.where(Match.match_date >= date_from)
        if date_to is not None:
            statement = statement.where(Match.match_date <= date_to)
        return TeamSummaryProjection(**session.execute(statement).mappings().one())
