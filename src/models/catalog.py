"""Historical catalog, deliberately independent of the prototype prediction tables."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


def _nonblank(*names: str) -> tuple[CheckConstraint, ...]:
    return tuple(
        CheckConstraint(f"{name} ~ '[^[:space:]]'", name=f"{name}_nonblank") for name in names
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("name_key", "category"),
        *_nonblank("name", "name_key", "category"),
        *(
            CheckConstraint(f"{name} BETWEEN 0 AND 100", name=f"{name}_range")
            for name in ("offense", "defense", "form", "star_power", "clutch")
        ),
        CheckConstraint("fifa_rank > 0", name="fifa_rank_positive"),
        CheckConstraint(
            "(offense IS NULL AND defense IS NULL AND form IS NULL AND star_power IS NULL "
            "AND clutch IS NULL) OR "
            "(ratings_source IS NOT NULL AND ratings_source ~ '[^[:space:]]')",
            name="ratings_attribution",
        ),
        CheckConstraint(
            "(fifa_rank IS NULL AND ranking_date IS NULL) OR "
            "(ranking_source IS NOT NULL AND ranking_source ~ '[^[:space:]]')",
            name="ranking_attribution",
        ),
    )
    team_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    offense: Mapped[float | None] = mapped_column(Double)
    defense: Mapped[float | None] = mapped_column(Double)
    form: Mapped[float | None] = mapped_column(Double)
    star_power: Mapped[float | None] = mapped_column(Double)
    clutch: Mapped[float | None] = mapped_column(Double)
    fifa_rank: Mapped[int | None]
    ratings_source: Mapped[str | None] = mapped_column(Text)
    ranking_source: Mapped[str | None] = mapped_column(Text)
    ranking_date: Mapped[date | None]


class Competition(Base):
    __tablename__ = "competitions"
    __table_args__ = (
        UniqueConstraint("name_key", "edition_label", "category"),
        *_nonblank("name", "name_key", "edition_label", "category"),
    )
    competition_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    name_key: Mapped[str] = mapped_column(String(160))
    edition_label: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(40))


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("source", "source_record_key"),
        CheckConstraint("home_team_id <> away_team_id", name="distinct_teams"),
        CheckConstraint("home_score >= 0 AND away_score >= 0", name="nonnegative_scores"),
        CheckConstraint("source_row > 0", name="source_row_positive"),
        CheckConstraint("source_record_key ~ '^[0-9a-f]{64}$'", name="record_key_sha256"),
        CheckConstraint("source_file_sha256 ~ '^[0-9a-f]{64}$'", name="file_sha256"),
        *_nonblank(
            "score_basis",
            "source",
            "source_version",
            "source_url",
            "source_home_team",
            "source_away_team",
            "source_tournament",
        ),
    )
    match_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.competition_id", ondelete="RESTRICT"), index=True
    )
    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), index=True
    )
    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), index=True
    )
    match_date: Mapped[date] = mapped_column(index=True)
    home_score: Mapped[int] = mapped_column(SmallInteger)
    away_score: Mapped[int] = mapped_column(SmallInteger)
    score_basis: Mapped[str] = mapped_column(String(64))
    neutral: Mapped[bool | None]
    city: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    source_record_key: Mapped[str] = mapped_column(String(64))
    source_version: Mapped[str] = mapped_column(Text)
    source_file_sha256: Mapped[str] = mapped_column(String(64))
    source_row: Mapped[int]
    source_url: Mapped[str] = mapped_column(Text)
    source_home_team: Mapped[str] = mapped_column(Text)
    source_away_team: Mapped[str] = mapped_column(Text)
    source_tournament: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
