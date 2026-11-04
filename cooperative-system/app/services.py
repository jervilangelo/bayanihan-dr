"""Business logic shared by the API and the seed script."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas
from app.errors import BusinessRuleViolation, Conflict, NotFound
from app.models import TRANSACTION_TYPES, Farmer, InventoryItem, Transaction

CENT = Decimal("0.01")


def low_stock_condition():
    """Single definition of "low stock", shared by the inventory filter and the summary report."""
    return (InventoryItem.reorder_level > 0) & (InventoryItem.quantity_on_hand <= InventoryItem.reorder_level)


def reference_for(txn_id: int) -> str:
    return f"TXN-{txn_id:07d}"


def create_transaction(db: Session, data: schemas.TransactionCreate) -> Transaction:
    """Record a ledger entry and apply its effect atomically.

    Rows are locked (SELECT ... FOR UPDATE) so concurrent sales cannot oversell stock.
    """
    farmer = db.get(Farmer, data.farmer_id, with_for_update=True)
    if farmer is None:
        raise NotFound(f"farmer {data.farmer_id} not found")

    item_id = quantity = unit_price = None
    if data.type == "contribution":
        amount = data.amount.quantize(CENT)
        farmer.share_capital += amount
    else:
        item = db.get(InventoryItem, data.item_id, with_for_update=True)
        if item is None:
            raise NotFound(f"inventory item {data.item_id} not found")
        if data.type == "sale" and farmer.status != "active":
            raise Conflict("sales are only allowed to active members")
        if data.type == "purchase" and item.category != "produce":
            raise BusinessRuleViolation("the cooperative only purchases produce from members")

        item_id, quantity = item.id, data.quantity
        unit_price = data.unit_price if data.unit_price is not None else item.unit_price
        amount = (quantity * unit_price).quantize(CENT)
        if amount <= 0:
            raise BusinessRuleViolation("transaction amount must be greater than zero")

        if data.type == "sale":
            if item.quantity_on_hand < quantity:
                raise Conflict(
                    f"insufficient stock for {item.sku}: {item.quantity_on_hand} {item.unit} available"
                )
            item.quantity_on_hand -= quantity
        else:
            item.quantity_on_hand += quantity

    txn = Transaction(
        type=data.type,
        farmer_id=farmer.id,
        item_id=item_id,
        quantity=quantity,
        unit_price=unit_price,
        amount=amount,
        notes=data.notes,
    )
    if data.occurred_at is not None:
        txn.occurred_at = data.occurred_at
    db.add(txn)
    db.flush()
    txn.reference = reference_for(txn.id)
    db.commit()
    db.refresh(txn)
    return txn


def report_summary(db: Session) -> schemas.ReportSummary:
    total, active = db.execute(
        select(func.count(), func.count().filter(Farmer.status == "active")).select_from(Farmer)
    ).one()

    items, low_stock, stock_value = db.execute(
        select(
            func.count(),
            func.count().filter(low_stock_condition()),
            func.coalesce(func.sum(InventoryItem.quantity_on_hand * InventoryItem.unit_price), 0),
        ).select_from(InventoryItem)
    ).one()

    rows = db.execute(
        select(Transaction.type, func.count(), func.sum(Transaction.amount)).group_by(Transaction.type)
    ).all()
    by_type = {t: schemas.TypeTotals(count=0, amount=Decimal("0.00")) for t in TRANSACTION_TYPES}
    for txn_type, count, amount in rows:
        by_type[txn_type] = schemas.TypeTotals(count=count, amount=amount)

    share_capital = db.scalar(select(func.coalesce(func.sum(Farmer.share_capital), 0)))

    return schemas.ReportSummary(
        generated_at=datetime.now(UTC),
        members=schemas.MemberCounts(total=total, active=active, inactive=total - active),
        inventory=schemas.InventorySummary(
            items=items, low_stock=low_stock, stock_value=Decimal(stock_value).quantize(CENT)
        ),
        transactions=schemas.TransactionSummary(count=sum(v.count for v in by_type.values()), by_type=by_type),
        total_share_capital=Decimal(share_capital).quantize(CENT),
    )

