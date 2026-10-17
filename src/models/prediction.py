"""Append-only saved outputs and effective inputs for a scenario prediction."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("model_version ~ '[^[:space:]]'", name="model_version_nonblank"),
        CheckConstraint("team1_win_probability BETWEEN 0 AND 1", name="team1_probability_range"),
        CheckConstraint("draw_probability BETWEEN 0 AND 1", name="draw_probability_range"),
        CheckConstraint("team2_win_probability BETWEEN 0 AND 1", name="team2_probability_range"),
        CheckConstraint(
            "abs(team1_win_probability + draw_probability + team2_win_probability - 1) <= 1e-9",
            name="probability_sum",
        ),
        CheckConstraint(
            "team1_expected_remaining_goals >= 0 "
            "AND team1_expected_remaining_goals < 'Infinity'::float8",
            name="team1_expected_goals_finite",
        ),
        CheckConstraint(
            "team2_expected_remaining_goals >= 0 "
            "AND team2_expected_remaining_goals < 'Infinity'::float8",
            name="team2_expected_goals_finite",
        ),
        CheckConstraint("most_likely_team1_score >= 0", name="team1_score_nonnegative"),
        CheckConstraint("most_likely_team2_score >= 0", name="team2_score_nonnegative"),
        CheckConstraint("jsonb_typeof(input_snapshot) = 'object'", name="input_snapshot_object"),
        CheckConstraint("jsonb_typeof(details) = 'object'", name="details_object"),
        Index("ix_predictions_scenario_id", "scenario_id", "generated_at", "prediction_id"),
        Index("ix_predictions_generated_at", "generated_at", "prediction_id"),
    )
    prediction_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.scenario_id", ondelete="RESTRICT")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    model_version: Mapped[str] = mapped_column(String(80))
    team1_win_probability: Mapped[float] = mapped_column(Double)
    draw_probability: Mapped[float] = mapped_column(Double)
    team2_win_probability: Mapped[float] = mapped_column(Double)
    team1_expected_remaining_goals: Mapped[float | None] = mapped_column(Double)
    team2_expected_remaining_goals: Mapped[float | None] = mapped_column(Double)
    most_likely_team1_score: Mapped[int | None] = mapped_column(SmallInteger)
    most_likely_team2_score: Mapped[int | None] = mapped_column(SmallInteger)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
