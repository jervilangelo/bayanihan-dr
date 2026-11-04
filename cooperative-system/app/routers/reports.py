from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas, services
from app.db import get_db

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/summary", response_model=schemas.ReportSummary)
def summary(db: Session = Depends(get_db)):
    """Operational totals. Also the record-level fingerprint used to validate a restored database."""
    return services.report_summary(db)
