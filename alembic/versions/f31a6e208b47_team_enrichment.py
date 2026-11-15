"""Add isolated team enrichment; preserve all existing catalog and prediction rows."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f31a6e208b47"
down_revision = "e42b7c19a603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_releases",
        sa.Column("release_id", sa.String(100), primary_key=True),
        sa.Column("published_on", sa.Date(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("index_sha256", sa.String(64), nullable=False),
        sa.Column("release_metadata", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_ranking_releases_published_on", "ranking_releases", ["published_on"])
    op.create_table(
        "ranking_observations",
        sa.Column(
            "release_id",
            sa.String(100),
            sa.ForeignKey("ranking_releases.release_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("fifa_team_id", sa.String(40), primary_key=True),
        sa.Column("rank", sa.Integer()),
        sa.Column("points", sa.Numeric()),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("rank IS NULL OR rank > 0", name="rank_positive"),
        sa.CheckConstraint(
            "points IS NULL OR (points >= 0 AND points < 'Infinity'::numeric)", name="points_finite"
        ),
    )
    op.create_table(
        "fifa_team_mappings",
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("fifa_team_id", sa.String(40), nullable=False, unique=True),
        sa.Column("source_name", sa.String(), nullable=False),
    )
    op.create_table(
        "rating_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("cutoff", sa.Date(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("cutoff", "model_version", "source_sha256"),
    )
    op.create_index("ix_rating_runs_cutoff", "rating_runs", ["cutoff"])
    op.create_table(
        "team_ratings",
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("rating_runs.run_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "team_id",
            sa.Integer(),
            sa.ForeignKey("teams.team_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("offense", sa.Float()),
        sa.Column("defense", sa.Float()),
        sa.Column("form", sa.Float()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        *(
            sa.CheckConstraint(f"{field} BETWEEN 0 AND 100", name=f"{field}_range")
            for field in ("offense", "defense", "form")
        ),
    )


def downgrade() -> None:
    tables = (
        "team_ratings",
        "rating_runs",
        "fifa_team_mappings",
        "ranking_observations",
        "ranking_releases",
    )
    op.execute("LOCK TABLE " + ", ".join(tables) + " IN ACCESS EXCLUSIVE MODE")
    for table in tables:
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table}) THEN "
            "RAISE EXCEPTION 'Enrichment downgrade refused: preserve populated tables'; "
            "END IF; END $$;"
        )
    for table in tables:
        op.drop_table(table)
