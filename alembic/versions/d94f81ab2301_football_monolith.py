"""Football domain in the shared monolith database."""

import sqlalchemy as sa
from alembic import op

revision = "d94f81ab2301"
down_revision = "b7f42e9c1a60"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("football_snapshots")
    op.drop_table("football_history")
    op.drop_table("football_teams")
