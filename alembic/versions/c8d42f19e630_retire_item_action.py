"""Retire empty Item/Action tables; refuse data loss in online and offline upgrades.

Downgrade recreates the original empty schema; it cannot restore retired records.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d42f19e630"
down_revision = "a7c93e25d104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Locks remain held through the transactional guard, drops and revision update.
    op.execute("LOCK TABLE items, actions IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $guard$
        DECLARE
            has_items boolean;
            has_actions boolean;
        BEGIN
            SELECT EXISTS (SELECT 1 FROM items) INTO has_items;
            SELECT EXISTS (SELECT 1 FROM actions) INTO has_actions;
            IF has_items OR has_actions THEN
                RAISE EXCEPTION 'Item/Action retirement refused: items or actions contains records.'
                    ' Preserve the data and coordinate retirement before retrying.'
                    USING ERRCODE = 'check_violation';
            END IF;
        END
        $guard$;
    """)
    op.drop_table("actions")
    op.drop_table("items")


def downgrade() -> None:
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
