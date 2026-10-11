"""Saved scenario identities, mutable match state and immutable explicit rating snapshots."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("team1_id <> team2_id", name="distinct_teams"),
        CheckConstraint(
            "abs(team1_possession + team2_possession - 100) <= 0.01", name="possession_total"
        ),
        Index("ix_scenarios_created_at", "created_at", "scenario_id"),
        CheckConstraint("match_minute BETWEEN 0 AND 120", name="match_minute_range"),
        CheckConstraint("team1_goals BETWEEN 0 AND 1000", name="team1_goals_range"),
        CheckConstraint("team1_shots BETWEEN 0 AND 1000", name="team1_shots_range"),
        CheckConstraint(
            "team1_shots_on_target BETWEEN 0 AND 1000", name="team1_shots_on_target_range"
        ),
        CheckConstraint("team1_big_chances BETWEEN 0 AND 1000", name="team1_big_chances_range"),
        CheckConstraint(
            "team1_defender_blocks BETWEEN 0 AND 1000", name="team1_defender_blocks_range"
        ),
        CheckConstraint(
            "team1_goalkeeper_saves BETWEEN 0 AND 1000", name="team1_goalkeeper_saves_range"
        ),
        CheckConstraint("team1_corners BETWEEN 0 AND 1000", name="team1_corners_range"),
        CheckConstraint("team1_yellow_cards BETWEEN 0 AND 1000", name="team1_yellow_cards_range"),
        CheckConstraint("team1_red_cards BETWEEN 0 AND 11", name="team1_red_cards_range"),
        CheckConstraint("team1_possession BETWEEN 0 AND 100", name="team1_possession_range"),
        CheckConstraint(
            "team1_modifier_total BETWEEN -3000 AND 3000", name="team1_modifier_total_range"
        ),
        CheckConstraint("team2_goals BETWEEN 0 AND 1000", name="team2_goals_range"),
        CheckConstraint("team2_shots BETWEEN 0 AND 1000", name="team2_shots_range"),
        CheckConstraint(
            "team2_shots_on_target BETWEEN 0 AND 1000", name="team2_shots_on_target_range"
        ),
        CheckConstraint("team2_big_chances BETWEEN 0 AND 1000", name="team2_big_chances_range"),
        CheckConstraint(
            "team2_defender_blocks BETWEEN 0 AND 1000", name="team2_defender_blocks_range"
        ),
        CheckConstraint(
            "team2_goalkeeper_saves BETWEEN 0 AND 1000", name="team2_goalkeeper_saves_range"
        ),
        CheckConstraint("team2_corners BETWEEN 0 AND 1000", name="team2_corners_range"),
        CheckConstraint("team2_yellow_cards BETWEEN 0 AND 1000", name="team2_yellow_cards_range"),
        CheckConstraint("team2_red_cards BETWEEN 0 AND 11", name="team2_red_cards_range"),
        CheckConstraint("team2_possession BETWEEN 0 AND 100", name="team2_possession_range"),
        CheckConstraint(
            "team2_modifier_total BETWEEN -3000 AND 3000", name="team2_modifier_total_range"
        ),
        CheckConstraint("team1_offense BETWEEN 0 AND 100", name="team1_offense_range"),
        CheckConstraint("team1_defense BETWEEN 0 AND 100", name="team1_defense_range"),
        CheckConstraint("team1_form BETWEEN 0 AND 100", name="team1_form_range"),
        CheckConstraint("team1_star_power BETWEEN 0 AND 100", name="team1_star_power_range"),
        CheckConstraint("team1_clutch BETWEEN 0 AND 100", name="team1_clutch_range"),
        CheckConstraint("team1_fifa_rank > 0", name="team1_fifa_rank_positive"),
        CheckConstraint("team2_offense BETWEEN 0 AND 100", name="team2_offense_range"),
        CheckConstraint("team2_defense BETWEEN 0 AND 100", name="team2_defense_range"),
        CheckConstraint("team2_form BETWEEN 0 AND 100", name="team2_form_range"),
        CheckConstraint("team2_star_power BETWEEN 0 AND 100", name="team2_star_power_range"),
        CheckConstraint("team2_clutch BETWEEN 0 AND 100", name="team2_clutch_range"),
        CheckConstraint("team2_fifa_rank > 0", name="team2_fifa_rank_positive"),
    )
    scenario_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(120))
    team1_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), index=True
    )
    team2_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"), index=True
    )
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.match_id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    match_minute: Mapped[int]
    team1_goals: Mapped[int]
    team1_shots: Mapped[int]
    team1_shots_on_target: Mapped[int]
    team1_big_chances: Mapped[int]
    team1_defender_blocks: Mapped[int]
    team1_goalkeeper_saves: Mapped[int]
    team1_corners: Mapped[int]
    team1_yellow_cards: Mapped[int]
    team1_red_cards: Mapped[int]
    team1_possession: Mapped[float] = mapped_column(Double)
    team1_modifier_total: Mapped[float] = mapped_column(Double, server_default=text("0"))
    team2_goals: Mapped[int]
    team2_shots: Mapped[int]
    team2_shots_on_target: Mapped[int]
    team2_big_chances: Mapped[int]
    team2_defender_blocks: Mapped[int]
    team2_goalkeeper_saves: Mapped[int]
    team2_corners: Mapped[int]
    team2_yellow_cards: Mapped[int]
    team2_red_cards: Mapped[int]
    team2_possession: Mapped[float] = mapped_column(Double)
    team2_modifier_total: Mapped[float] = mapped_column(Double, server_default=text("0"))
    team1_offense: Mapped[float] = mapped_column(Double)
    team1_defense: Mapped[float] = mapped_column(Double)
    team1_form: Mapped[float] = mapped_column(Double)
    team1_star_power: Mapped[float] = mapped_column(Double)
    team1_clutch: Mapped[float] = mapped_column(Double)
    team1_fifa_rank: Mapped[int | None]
    team2_offense: Mapped[float] = mapped_column(Double)
    team2_defense: Mapped[float] = mapped_column(Double)
    team2_form: Mapped[float] = mapped_column(Double)
    team2_star_power: Mapped[float] = mapped_column(Double)
    team2_clutch: Mapped[float] = mapped_column(Double)
    team2_fifa_rank: Mapped[int | None]
