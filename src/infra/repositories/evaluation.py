"""Bounded repeatable-read historical projection. Never writes or uses current ratings."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.orm import Session, aliased

from infra.resources.db import Database
from models.competition import Competition
from models.enrichment import FifaTeamMapping, RankingObservation, RankingRelease
from models.match import Match
from models.team import Team


@dataclass(frozen=True)
class HistoricalCase:
    match_id: int
    match_key: str
    day: date
    home_id: int
    away_id: int
    home: str
    away: str
    source_home: str
    source_away: str
    recorded_home: int
    recorded_away: int
    score_basis: str
    source_hash: str
    source_version: str


class EvaluationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        return self.database.transaction()

    def candidates(self, session: Session) -> list[HistoricalCase]:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        home, away = aliased(Team), aliased(Team)
        statement = (
            select(Match, home.name, away.name)
            .join(Competition, Competition.competition_id == Match.competition_id)
            .join(home, home.team_id == Match.home_team_id)
            .join(away, away.team_id == Match.away_team_id)
            .where(
                Competition.name_key == "fifa women's world cup",
                Competition.category == "women_senior_national",
                Competition.edition_label.in_([str(y) for y in range(1991, 2024, 4)]),
            )
            .order_by(Match.match_date, Match.source_record_key)
            .limit(349)
        )
        return [
            HistoricalCase(
                m.match_id,
                m.source_record_key,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                h,
                a,
                m.source_home_team,
                m.source_away_team,
                m.home_score,
                m.away_score,
                m.score_basis,
                m.source_file_sha256,
                m.source_version,
            )
            for m, h, a in session.execute(statement)
        ]

    def ranking(self, session: Session, team_id: int, day: date) -> dict[str, object]:
        release = session.scalar(
            select(RankingRelease)
            .where(RankingRelease.published_on < day)
            .order_by(RankingRelease.published_on.desc(), RankingRelease.release_id)
            .limit(1)
        )
        if release is None:
            return {"rank": None, "reason": "no_pre_match_ranking_release"}
        mapping = session.get(FifaTeamMapping, team_id)
        row = (
            session.get(RankingObservation, (release.release_id, mapping.fifa_team_id))
            if mapping
            else None
        )
        return {
            "rank": row.rank if row else None,
            "published_on": release.published_on.isoformat(),
            "release_id": release.release_id,
            "source": release.source_url,
            "source_hash": release.sha256,
            "reason": None if row and row.rank is not None else "missing_rank_in_pre_match_release",
        }
