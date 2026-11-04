from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.errors import Conflict, NotFound
from app.models import Farmer, Transaction

router = APIRouter(prefix="/api/v1/farmers", tags=["farmers"])


def _get_or_404(db: Session, farmer_id: int) -> Farmer:
    farmer = db.get(Farmer, farmer_id)
    if farmer is None:
        raise NotFound(f"farmer {farmer_id} not found")
    return farmer


@router.get("", response_model=schemas.Page[schemas.FarmerRead])
def list_farmers(
    db: Session = Depends(get_db),
    q: str | None = Query(None, max_length=60, description="Search name or member code"),
    status_: schemas.FarmerStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Farmer)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(Farmer.first_name.ilike(pattern), Farmer.last_name.ilike(pattern), Farmer.member_code.ilike(pattern))
        )
    if status_:
        stmt = stmt.where(Farmer.status == status_)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Farmer.id).limit(limit).offset(offset)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", response_model=schemas.FarmerRead, status_code=status.HTTP_201_CREATED)
def create_farmer(data: schemas.FarmerCreate, db: Session = Depends(get_db)):
    farmer = Farmer(**data.model_dump())
    db.add(farmer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"member code {data.member_code} already exists") from exc
    db.refresh(farmer)
    return farmer


@router.get("/{farmer_id}", response_model=schemas.FarmerRead)
def get_farmer(farmer_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, farmer_id)


@router.patch("/{farmer_id}", response_model=schemas.FarmerRead)
def update_farmer(farmer_id: int, data: schemas.FarmerUpdate, db: Session = Depends(get_db)):
    farmer = _get_or_404(db, farmer_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(farmer, field, value)
    db.commit()
    db.refresh(farmer)
    return farmer


@router.delete("/{farmer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farmer(farmer_id: int, db: Session = Depends(get_db)):
    farmer = _get_or_404(db, farmer_id)
    if db.scalar(select(exists().where(Transaction.farmer_id == farmer_id))):
        raise Conflict("member has ledger transactions; set status to 'inactive' instead")
    db.delete(farmer)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
