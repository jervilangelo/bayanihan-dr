"""HTTP API for the job runner. Local only, token-authenticated, origin-checked, allowlisted actions."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .model import JobError
from .ports import AwsPort
from .runner import JobRunner

ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


class CreateJob(BaseModel):
    type: Literal["recovery-drill", "teardown"]
    backup_id: str | None = Field(default=None, pattern=r"^\d{8}T\d{6}Z$")


class Approve(BaseModel):
    confirm_job_id: str = Field(pattern=r"^job-\d{8}T\d{6}Z-[a-f0-9]{6}$")


def create_app(runner: JobRunner, aws: AwsPort, token: str, status_reader: Callable[[], dict[str, Any] | None]) -> FastAPI:
    app = FastAPI(title="BayanihanDR job runner", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    # DNS-rebinding defence: only requests addressed to this machine by name or loopback IP.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def origin_check(request: Request, call_next):  # browsers always send Origin on cross-site writes
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "origin not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def admin(authorization: str = Header(default="")) -> str:
        scheme, _, presented = authorization.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(presented.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="administrator token required")
        return "admin"

    @app.exception_handler(JobError)
    async def job_error(_: Request, e: JobError):
        return JSONResponse({"code": e.code, "detail": str(e)}, status_code=e.status)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/session")
    def session(_: str = Depends(admin)) -> dict[str, Any]:
        return {"authenticated": True, "identity": aws.identity_arn().split("/")[-2] if "/" in aws.identity_arn() else "unknown"}

    @app.get("/api/status")
    def status(_: str = Depends(admin)) -> dict[str, Any]:
        s = status_reader()
        if s is None:
            raise HTTPException(status_code=404, detail="no backup status yet")
        return s

    @app.get("/api/recovery-points")
    def recovery_points(_: str = Depends(admin)) -> list[dict[str, Any]]:
        return aws.recovery_points()

    @app.get("/api/jobs")
    def jobs(_: str = Depends(admin)) -> list[dict[str, Any]]:
        return [j.to_dict() for j in runner.store.all()[:50]]

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str, _: str = Depends(admin)) -> dict[str, Any]:
        return runner.store.load(job_id).to_dict()

    @app.post("/api/jobs", status_code=202)
    def create(body: CreateJob, _: str = Depends(admin)) -> dict[str, Any]:
        return runner.create(body.type, body.backup_id).to_dict()

    @app.post("/api/jobs/{job_id}/approve", status_code=202)
    def approve(job_id: str, body: Approve, _: str = Depends(admin)) -> dict[str, Any]:
        return runner.approve(job_id, body.confirm_job_id).to_dict()

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str, _: str = Depends(admin)) -> dict[str, Any]:
        return runner.cancel(job_id).to_dict()

    @app.get("/api/audit")
    def audit(_: str = Depends(admin)) -> list[dict[str, Any]]:
        return list(reversed(runner.store.audit_log()))

    return app
