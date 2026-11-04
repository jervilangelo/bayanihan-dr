"""SQLAlchemy ORM models for the cooperative's core records.

Money and quantities use NUMERIC (never float) so restored totals can be compared exactly
during disaster-recovery validation.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(12, 2)
QUANTITY = Numeric(12, 2)

FARMER_STATUSES = ("active", "inactive")
ITEM_CATEGORIES = ("seed", "fertilizer", "pesticide", "produce", "equipment")
TRANSACTION_TYPES = ("sale", "purchase", "contribution")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Farmer(TimestampMixin, Base):
    """A cooperative member. ``share_capital`` is derived from contribution transactions only."""

    __tablename__ = "farmers"
    __table_args__ = (
        CheckConstraint(_in("status", FARMER_STATUSES), name="ck_farmers_status"),
        CheckConstraint("farm_size_hectares >= 0", name="ck_farmers_farm_size_non_negative"),
        CheckConstraint("share_capital >= 0", name="ck_farmers_share_capital_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(60), nullable=False)
    last_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    barangay: Mapped[str] = mapped_column(String(80), nullable=False)
    municipality: Mapped[str] = mapped_column(String(80), nullable=False)
    province: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    farm_size_hectares: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    primary_crop: Mapped[str] = mapped_column(String(40), nullable=False)
    membership_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    share_capital: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint(_in("category", ITEM_CATEGORIES), name="ck_inventory_category"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_quantity_non_negative"),
        CheckConstraint("unit_price >= 0", name="ck_inventory_price_non_negative"),
        CheckConstraint("reorder_level >= 0", name="ck_inventory_reorder_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("0"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    reorder_level: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("0"))


class Transaction(Base):
    """Immutable ledger entry (see ADR-004)."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(_in("type", TRANSACTION_TYPES), name="ck_transactions_type"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "(type = 'contribution' AND item_id IS NULL AND quantity IS NULL AND unit_price IS NULL)"
            " OR (type <> 'contribution' AND item_id IS NOT NULL AND quantity > 0 AND unit_price >= 0)",
            name="ck_transactions_shape",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str | None] = mapped_column(String(16), unique=True)
    type: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("farmers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    unit_price: Mapped[Decimal | None] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    farmer: Mapped[Farmer] = relationship()
    item: Mapped[InventoryItem | None] = relationship()
