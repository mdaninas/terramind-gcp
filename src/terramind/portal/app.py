"""Single-host portal: authenticated ownership, CSRF-protected actions and synthetic inputs."""

import asyncio
import secrets
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from html import escape
from importlib.resources import files
from urllib.parse import parse_qsl, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from terramind.api.app import demo_plan
from terramind.api.service import AdmissionGate, Throttled, cloud_analysis
from terramind.cloud.budget import DependencyUnavailable
from terramind.cloud.settings import CloudSettings
from terramind.events.service import packaged_corpus
from terramind.incidents.search import IncidentSearcher
from terramind.portal import views
from terramind.portal.oidc import GoogleOIDC, IdentityProvider
from terramind.portal.settings import PortalSettings
from terramind.portal.store import HistoryFilters, PortalAnalysis, PortalStore, Session, owner_key
from terramind.reports.render import build_report, markdown
from terramind.schemas.normalized import NormalizedPlan
from terramind.schemas.report import Report


async def form(request: Request, expected: set[str]) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
        or request.headers.get("content-encoding", "identity") != "identity"
    ):
        raise HTTPException(415, "Use an unencoded form")
    raw = bytearray()
    try:
        async with asyncio.timeout(5):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 4096:
                    raise HTTPException(413, "Form exceeds its size limit")
                raw.extend(chunk)
        pairs = parse_qsl(
            raw.decode("utf-8"),
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=8,
            errors="strict",
        )
        values = dict(pairs)
        if len(values) != len(pairs) or set(values) != expected:
            raise ValueError("Unexpected form fields")
        return values
    except TimeoutError:
        raise HTTPException(408, "Form body timeout") from None
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid form") from None


def history_filters(request: Request) -> tuple[HistoryFilters, dict[str, str]]:
    values = request.query_params
    if set(values) - {"risk", "rule", "from", "to", "cursor"} or any(
        len(values.getlist(key)) > 1 for key in values
    ):
        raise HTTPException(400, "Invalid history filters")
    raw = {key: values.get(key, "") for key in ("risk", "rule", "from", "to")}
    try:
        bounds = []
        for key in ("from", "to"):
            date = datetime.strptime(raw[key], "%Y-%m-%d").replace(tzinfo=UTC) if raw[key] else None
            if date is not None and date.strftime("%Y-%m-%d") != raw[key]:
                raise ValueError("Date must use ISO form")
            if date is not None and key == "to":
                date += timedelta(days=1)
            bounds.append(int(date.timestamp() * 1000000) if date else None)
        result = HistoryFilters.model_validate(
            {
                "risk": raw["risk"] or None,
                "rule": raw["rule"] or None,
                "since": bounds[0],
                "until": bounds[1],
            }
        )
        return result, raw
    except (ValueError, OverflowError):
        raise HTTPException(400, "Invalid history filters") from None


def create_app(
    settings: PortalSettings | None = None,
    store: PortalStore | None = None,
    provider: IdentityProvider | None = None,
    analyzer: Callable[[NormalizedPlan], Report] | None = None,
) -> FastAPI:
    settings = settings or PortalSettings.from_env()
    owned_store = store is None
    store = store or PortalStore(settings.database)
    storage = store
    identity = provider or GoogleOIDC(settings)
    searcher = IncidentSearcher()
    gate = AdmissionGate(6)
    analyze = (
        analyzer or (lambda plan: cloud_analysis(plan, CloudSettings.from_env()))
        if settings.analysis_mode == "cloud"
        else analyzer or build_report
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owned_store:
                storage.close()

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @application.middleware("http")
    async def boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.headers.get("host", "").lower() != urlsplit(settings.origin).netloc.lower():
            return JSONResponse({"detail": "Unrecognized portal host"}, status_code=400)
        if settings.auth_mode == "demo" and (
            request.client is None or request.client.host not in {"127.0.0.1", "::1"}
        ):
            return JSONResponse(
                {"detail": "Demo accounts require a loopback connection"}, status_code=403
            )
        if len(request.scope.get("query_string", b"")) > 8192:
            return JSONResponse({"detail": "Query exceeds its limit"}, status_code=414)
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse({"detail": "Portal unavailable"}, status_code=500)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "strict-origin",
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; img-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            }
        )
        if settings.secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @application.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse({"detail": "Invalid portal request"}, status_code=422)

    @application.exception_handler(DependencyUnavailable)
    @application.exception_handler(sqlite3.Error)
    async def unavailable(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": "Portal storage unavailable"}, status_code=503)

    @application.exception_handler(Throttled)
    async def throttled(request: Request, error: Throttled) -> JSONResponse:
        return JSONResponse(
            {"detail": "Analysis limit reached"}, status_code=429, headers={"Retry-After": "60"}
        )

    def session(request: Request, *, authenticated: bool = True) -> Session:
        found = storage.session(request.cookies.get(settings.cookie_name, ""))
        if found is None or (authenticated and found.owner is None):
            raise HTTPException(401, "Sign in required")
        return found

    def cookie(response: Response, current: Session) -> Response:
        response.set_cookie(
            settings.cookie_name,
            current.token,
            max_age=14400,
            httponly=True,
            secure=settings.secure,
            samesite="lax",
            path="/",
        )
        return response

    def csrf(request: Request, current: Session, values: dict[str, str]) -> None:
        if request.headers.get("origin") != settings.origin or not secrets.compare_digest(
            values.get("csrf", "").encode(), current.csrf.encode()
        ):
            raise HTTPException(403, "Invalid request origin or CSRF token")

    @application.get("/health")
    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "terramind-portal"}

    @application.get("/")
    def root() -> Response:
        return RedirectResponse("/dashboard", status_code=303)

    @application.get("/login")
    def login(request: Request) -> Response:
        current = storage.session(request.cookies.get(settings.cookie_name, ""))
        if current and current.owner:
            return RedirectResponse("/dashboard", status_code=303)
        current = current or storage.new_session()
        return cookie(
            HTMLResponse(views.login(current, demo=settings.auth_mode == "demo")), current
        )

    @application.post("/auth/demo")
    async def demo_login(request: Request) -> Response:
        if settings.auth_mode != "demo":
            raise HTTPException(404, "Not found")
        current = session(request, authenticated=False)
        values = await form(request, {"csrf", "account"})
        csrf(request, current, values)
        account = values["account"]
        if account not in {"analyst", "reviewer"}:
            raise HTTPException(400, "Unknown synthetic account")
        signed_in = storage.new_session(
            owner_key("demo", account), f"Synthetic {account}", previous=current.token
        )
        return cookie(RedirectResponse("/dashboard", status_code=303), signed_in)

    @application.post("/auth/google")
    async def google_login(request: Request) -> Response:
        if settings.auth_mode != "google":
            raise HTTPException(404, "Not found")
        current = session(request, authenticated=False)
        values = await form(request, {"csrf"})
        csrf(request, current, values)
        state, nonce, verifier = storage.begin_flow(current)
        return RedirectResponse(identity.authorize(state, nonce, verifier), status_code=303)

    @application.get("/auth/callback")
    async def callback(request: Request) -> Response:
        if settings.auth_mode != "google":
            raise HTTPException(404, "Not found")
        current = session(request, authenticated=False)
        if any(len(request.query_params.getlist(key)) != 1 for key in ("state", "code")):
            raise HTTPException(400, "Invalid authorization response")
        state = request.query_params.get("state", "")
        flow = storage.consume_flow(current, state)
        if flow is None:
            raise HTTPException(400, "Authorization flow expired or invalid")
        try:
            owner = await run_in_threadpool(identity.exchange, request.query_params["code"], *flow)
        except Exception:
            raise HTTPException(403, "Google account could not be authorized") from None
        signed_in = storage.new_session(owner, "Google account", previous=current.token)
        return cookie(RedirectResponse("/dashboard", status_code=303), signed_in)

    @application.post("/auth/logout")
    async def logout(request: Request) -> Response:
        current = session(request)
        values = await form(request, {"csrf"})
        csrf(request, current, values)
        storage.logout(current.token)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(
            settings.cookie_name, path="/", httponly=True, secure=settings.secure, samesite="lax"
        )
        return response

    @application.get("/dashboard")
    def dashboard(request: Request) -> Response:
        try:
            current = session(request)
        except HTTPException:
            return RedirectResponse("/login", status_code=303)
        filters, raw = history_filters(request)
        try:
            history = storage.history(
                current.owner or "", filters, request.query_params.get("cursor", "")
            )
        except ValueError:
            raise HTTPException(400, "Invalid history filters or cursor") from None
        return HTMLResponse(views.dashboard(current, history, filters, raw, settings.analysis_mode))

    @application.get("/api/history")
    def history_api(request: Request) -> dict[str, object]:
        current = session(request)
        filters, _ = history_filters(request)
        try:
            return storage.history(
                current.owner or "", filters, request.query_params.get("cursor", "")
            )
        except ValueError:
            raise HTTPException(400, "Invalid history filters or cursor") from None

    def create_analysis(owner: str, scenario: str) -> PortalAnalysis:
        with gate.enter():
            plan = (
                demo_plan()
                if scenario == "risk-demo"
                else NormalizedPlan(
                    schema_version="1.0",
                    source="synthetic-demo",
                    changes=(),
                )
            )
            report = analyze(plan)
            bundle = PortalAnalysis(report=report, incident_memory=searcher.search(report))
            storage.save(owner, bundle)
            return bundle

    @application.post("/analyses")
    async def create(request: Request) -> Response:
        current = session(request)
        values = await form(request, {"csrf", "scenario"})
        csrf(request, current, values)
        if values["scenario"] not in {"risk-demo", "benign"}:
            raise HTTPException(400, "Unknown synthetic scenario")
        bundle = await run_in_threadpool(create_analysis, current.owner or "", values["scenario"])
        return RedirectResponse(f"/reports/{bundle.report.analysis_id}", status_code=303)

    def owned(request: Request, report_id: str) -> tuple[Session, PortalAnalysis]:
        current = session(request)
        report = storage.get(current.owner or "", report_id)
        if report is None:
            raise HTTPException(404, "Report not found or expired")
        return current, report

    @application.get("/reports/{report_id}")
    def report_view(request: Request, report_id: str) -> Response:
        current, report = owned(request, report_id)
        return HTMLResponse(views.analysis_page(current, report))

    @application.get("/reports/{report_id}/json")
    def report_json(request: Request, report_id: str) -> Response:
        _, report = owned(request, report_id)
        return Response(report.model_dump_json(), media_type="application/json")

    @application.get("/reports/{report_id}/markdown")
    def report_markdown(request: Request, report_id: str) -> Response:
        _, report = owned(request, report_id)
        text = markdown(report.report) + "\n\n## Incident Memory\n\n"
        text += (
            "Synthetic tabletop exercises only. "
            "Lexical similarity is not evidence of an incident.\n"
        )
        for match in report.incident_memory.matches:
            text += (
                f"\n- {match.doc_id}: {match.title}, cosine {match.similarity:.3f}, "
                f"SHA-256 {match.content_hash}\n"
            )
        return Response(
            text,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="terramind-report.md"'},
        )

    @application.get("/incidents/{doc_id}")
    def incident(request: Request, doc_id: str) -> Response:
        current = session(request)
        document = next(
            (
                doc
                for doc in packaged_corpus()
                if doc.doc_id == doc_id and doc.source_path.startswith("incidents/")
            ),
            None,
        )
        if document is None:
            raise HTTPException(404, "Incident source not found")
        return HTMLResponse(
            views.page(
                document.title,
                f"<h1>{escape(document.title)}</h1>"
                "<p>Synthetic tabletop material, not real incident evidence.</p>"
                f"<p>{escape(document.source_path)}, version {escape(document.version)}</p>"
                f"<code>SHA-256 {document.content_hash}</code><pre>{escape(document.body)}</pre>",
                current,
            )
        )

    @application.get("/assets/{name}")
    def asset(name: str) -> Response:
        if name == "portal.css":
            return Response(
                files("terramind.portal").joinpath("assets/portal.css").read_bytes(),
                media_type="text/css",
            )
        if name in {"terramind-logo.png", "terramind-icon.png"}:
            return Response(
                files("terramind.api").joinpath("assets", name).read_bytes(), media_type="image/png"
            )
        raise HTTPException(404, "Asset not found")

    return application


app = create_app()
