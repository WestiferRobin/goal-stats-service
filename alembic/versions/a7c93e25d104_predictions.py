"""Add append-only scenario predictions with immutable input snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7c93e25d104"
down_revision = "f6b82d14c903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("prediction_id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("team1_win_probability", sa.Double(), nullable=False),
        sa.Column("draw_probability", sa.Double(), nullable=False),
        sa.Column("team2_win_probability", sa.Double(), nullable=False),
        sa.Column("team1_expected_remaining_goals", sa.Double(), nullable=True),
        sa.Column("team2_expected_remaining_goals", sa.Double(), nullable=True),
        sa.Column("most_likely_team1_score", sa.SmallInteger(), nullable=True),
        sa.Column("most_likely_team2_score", sa.SmallInteger(), nullable=True),
        sa.Column("input_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object'", name=op.f("ck_predictions_details_object")
        ),
        sa.CheckConstraint(
            "draw_probability BETWEEN 0 AND 1", name=op.f("ck_predictions_draw_probability_range")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(input_snapshot) = 'object'",
            name=op.f("ck_predictions_input_snapshot_object"),
        ),
        sa.CheckConstraint(
            "model_version ~ '[^[:space:]]'", name=op.f("ck_predictions_model_version_nonblank")
        ),
        sa.CheckConstraint(
            "abs(team1_win_probability + draw_probability + team2_win_probability - 1) <= 1e-9",
            name=op.f("ck_predictions_probability_sum"),
        ),
        sa.CheckConstraint(
            "team1_expected_remaining_goals >= 0 "
            "AND team1_expected_remaining_goals < 'Infinity'::float8",
            name=op.f("ck_predictions_team1_expected_goals_finite"),
        ),
        sa.CheckConstraint(
            "team1_win_probability BETWEEN 0 AND 1",
            name=op.f("ck_predictions_team1_probability_range"),
        ),
        sa.CheckConstraint(
            "most_likely_team1_score >= 0", name=op.f("ck_predictions_team1_score_nonnegative")
        ),
        sa.CheckConstraint(
            "team2_expected_remaining_goals >= 0 "
            "AND team2_expected_remaining_goals < 'Infinity'::float8",
            name=op.f("ck_predictions_team2_expected_goals_finite"),
        ),
        sa.CheckConstraint(
            "team2_win_probability BETWEEN 0 AND 1",
            name=op.f("ck_predictions_team2_probability_range"),
        ),
        sa.CheckConstraint(
            "most_likely_team2_score >= 0", name=op.f("ck_predictions_team2_score_nonnegative")
        ),
        sa.PrimaryKeyConstraint("prediction_id", name=op.f("pk_predictions")),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
            name=op.f("fk_predictions_scenario_id_scenarios"),
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_predictions_scenario_id",
        "predictions",
        ["scenario_id", "generated_at", "prediction_id"],
    )
    op.create_index("ix_predictions_generated_at", "predictions", ["generated_at", "prediction_id"])


def downgrade() -> None:
    op.drop_table("predictions")
