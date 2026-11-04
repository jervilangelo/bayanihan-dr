"""Ledger endpoints. Deliberately no PUT/PATCH/DELETE: entries are immutable (ADR-004)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schemas, services
from app.db import get_db
from app.errors import NotFound
from app.models import Transaction

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("", response_model=schemas.Page[schemas.TransactionRead])
def list_transactions(
    db: Session = Depends(get_db),
    farmer_id: int | None = None,
    item_id: int | None = None,
    type_: schemas.TransactionType | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Transaction)
    if farmer_id is not None:
        stmt = stmt.where(Transaction.farmer_id == farmer_id)
    if item_id is not None:
        stmt = stmt.where(Transaction.item_id == item_id)
    if type_:
        stmt = stmt.where(Transaction.type == type_)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=schemas.TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(data: schemas.TransactionCreate, db: Session = Depends(get_db)):
    return services.create_transaction(db, data)


@router.get("/{transaction_id}", response_model=schemas.TransactionRead)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise NotFound(f"transaction {transaction_id} not found")
    return txn
