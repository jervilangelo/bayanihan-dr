"""Initial schema: farmers, inventory_items, transactions.

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "farmers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_code", sa.String(12), nullable=False, unique=True),
        sa.Column("first_name", sa.String(60), nullable=False),
        sa.Column("last_name", sa.String(60), nullable=False),
        sa.Column("barangay", sa.String(80), nullable=False),
        sa.Column("municipality", sa.String(80), nullable=False),
        sa.Column("province", sa.String(80), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("farm_size_hectares", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("primary_crop", sa.String(40), nullable=False),
        sa.Column("membership_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("share_capital", sa.Numeric(12, 2), nullable=False, server_default="0"),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_farmers_status"),
        sa.CheckConstraint("farm_size_hectares >= 0", name="ck_farmers_farm_size_non_negative"),
        sa.CheckConstraint("share_capital >= 0", name="ck_farmers_share_capital_non_negative"),
    )
    op.create_index("ix_farmers_last_name", "farmers", ["last_name"])

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("reorder_level", sa.Numeric(12, 2), nullable=False, server_default="0"),
        *_timestamps(),
        sa.CheckConstraint(
            "category IN ('seed', 'fertilizer', 'pesticide', 'produce', 'equipment')",
            name="ck_inventory_category",
        ),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_quantity_non_negative"),
        sa.CheckConstraint("unit_price >= 0", name="ck_inventory_price_non_negative"),
        sa.CheckConstraint("reorder_level >= 0", name="ck_inventory_reorder_non_negative"),
    )
    op.create_index("ix_inventory_items_category", "inventory_items", ["category"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(16), unique=True),
        sa.Column("type", sa.String(12), nullable=False),
        sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("inventory_items.id", ondelete="RESTRICT")),
        sa.Column("quantity", sa.Numeric(12, 2)),
        sa.Column("unit_price", sa.Numeric(12, 2)),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('sale', 'purchase', 'contribution')", name="ck_transactions_type"),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint(
            "(type = 'contribution' AND item_id IS NULL AND quantity IS NULL AND unit_price IS NULL)"
            " OR (type <> 'contribution' AND item_id IS NOT NULL AND quantity > 0 AND unit_price >= 0)",
            name="ck_transactions_shape",
        ),
    )
    op.create_index("ix_transactions_type", "transactions", ["type"])
    op.create_index("ix_transactions_farmer_id", "transactions", ["farmer_id"])
    op.create_index("ix_transactions_item_id", "transactions", ["item_id"])
    op.create_index("ix_transactions_occurred_at", "transactions", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("inventory_items")
    op.drop_table("farmers")
