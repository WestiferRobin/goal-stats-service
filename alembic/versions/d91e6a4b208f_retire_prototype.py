"""Retire only empty, current-user-owned prototype tables.

Populated installations must first inventory and verify an external backup, then
coordinate archival/removal separately. This migration never deletes records or
converts incomplete snapshots. Downgrade restores empty schema, not data.
"""

import sqlalchemy as sa
from alembic import op

revision = "d91e6a4b208f"
down_revision = "c8d42f19e630"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "LOCK TABLE football_snapshots, football_history, football_teams IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""
        DO $guard$
        DECLARE t text;
        BEGIN
            FOREACH t IN ARRAY ARRAY['football_teams','football_history','football_snapshots'] LOOP
                IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE c.oid=to_regclass(t) AND n.nspname=current_schema()
                    AND c.relkind='r' AND pg_get_userbyid(c.relowner)=current_user) THEN
                    RAISE EXCEPTION 'Prototype retirement refused: unexpected table owner.';
                END IF;
            END LOOP;
            IF EXISTS (SELECT 1 FROM football_teams) OR EXISTS (SELECT 1 FROM football_history)
                OR EXISTS (SELECT 1 FROM football_snapshots) THEN
                RAISE EXCEPTION 'Prototype retirement refused: populated tables.'
                    ' Inventory, verify backups and coordinate archival before retrying.'
                    USING ERRCODE='check_violation';
            END IF;
        END
        $guard$;
    """)
    # RESTRICT is intentional: unexpected dependencies abort the entire transaction.
    op.drop_table("football_snapshots")
    op.drop_table("football_history")
    op.drop_table("football_teams")


def downgrade() -> None:
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
