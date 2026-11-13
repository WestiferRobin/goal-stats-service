"""Prepare optional scenario ownership without changing shared API behavior.

Downgrade refuses populated identities or ownership; it never clears either.
"""

import sqlalchemy as sa
from alembic import op

revision = "e42b7c19a603"
down_revision = "d91e6a4b208f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_users")),
    )
    op.add_column("scenarios", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_scenarios_owner_user_id_users"),
        "scenarios",
        "users",
        ["owner_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_scenarios_owner_user_id", "scenarios", ["owner_user_id", "created_at", "scenario_id"]
    )


def downgrade() -> None:
    # Held through guard, DDL and revision update to prevent check/drop races.
    op.execute("LOCK TABLE scenarios, users IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM users)
               OR EXISTS (SELECT 1 FROM scenarios WHERE owner_user_id IS NOT NULL) THEN
                RAISE EXCEPTION 'Ownership downgrade refused: users or ownership contains data.'
                    ' Preserve the data and coordinate rollback before retrying.'
                    USING ERRCODE = 'check_violation';
            END IF;
        END
        $guard$;
    """)
    op.drop_index("ix_scenarios_owner_user_id", table_name="scenarios")
    op.drop_constraint("fk_scenarios_owner_user_id_users", "scenarios", type_="foreignkey")
    op.drop_column("scenarios", "owner_user_id")
    op.drop_table("users")
