import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.db import get_db

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health")
def liveness() -> dict:
    """Process is up. Does not touch the database."""
    return {"status": "ok", "service": "bfc-cms", "version": __version__}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    """Database reachable and migrated. Used by Docker, and later by the DR health checks."""
    try:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError as exc:
        log.warning("readiness check failed: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "error", "schema_revision": None},
        )
    return {"status": "ready", "database": "ok", "schema_revision": revision}
