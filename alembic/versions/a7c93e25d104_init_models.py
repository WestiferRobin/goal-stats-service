"""Initialize all application models.

The former five-revision chain is consolidated here. Retaining its head ID lets
fully migrated databases continue without schema changes or restamping. Databases
at older intermediate revisions must finish the original chain before switching.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7c93e25d104"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active", "archived", name="item_status", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name=op.f("ck_items_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
    )
    op.create_table(
        "actions",
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum(
                "create",
                "update",
                "delete",
                name="action_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name=op.f("ck_actions_name_not_blank")),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name=op.f("fk_actions_item_id_items"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actions")),
    )
    op.create_index(op.f("ix_actions_item_id"), "actions", ["item_id"], unique=False)
    op.create_table(
        "football_teams",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("ratings", sa.JSON(), nullable=False),
    )
    op.create_table(
        "football_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("team1", sa.String(100), sa.ForeignKey("football_teams.name"), nullable=False),
        sa.Column("team2", sa.String(100), sa.ForeignKey("football_teams.name"), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("source", "source_row"),
        sa.CheckConstraint("team1 <> team2", name="distinct_teams"),
    )
    op.create_table(
        "football_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("team1", sa.String(100), sa.ForeignKey("football_teams.name"), nullable=False),
        sa.Column("team2", sa.String(100), sa.ForeignKey("football_teams.name"), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("prediction", sa.JSON(), nullable=False),
        sa.CheckConstraint("team1 <> team2", name="distinct_teams"),
    )
    op.create_index("ix_football_snapshots_team1", "football_snapshots", ["team1"])
    op.create_index("ix_football_snapshots_team2", "football_snapshots", ["team2"])
    op.create_table(
        "teams",
        sa.Column("team_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_key", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("offense", sa.Double(), nullable=True),
        sa.Column("defense", sa.Double(), nullable=True),
        sa.Column("form", sa.Double(), nullable=True),
        sa.Column("star_power", sa.Double(), nullable=True),
        sa.Column("clutch", sa.Double(), nullable=True),
        sa.Column("fifa_rank", sa.Integer(), nullable=True),
        sa.Column("ratings_source", sa.Text(), nullable=True),
        sa.Column("ranking_source", sa.Text(), nullable=True),
        sa.Column("ranking_date", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "(fifa_rank IS NULL AND ranking_date IS NULL) OR "
            "(ranking_source IS NOT NULL AND ranking_source ~ '[^[:space:]]')",
            name=op.f("ck_teams_ranking_attribution"),
        ),
        sa.CheckConstraint(
            "(offense IS NULL AND defense IS NULL AND form IS NULL "
            "AND star_power IS NULL AND clutch IS NULL) OR "
            "(ratings_source IS NOT NULL AND ratings_source ~ '[^[:space:]]')",
            name=op.f("ck_teams_ratings_attribution"),
        ),
        sa.CheckConstraint("category ~ '[^[:space:]]'", name=op.f("ck_teams_category_nonblank")),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name=op.f("ck_teams_name_nonblank")),
        sa.CheckConstraint("name_key ~ '[^[:space:]]'", name=op.f("ck_teams_name_key_nonblank")),
        sa.CheckConstraint("clutch BETWEEN 0 AND 100", name=op.f("ck_teams_clutch_range")),
        sa.CheckConstraint("defense BETWEEN 0 AND 100", name=op.f("ck_teams_defense_range")),
        sa.CheckConstraint("fifa_rank > 0", name=op.f("ck_teams_fifa_rank_positive")),
        sa.CheckConstraint("form BETWEEN 0 AND 100", name=op.f("ck_teams_form_range")),
        sa.CheckConstraint("offense BETWEEN 0 AND 100", name=op.f("ck_teams_offense_range")),
        sa.CheckConstraint("star_power BETWEEN 0 AND 100", name=op.f("ck_teams_star_power_range")),
        sa.PrimaryKeyConstraint("team_id", name=op.f("pk_teams")),
        sa.UniqueConstraint("name_key", "category", name=op.f("uq_teams_name_key")),
    )
    op.create_table(
        "competitions",
        sa.Column("competition_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("name_key", sa.String(length=160), nullable=False),
        sa.Column("edition_label", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "category ~ '[^[:space:]]'", name=op.f("ck_competitions_category_nonblank")
        ),
        sa.CheckConstraint(
            "edition_label ~ '[^[:space:]]'", name=op.f("ck_competitions_edition_label_nonblank")
        ),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name=op.f("ck_competitions_name_nonblank")),
        sa.CheckConstraint(
            "name_key ~ '[^[:space:]]'", name=op.f("ck_competitions_name_key_nonblank")
        ),
        sa.PrimaryKeyConstraint("competition_id", name=op.f("pk_competitions")),
        sa.UniqueConstraint(
            "name_key", "edition_label", "category", name=op.f("uq_competitions_name_key")
        ),
    )
    op.create_table(
        "matches",
        sa.Column("match_id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("home_score", sa.SmallInteger(), nullable=False),
        sa.Column("away_score", sa.SmallInteger(), nullable=False),
        sa.Column("score_basis", sa.String(length=64), nullable=False),
        sa.Column("neutral", sa.Boolean(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_record_key", sa.String(length=64), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("source_file_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_home_team", sa.Text(), nullable=False),
        sa.Column("source_away_team", sa.Text(), nullable=False),
        sa.Column("source_tournament", sa.Text(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "score_basis ~ '[^[:space:]]'", name=op.f("ck_matches_score_basis_nonblank")
        ),
        sa.CheckConstraint("source ~ '[^[:space:]]'", name=op.f("ck_matches_source_nonblank")),
        sa.CheckConstraint(
            "source_away_team ~ '[^[:space:]]'", name=op.f("ck_matches_source_away_team_nonblank")
        ),
        sa.CheckConstraint(
            "source_file_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_matches_file_sha256")
        ),
        sa.CheckConstraint(
            "source_home_team ~ '[^[:space:]]'", name=op.f("ck_matches_source_home_team_nonblank")
        ),
        sa.CheckConstraint(
            "source_record_key ~ '^[0-9a-f]{64}$'", name=op.f("ck_matches_record_key_sha256")
        ),
        sa.CheckConstraint(
            "source_tournament ~ '[^[:space:]]'", name=op.f("ck_matches_source_tournament_nonblank")
        ),
        sa.CheckConstraint(
            "source_url ~ '[^[:space:]]'", name=op.f("ck_matches_source_url_nonblank")
        ),
        sa.CheckConstraint(
            "source_version ~ '[^[:space:]]'", name=op.f("ck_matches_source_version_nonblank")
        ),
        sa.CheckConstraint(
            "home_score >= 0 AND away_score >= 0", name=op.f("ck_matches_nonnegative_scores")
        ),
        sa.CheckConstraint("home_team_id <> away_team_id", name=op.f("ck_matches_distinct_teams")),
        sa.CheckConstraint("source_row > 0", name=op.f("ck_matches_source_row_positive")),
        sa.ForeignKeyConstraint(
            ["away_team_id"],
            ["teams.team_id"],
            name=op.f("fk_matches_away_team_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.competition_id"],
            name=op.f("fk_matches_competition_id_competitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["home_team_id"],
            ["teams.team_id"],
            name=op.f("fk_matches_home_team_id_teams"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("match_id", name=op.f("pk_matches")),
        sa.UniqueConstraint("source", "source_record_key", name=op.f("uq_matches_source")),
    )
    op.create_index(op.f("ix_matches_away_team_id"), "matches", ["away_team_id"], unique=False)
    op.create_index(op.f("ix_matches_competition_id"), "matches", ["competition_id"], unique=False)
    op.create_index(op.f("ix_matches_home_team_id"), "matches", ["home_team_id"], unique=False)
    op.create_index(op.f("ix_matches_match_date"), "matches", ["match_date"], unique=False)
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
    op.drop_table("scenarios")
    op.drop_table("matches")
    op.drop_table("competitions")
    op.drop_table("teams")
    op.drop_table("football_snapshots")
    op.drop_table("football_history")
    op.drop_table("football_teams")
    op.drop_index(op.f("ix_actions_item_id"), table_name="actions")
    op.drop_table("actions")
    op.drop_table("items")
