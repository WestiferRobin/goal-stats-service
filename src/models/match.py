from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, _nonblank


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
