import json
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.errors import DomainError
from app.routers import farmers, health, inventory, reports, transactions


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so logs can be shipped to CloudWatch and queried."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(get_settings().log_level)


_configure_logging()
log = logging.getLogger("bfc_cms.access")

app = FastAPI(
    title="BFC Cooperative Management System",
    version=__version__,
    description="Synthetic-data CMS for the Bicol Farmers Cooperative (BayanihanDR System A).",
)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log.info(
        "request",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
        },
    )
    return response


for module in (health, farmers, inventory, transactions, reports):
    app.include_router(module.router)
