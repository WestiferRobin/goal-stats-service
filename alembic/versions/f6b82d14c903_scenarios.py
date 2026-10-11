"""Add scenarios without changing catalog or prototype data."""

import sqlalchemy as sa
from alembic import op

revision = "f6b82d14c903"
down_revision = "e3a71c92b406"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("scenario_id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("team1_id", sa.Integer(), nullable=False),
        sa.Column("team2_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("match_minute", sa.Integer(), nullable=False),
        sa.Column("team1_goals", sa.Integer(), nullable=False),
        sa.Column("team1_shots", sa.Integer(), nullable=False),
        sa.Column("team1_shots_on_target", sa.Integer(), nullable=False),
        sa.Column("team1_big_chances", sa.Integer(), nullable=False),
        sa.Column("team1_defender_blocks", sa.Integer(), nullable=False),
        sa.Column("team1_goalkeeper_saves", sa.Integer(), nullable=False),
        sa.Column("team1_corners", sa.Integer(), nullable=False),
        sa.Column("team1_yellow_cards", sa.Integer(), nullable=False),
        sa.Column("team1_red_cards", sa.Integer(), nullable=False),
        sa.Column("team1_possession", sa.Double(), nullable=False),
        sa.Column("team1_modifier_total", sa.Double(), nullable=False, server_default=sa.text("0")),
        sa.Column("team2_goals", sa.Integer(), nullable=False),
        sa.Column("team2_shots", sa.Integer(), nullable=False),
        sa.Column("team2_shots_on_target", sa.Integer(), nullable=False),
        sa.Column("team2_big_chances", sa.Integer(), nullable=False),
        sa.Column("team2_defender_blocks", sa.Integer(), nullable=False),
        sa.Column("team2_goalkeeper_saves", sa.Integer(), nullable=False),
        sa.Column("team2_corners", sa.Integer(), nullable=False),
        sa.Column("team2_yellow_cards", sa.Integer(), nullable=False),
        sa.Column("team2_red_cards", sa.Integer(), nullable=False),
        sa.Column("team2_possession", sa.Double(), nullable=False),
        sa.Column("team2_modifier_total", sa.Double(), nullable=False, server_default=sa.text("0")),
        sa.Column("team1_offense", sa.Double(), nullable=False),
        sa.Column("team1_defense", sa.Double(), nullable=False),
        sa.Column("team1_form", sa.Double(), nullable=False),
        sa.Column("team1_star_power", sa.Double(), nullable=False),
        sa.Column("team1_clutch", sa.Double(), nullable=False),
        sa.Column("team1_fifa_rank", sa.Integer(), nullable=True),
        sa.Column("team2_offense", sa.Double(), nullable=False),
        sa.Column("team2_defense", sa.Double(), nullable=False),
        sa.Column("team2_form", sa.Double(), nullable=False),
        sa.Column("team2_star_power", sa.Double(), nullable=False),
        sa.Column("team2_clutch", sa.Double(), nullable=False),
        sa.Column("team2_fifa_rank", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "match_minute BETWEEN 0 AND 120", name=op.f("ck_scenarios_match_minute_range")
        ),
        sa.CheckConstraint(
            "team1_goals BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team1_goals_range")
        ),
        sa.CheckConstraint(
            "team1_shots BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team1_shots_range")
        ),
        sa.CheckConstraint(
            "team1_shots_on_target BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team1_shots_on_target_range"),
        ),
        sa.CheckConstraint(
            "team1_big_chances BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team1_big_chances_range"),
        ),
        sa.CheckConstraint(
            "team1_defender_blocks BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team1_defender_blocks_range"),
        ),
        sa.CheckConstraint(
            "team1_goalkeeper_saves BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team1_goalkeeper_saves_range"),
        ),
        sa.CheckConstraint(
            "team1_corners BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team1_corners_range")
        ),
        sa.CheckConstraint(
            "team1_yellow_cards BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team1_yellow_cards_range"),
        ),
        sa.CheckConstraint(
            "team1_red_cards BETWEEN 0 AND 11", name=op.f("ck_scenarios_team1_red_cards_range")
        ),
        sa.CheckConstraint(
            "team1_possession BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_possession_range")
        ),
        sa.CheckConstraint(
            "team1_modifier_total BETWEEN -3000 AND 3000",
            name=op.f("ck_scenarios_team1_modifier_total_range"),
        ),
        sa.CheckConstraint(
            "team2_goals BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team2_goals_range")
        ),
        sa.CheckConstraint(
            "team2_shots BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team2_shots_range")
        ),
        sa.CheckConstraint(
            "team2_shots_on_target BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team2_shots_on_target_range"),
        ),
        sa.CheckConstraint(
            "team2_big_chances BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team2_big_chances_range"),
        ),
        sa.CheckConstraint(
            "team2_defender_blocks BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team2_defender_blocks_range"),
        ),
        sa.CheckConstraint(
            "team2_goalkeeper_saves BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team2_goalkeeper_saves_range"),
        ),
        sa.CheckConstraint(
            "team2_corners BETWEEN 0 AND 1000", name=op.f("ck_scenarios_team2_corners_range")
        ),
        sa.CheckConstraint(
            "team2_yellow_cards BETWEEN 0 AND 1000",
            name=op.f("ck_scenarios_team2_yellow_cards_range"),
        ),
        sa.CheckConstraint(
            "team2_red_cards BETWEEN 0 AND 11", name=op.f("ck_scenarios_team2_red_cards_range")
        ),
        sa.CheckConstraint(
            "team2_possession BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_possession_range")
        ),
        sa.CheckConstraint(
            "team2_modifier_total BETWEEN -3000 AND 3000",
            name=op.f("ck_scenarios_team2_modifier_total_range"),
        ),
        sa.CheckConstraint(
            "team1_offense BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_offense_range")
        ),
        sa.CheckConstraint(
            "team1_defense BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_defense_range")
        ),
        sa.CheckConstraint(
            "team1_form BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_form_range")
        ),
        sa.CheckConstraint(
            "team1_star_power BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_star_power_range")
        ),
        sa.CheckConstraint(
            "team1_clutch BETWEEN 0 AND 100", name=op.f("ck_scenarios_team1_clutch_range")
        ),
        sa.CheckConstraint(
            "team1_fifa_rank > 0", name=op.f("ck_scenarios_team1_fifa_rank_positive")
        ),
        sa.CheckConstraint(
            "team2_offense BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_offense_range")
        ),
        sa.CheckConstraint(
            "team2_defense BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_defense_range")
        ),
        sa.CheckConstraint(
            "team2_form BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_form_range")
        ),
        sa.CheckConstraint(
            "team2_star_power BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_star_power_range")
        ),
        sa.CheckConstraint(
            "team2_clutch BETWEEN 0 AND 100", name=op.f("ck_scenarios_team2_clutch_range")
        ),
        sa.CheckConstraint(
            "team2_fifa_rank > 0", name=op.f("ck_scenarios_team2_fifa_rank_positive")
        ),
        sa.CheckConstraint("team1_id <> team2_id", name=op.f("ck_scenarios_distinct_teams")),
        sa.CheckConstraint(
            "abs(team1_possession + team2_possession - 100) <= 0.01",
            name=op.f("ck_scenarios_possession_total"),
        ),
        sa.PrimaryKeyConstraint("scenario_id", name=op.f("pk_scenarios")),
        sa.ForeignKeyConstraint(
            ["team1_id"],
            ["teams.team_id"],
            name=op.f("fk_scenarios_team1_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team2_id"],
            ["teams.team_id"],
            name=op.f("fk_scenarios_team2_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.match_id"],
            name=op.f("fk_scenarios_match_id_matches"),
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_scenarios_team1_id", "scenarios", ["team1_id"])
    op.create_index("ix_scenarios_team2_id", "scenarios", ["team2_id"])
    op.create_index("ix_scenarios_match_id", "scenarios", ["match_id"])
    op.create_index("ix_scenarios_created_at", "scenarios", ["created_at", "scenario_id"])


def downgrade() -> None:
    op.drop_table("scenarios")
