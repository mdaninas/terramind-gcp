"""Private synthetic analysis API with bounded, content-free request telemetry."""

import asyncio
import json
import logging
import sys
from collections.abc import Awaitable, Callable
from importlib.resources import files
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from terramind import __version__
from terramind.api.service import AnalysisService, ApiSettings, Throttled, default_service
from terramind.api.views import report_page
from terramind.cloud.budget import DependencyUnavailable
from terramind.errors import InputError
from terramind.normalizer.io import load_normalized, parse_json
from terramind.reports.render import build_report, markdown
from terramind.reports.store import valid_id
from terramind.schemas.api import AnalysisRequest
from terramind.schemas.normalized import MAX_REQUEST_BYTES, ClosedModel, NormalizedPlan
from terramind.schemas.report import Report

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


def demo_plan() -> NormalizedPlan:
    return load_normalized(files("terramind.api").joinpath("assets/sample.json").read_bytes())


async def read_plan(request: Request) -> NormalizedPlan:
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Encoded bodies are not supported")
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(415, "Content-Type must be application/json")
    length = request.headers.get("content-length")
    if length is not None:
        if not length.isascii() or not length.isdigit():
            raise HTTPException(400, "Invalid Content-Length")
        if len(length) > 10 or int(length) > MAX_REQUEST_BYTES:
            raise HTTPException(413, "Request exceeds 256 KiB")
    data = bytearray()
    try:
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_REQUEST_BYTES:
                    raise HTTPException(413, "Request exceeds 256 KiB")
                data.extend(chunk)
    except TimeoutError:
        raise HTTPException(408, "Request body timed out") from None
    try:
        parse_json(bytes(data), MAX_REQUEST_BYTES)
    except InputError:
        raise HTTPException(400, "Invalid JSON object") from None
    try:
        plan = AnalysisRequest.model_validate_json(data)
    except ValidationError:
        raise HTTPException(422, "Normalized schema validation failed; see schema v1.0") from None
    return plan


def create_app(service: AnalysisService | None = None) -> FastAPI:
    # Cloud Run enforces IAM before requests reach the container. Local serving
    # is for development and does not claim to implement Google authentication.
    application = FastAPI(
        title="Terramind",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    service = service or default_service(ApiSettings.from_env())
    application.state.analysis_service = service

    @application.exception_handler(DependencyUnavailable)
    async def unavailable(request: Request, error: DependencyUnavailable) -> JSONResponse:
        return JSONResponse({"detail": "Report storage unavailable"}, status_code=503)

    @application.exception_handler(Throttled)
    async def throttled(request: Request, error: Throttled) -> JSONResponse:
        return JSONResponse(
            {"detail": "Analysis limit reached; retry later"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    @application.middleware("http")
    async def observe(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = perf_counter()
        request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            # Do not serialize exception details, request bodies or headers.
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        allowed_routes = {
            "/health",
            "/healthz",
            "/demo",
            "/assets/report.css",
            "/assets/demo.js",
            "/v1/analyses",
            "/v1/analyses/{analysis_id}",
            "/v1/analyses/{analysis_id}/markdown",
            "/v1/analyses/{analysis_id}/view",
        }
        logger.info(
            json.dumps(
                {
                    "severity": "ERROR" if response.status_code >= 500 else "INFO",
                    "event": "http_request",
                    "request_id": request_id,
                    "route": route_path if route_path in allowed_routes else "unmatched",
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

    @application.post("/v1/analyses", status_code=201)
    async def create_analysis(request: Request) -> JSONResponse:
        plan = await read_plan(request)
        report = await run_in_threadpool(service.create, plan)
        logger.info(
            json.dumps(
                {
                    "severity": "INFO",
                    "event": "analysis_complete",
                    "request_id": request.state.request_id,
                    "overall_risk": report.overall_risk,
                    "finding_count": len(report.findings),
                    "rag_status": report.rag_status,
                    "advisory_present": report.advisory is not None,
                }
            )
        )
        return JSONResponse(
            report.model_dump(mode="json"),
            status_code=201,
            headers={"Location": f"/v1/analyses/{report.analysis_id}"},
        )

    async def get_report(analysis_id: str) -> "Report":
        if not valid_id(analysis_id):
            raise HTTPException(404, "Report not found")
        report = await run_in_threadpool(service.get, analysis_id)
        if report is None:
            raise HTTPException(404, "Report not found")
        return report

    @application.get("/v1/analyses/{analysis_id}")
    async def read_analysis(analysis_id: str) -> JSONResponse:
        report = await get_report(analysis_id)
        return JSONResponse(report.model_dump(mode="json"))

    @application.get("/v1/analyses/{analysis_id}/markdown")
    async def download_markdown(analysis_id: str) -> Response:
        report = await get_report(analysis_id)
        return Response(
            markdown(report),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="terramind-{analysis_id}.md"'},
        )

    @application.get("/v1/analyses/{analysis_id}/view", response_class=HTMLResponse)
    async def read_view(analysis_id: str) -> str:
        return report_page(
            await get_report(analysis_id),
            mode=service.settings.mode,
            retention_hours=service.settings.retention_hours,
        )

    @application.get("/demo", response_class=HTMLResponse)
    async def demo() -> str:
        sample = demo_plan()
        return report_page(
            build_report(sample),
            mode=service.settings.mode,
            sample=sample,
            retention_hours=service.settings.retention_hours,
        )

    @application.get("/assets/report.css")
    async def stylesheet() -> Response:
        return Response(
            files("terramind.api").joinpath("assets/report.css").read_text(), media_type="text/css"
        )

    @application.get("/assets/demo.js")
    async def javascript() -> Response:
        return Response(
            files("terramind.api").joinpath("assets/demo.js").read_text(),
            media_type="text/javascript",
        )

    return application


app = create_app()
