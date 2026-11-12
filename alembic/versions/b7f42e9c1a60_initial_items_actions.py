"""initial items actions

Revision ID: b7f42e9c1a60
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f42e9c1a60"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def downgrade() -> None:
    op.drop_index(op.f("ix_actions_item_id"), table_name="actions")
    op.drop_table("actions")
    op.drop_table("items")
