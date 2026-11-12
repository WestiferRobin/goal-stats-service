"""Add the normalized historical catalog; leave prototype records untouched."""

import sqlalchemy as sa
from alembic import op

revision = "e3a71c92b406"
down_revision = "d94f81ab2301"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_table("competitions")
    op.drop_table("teams")
