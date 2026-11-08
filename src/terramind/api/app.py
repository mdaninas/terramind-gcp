"""Liveness service with bounded, content-free request telemetry."""

import json
import logging
import sys
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from terramind import __version__
from terramind.schemas.normalized import ClosedModel

logger = logging.getLogger("terramind.api")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class Health(ClosedModel):
    status: str = "ok"
    service: str = "terramind"
    version: str = __version__


def create_app() -> FastAPI:
    # Cloud Run enforces IAM before requests reach the container. Local serving
    # is for development and does not claim to implement Google authentication.
    application = FastAPI(
        title="Terramind",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @application.middleware("http")
    async def observe(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = perf_counter()
        request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            # Do not serialize exception details, request bodies or headers.
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "severity": "ERROR" if response.status_code >= 500 else "INFO",
                    "event": "http_request",
                    "request_id": request_id,
                    "route": request.url.path
                    if request.url.path in {"/health", "/healthz"}
                    else "unmatched",
                    "method": request.method
                    if request.method in {"GET", "HEAD", "POST"}
                    else "OTHER",
                    "status": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                }
            )
        )
        return response

    # Keep the PRD probe path inside the container. Cloud Run reserves some
    # external paths ending in z, so expose an IAM-protected compatible alias.
    @application.get("/health", response_model=Health)
    @application.get("/healthz", response_model=Health)
    async def healthz() -> Health:
        return Health()

    return application


app = create_app()
