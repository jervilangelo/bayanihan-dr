from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.errors import Conflict, NotFound
from app.models import InventoryItem, Transaction
from app.services import low_stock_condition

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


def _get_or_404(db: Session, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise NotFound(f"inventory item {item_id} not found")
    return item


@router.get("", response_model=schemas.Page[schemas.InventoryRead])
def list_items(
    db: Session = Depends(get_db),
    category: schemas.ItemCategory | None = None,
    low_stock: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(InventoryItem)
    if category:
        stmt = stmt.where(InventoryItem.category == category)
    if low_stock:
        stmt = stmt.where(low_stock_condition())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(InventoryItem.id).limit(limit).offset(offset)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=schemas.InventoryRead, status_code=status.HTTP_201_CREATED)
def create_item(data: schemas.InventoryCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"SKU {data.sku} already exists") from exc
    db.refresh(item)
    return item


@router.get("/{item_id}", response_model=schemas.InventoryRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, item_id)


@router.patch("/{item_id}", response_model=schemas.InventoryRead)
def update_item(item_id: int, data: schemas.InventoryUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(db, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = _get_or_404(db, item_id)
    if db.scalar(select(exists().where(Transaction.item_id == item_id))):
        raise Conflict("item is referenced by ledger transactions and cannot be deleted")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
