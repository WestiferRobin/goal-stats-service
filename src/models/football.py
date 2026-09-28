"""Football tables share the monolith's engine and migration history."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, Timestamped


class FootballTeam(Base):
    __tablename__ = "football_teams"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    ratings: Mapped[dict[str, Any]] = mapped_column(JSON)


class FootballHistory(Base):
    __tablename__ = "football_history"
    __table_args__ = (
        UniqueConstraint("source", "source_row"),
        CheckConstraint("team1 <> team2", name="distinct_teams"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(100))
    source_row: Mapped[int]
    team1: Mapped[str] = mapped_column(ForeignKey("football_teams.name"))
    team2: Mapped[str] = mapped_column(ForeignKey("football_teams.name"))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class FootballSnapshot(Timestamped, Base):
    __tablename__ = "football_snapshots"
    __table_args__ = (CheckConstraint("team1 <> team2", name="distinct_teams"),)
    team1: Mapped[str] = mapped_column(ForeignKey("football_teams.name"), index=True)
    team2: Mapped[str] = mapped_column(ForeignKey("football_teams.name"), index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    prediction: Mapped[dict[str, Any]] = mapped_column(JSON)
