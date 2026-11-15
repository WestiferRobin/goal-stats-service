"""Historical team reads using the caller's transaction."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, case, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from infra.resources.db import Database
from models.competition import Competition
from models.enrichment import (
    FifaTeamMapping,
    RankingObservation,
    RankingRelease,
    RatingRun,
    TeamRating,
)
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

    def list_profiles(
        self, session: Session, team_id: int | None = None
    ) -> Sequence[tuple[Team, dict[str, object]]]:
        """One SELECT and one database snapshot, including both latest cohorts."""
        release = aliased(
            RankingRelease,
            select(RankingRelease)
            .where(RankingRelease.published_on <= date.today())
            .order_by(RankingRelease.published_on.desc())
            .limit(1)
            .subquery(),
        )
        run = aliased(
            RatingRun,
            select(RatingRun)
            .where(RatingRun.cutoff <= date.today())
            .order_by(RatingRun.cutoff.desc(), RatingRun.model_version.desc(), RatingRun.run_id)
            .limit(1)
            .subquery(),
        )
        statement = (
            select(Team, FifaTeamMapping, release, RankingObservation, run, TeamRating)
            .select_from(Team)
            .outerjoin(FifaTeamMapping, FifaTeamMapping.team_id == Team.team_id)
            .outerjoin(release, true())
            .outerjoin(
                RankingObservation,
                and_(
                    RankingObservation.release_id == release.release_id,
                    RankingObservation.fifa_team_id == FifaTeamMapping.fifa_team_id,
                ),
            )
            .outerjoin(run, true())
            .outerjoin(
                TeamRating,
                and_(TeamRating.run_id == run.run_id, TeamRating.team_id == Team.team_id),
            )
            .order_by(Team.name, Team.team_id)
        )
        if team_id is not None:
            statement = statement.where(Team.team_id == team_id)
        result = []
        for team, mapping, official, observation, cohort, rating in session.execute(statement):
            values: dict[str, object] = {}
            if official and mapping:
                values.update(
                    fifa_rank=observation.rank if observation else None,
                    fifa_points=float(observation.points)
                    if observation and observation.points is not None
                    else None,
                    ranking_date=official.published_on,
                    ranking_source=official.source_url,
                    ranking_release_id=official.release_id,
                    fifa_team_id=mapping.fifa_team_id,
                    ranking_status="ranked"
                    if observation and observation.rank is not None
                    else "unranked",
                )
            if cohort and rating:
                values.update(
                    offense=rating.offense,
                    defense=rating.defense,
                    form=rating.form,
                    ratings_metadata={
                        "run_id": cohort.run_id,
                        "model": cohort.model_version,
                        "cutoff": cohort.cutoff.isoformat(),
                        "source": cohort.source_url,
                        "source_sha256": cohort.source_sha256,
                        "status": "experimental",
                        "evidence": rating.evidence,
                    },
                )
            result.append((team, values))
        return result

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
