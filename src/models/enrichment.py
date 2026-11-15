"""Append-only official observations and reproducible experimental rating cohorts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class RankingRelease(Base):
    __tablename__ = "ranking_releases"
    release_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    published_on: Mapped[date] = mapped_column(index=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))
    index_sha256: Mapped[str] = mapped_column(String(64))
    release_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RankingObservation(Base):
    __tablename__ = "ranking_observations"
    __table_args__ = (
        CheckConstraint("rank IS NULL OR rank > 0", name="rank_positive"),
        CheckConstraint(
            "points IS NULL OR (points >= 0 AND points < 'Infinity'::numeric)", name="points_finite"
        ),
    )
    release_id: Mapped[str] = mapped_column(
        ForeignKey("ranking_releases.release_id", ondelete="RESTRICT"), primary_key=True
    )
    fifa_team_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    rank: Mapped[int | None]
    points: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[int]
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)


class FifaTeamMapping(Base):
    __tablename__ = "fifa_team_mappings"
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), primary_key=True
    )
    fifa_team_id: Mapped[str] = mapped_column(String(40), unique=True)
    source_name: Mapped[str]


class RatingRun(Base):
    __tablename__ = "rating_runs"
    __table_args__ = (UniqueConstraint("cutoff", "model_version", "source_sha256"),)
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cutoff: Mapped[date] = mapped_column(index=True)
    model_version: Mapped[str]
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str]
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)


class TeamRating(Base):
    __tablename__ = "team_ratings"
    __table_args__ = tuple(
        CheckConstraint(f"{field} BETWEEN 0 AND 100", name=f"{field}_range")
        for field in ("offense", "defense", "form")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("rating_runs.run_id", ondelete="RESTRICT"), primary_key=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), primary_key=True
    )
    offense: Mapped[float | None]
    defense: Mapped[float | None]
    form: Mapped[float | None]
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
