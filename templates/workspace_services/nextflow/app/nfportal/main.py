"""FastAPI application: JSON API, sandboxed file downloads and the Fluent UI single-page app."""

import asyncio
import contextlib
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import (
    DEV_USER,
    SESSION_FLOW,
    SESSION_LIFETIME_SECONDS,
    SESSION_USER,
    AuthClient,
    AuthMiddleware,
    MsalAuthClient,
    User,
    no_role_response,
    safe_next,
    session_payload,
    user_from_claims,
)
from .batch import AzureBatchHeadRunner
from .config import Settings, load_settings
from .pipelines import PipelineCatalog, coerce_params
from .render import PREVIEW_LIMIT, kind_for, parse_table
from .runs import RunService
from .store import (
    BROWSABLE,
    INPUTS,
    PIPELINES,
    AzureBlobStore,
    InvalidPath,
    LocalStore,
    Store,
    content_type_for,
    safe_blob_name,
)

log = logging.getLogger("nfportal")
WRITABLE = (INPUTS, PIPELINES)
REFRESH_SECONDS = 30
WORK_EXPIRY_SECONDS = 6 * 3600
CSRF_HEADER = "x-requested-with"
# nf-azure writes these zero-byte blobs to mark folders it published.
FOLDER_MARKER = ".azure_blob_dir"

# Applies to every response except /files, which sets a stricter sandbox policy.
APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'self'"
)
# Result files come from pipelines, so HTML reports run scripts in an opaque origin with no network access.
FILE_CSP = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data: blob:; font-src data:; media-src data: blob:"
)


class Services:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        runs: RunService,
        catalog: PipelineCatalog,
        auth: AuthClient | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.runs = runs
        self.catalog = catalog
        self.auth = auth


def build_services(settings: Settings) -> Services:
    if settings.dev_mode:
        from .dev import SimulatedHeadRunner

        store: Store = LocalStore(settings.data_dir)
        runner = SimulatedHeadRunner(store)
    else:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        store = AzureBlobStore(settings.blob_endpoint, credential, settings.storage_container)
        runner = AzureBatchHeadRunner(
            settings.batch_endpoint, credential, settings.head_pool_id, settings.runtime_image
        )
    auth = (
        None
        if settings.dev_mode
        else MsalAuthClient(settings.auth_client_id, settings.auth_client_secret, settings.auth_authority)
    )
    return Services(
        settings,
        store,
        RunService(settings, store, runner),
        PipelineCatalog(store, settings.builtin_pipelines_dir),
        auth,
    )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                names = {k.lower() for k, _ in headers}
                defaults = {
                    b"content-security-policy": APP_CSP.encode(),
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"same-origin",
                    b"x-frame-options": b"SAMEORIGIN",
                }
                headers.extend((k, v) for k, v in defaults.items() if k not in names)
            await send(message)

        await self.app(scope, receive, send_with_headers)


class LaunchRequest(BaseModel):
    pipeline_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    label: str = ""


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or load_settings()
    services = services or build_services(settings)
    static_dir = Path(__file__).resolve().parent / "static"

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(_refresh_loop(services))
        yield
        task.cancel()

    app = FastAPI(title="Azure TRE Nextflow portal", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = services
    if not settings.dev_mode and len(settings.session_secret) < 32:
        raise RuntimeError("NF_SESSION_SECRET must be at least 32 characters")
    # Starlette runs the last-added middleware first: security headers, then the session, then sign-in checks.
    app.add_middleware(AuthMiddleware, allowed_roles=settings.allowed_roles, dev_mode=settings.dev_mode)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret or "dev-only-session-secret",
        session_cookie="nfportal_session",
        max_age=SESSION_LIFETIME_SECONDS,
        same_site="lax",
        https_only=not settings.dev_mode,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    def redirect_uri(request: Request) -> str:
        base = settings.public_url or str(request.base_url).rstrip("/")
        return f"{base}/auth/callback"

    @app.get("/auth/login", include_in_schema=False)
    def login(request: Request, next: str = "/"):
        if settings.dev_mode or services.auth is None:
            return RedirectResponse(safe_next(next))
        auth_uri, flow = services.auth.start(redirect_uri(request))
        request.session[SESSION_FLOW] = {"flow": flow, "next": safe_next(next)}
        return RedirectResponse(auth_uri)

    @app.get("/auth/callback", include_in_schema=False)
    def callback(request: Request):
        pending = request.session.pop(SESSION_FLOW, None)
        if not pending or services.auth is None:
            return RedirectResponse("/auth/login")
        try:
            claims = services.auth.finish(pending["flow"], dict(request.query_params))
        except (PermissionError, ValueError) as exc:
            log.warning("Sign-in failed: %s", exc)
            return PlainTextResponse("Sign-in failed. Close this tab and try again.", status_code=401)
        signed_in = user_from_claims(claims, settings.allowed_roles)
        if signed_in is None:
            request.session.clear()
            return no_role_response()
        request.session[SESSION_USER] = session_payload(signed_in)
        return RedirectResponse(pending.get("next") or "/")

    @app.get("/auth/logout", include_in_schema=False)
    def logout(request: Request):
        request.session.clear()
        return PlainTextResponse("You are signed out of the Nextflow portal. Close this browser tab.")

    def user(request: Request) -> User:
        return getattr(request.state, "user", None) or (DEV_USER if settings.dev_mode else _forbidden())

    def require_csrf_header(request: Request) -> None:
        # Cross-site forms cannot set custom headers without a CORS preflight, which this app never allows.
        if request.headers.get(CSRF_HEADER) != "nfportal":
            raise HTTPException(status_code=403, detail="Missing request header")

    api = APIRouter(prefix="/api")

    @api.get("/me")
    def me(u: User = Depends(user)) -> dict:
        return {
            "name": u.name,
            "roles": list(u.roles),
            "is_owner": u.is_owner,
            "service_name": settings.service_name,
            "max_upload_bytes": settings.max_upload_bytes,
        }

    @api.get("/pipelines")
    def list_pipelines() -> list[dict]:
        return [
            {"id": p.id, "name": p.name, "source": p.source, "description": p.description}
            for p in services.catalog.list()
        ]

    @api.get("/pipelines/{pipeline_id}")
    def get_pipeline(pipeline_id: str) -> dict:
        p = services.catalog.get(pipeline_id)
        if not p:
            raise HTTPException(404, "Pipeline not found")
        return {
            "id": p.id,
            "name": p.name,
            "source": p.source,
            "description": p.description,
            "readme": p.readme,
            "fields": [asdict(f) | {"is_path": f.is_path} for f in p.fields],
        }

    @api.get("/runs")
    def list_runs() -> list[dict]:
        return [asdict(r) for r in services.runs.list()]

    @api.post("/runs", status_code=201, dependencies=[Depends(require_csrf_header)])
    def launch(body: LaunchRequest, u: User = Depends(user)):
        p = services.catalog.get(body.pipeline_id)
        if not p:
            raise HTTPException(404, "Pipeline not found")
        params, errors = coerce_params(p.fields, body.params, settings.storage_container)
        if errors:
            return JSONResponse({"errors": errors}, status_code=422)
        return asdict(services.runs.create(u, p, params, body.label))

    def _run_or_404(run_id: str):
        r = services.runs.get(run_id)
        if not r:
            raise HTTPException(404, "Run not found")
        return r

    @api.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        r = services.runs.refresh(_run_or_404(run_id))
        return asdict(r) | {"progress": [asdict(p) for p in services.runs.progress(run_id)]}

    @api.post("/runs/{run_id}/cancel", dependencies=[Depends(require_csrf_header)])
    def cancel_run(run_id: str, u: User = Depends(user)) -> dict:
        r = _run_or_404(run_id)
        try:
            services.runs.cancel(r, u)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        return asdict(r)

    @api.get("/runs/{run_id}/log", response_class=PlainTextResponse)
    def run_log(run_id: str) -> str:
        return services.runs.read_log(_run_or_404(run_id))

    @api.get("/storage/{container}")
    def list_files(container: str, prefix: str = "") -> list[dict]:
        _check_container(container)
        return [
            {
                "name": i.name,
                "size": i.size,
                "last_modified": i.last_modified.isoformat() if i.last_modified else None,
                "kind": kind_for(i.name),
            }
            for i in services.store.list(container, prefix)
            if not i.name.endswith(FOLDER_MARKER)
        ]

    @api.get("/storage/{container}/preview")
    def preview(container: str, name: str = Query(...)) -> dict:
        _check_container(container)
        name = _safe(name)
        kind = kind_for(name)
        url = f"/files/{container}/{quote(name)}"
        result: dict[str, Any] = {"name": name, "kind": kind, "url": url}
        if kind in ("table", "text", "markdown"):
            data = services.store.read_head(container, name, PREVIEW_LIMIT)
            if data is None:
                raise HTTPException(404, "File not found")
            truncated = len(data) >= PREVIEW_LIMIT
            if kind == "table":
                columns, rows, more = parse_table(name, data)
                result |= {"columns": columns, "rows": rows, "truncated": truncated or more}
            else:
                result |= {"text": data.decode("utf-8", "replace"), "truncated": truncated}
        return result

    @api.post("/storage/{container}", status_code=201, dependencies=[Depends(require_csrf_header)])
    async def upload(container: str, files: list[UploadFile] = File(...), folder: str = Form("")) -> dict:
        if container not in WRITABLE:
            raise HTTPException(403, "Uploads are only allowed to inputs or pipelines")
        names = []
        for f in files:
            if f.size is not None and f.size > settings.max_upload_bytes:
                raise HTTPException(413, f"{f.filename} is larger than the upload limit")
            name = _safe(f"{folder.strip('/')}/{f.filename}" if folder.strip("/") else (f.filename or ""))
            await run_in_threadpool(services.store.write_stream, container, name, f.file)
            names.append(name)
        return {"uploaded": names}

    @api.delete("/storage/{container}", dependencies=[Depends(require_csrf_header)])
    def delete_file(container: str, name: str = Query(...)) -> dict:
        if container not in WRITABLE:
            raise HTTPException(403, "Files can only be deleted from inputs or pipelines")
        services.store.delete(container, _safe(name))
        return {"deleted": name}

    app.include_router(api)

    @app.get("/files/{container}/{path:path}")
    def download(container: str, path: str, download: bool = False):
        _check_container(container)
        name = _safe(path)
        size = services.store.size(container, name)
        if size is None:
            raise HTTPException(404, "File not found")
        kind = kind_for(name)
        headers = {"Content-Length": str(size), "Cache-Control": "private, no-store"}
        if kind != "pdf":  # browsers do not render PDFs inside a CSP sandbox
            headers["Content-Security-Policy"] = FILE_CSP
        if download or kind == "binary":
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(Path(name).name)}"
        media_type = content_type_for(name)
        if kind == "text" or kind == "table":
            media_type = "text/plain; charset=utf-8"
        return StreamingResponse(services.store.iter_bytes(container, name), media_type=media_type, headers=headers)

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz() -> str:
        return "ok"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and static_dir in candidate.parents:
            return FileResponse(candidate)
        index = static_dir / "index.html"
        if full_path.startswith(("api/", "files/")) or not index.is_file():
            raise HTTPException(404)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


def _forbidden():
    raise HTTPException(403)


def _check_container(container: str) -> None:
    if container not in BROWSABLE:
        raise HTTPException(404, "Unknown storage area")


def _safe(name: str) -> str:
    try:
        return safe_blob_name(name)
    except InvalidPath as exc:
        raise HTTPException(400, str(exc)) from exc


async def _refresh_loop(services: Services) -> None:
    next_expiry = 0.0
    while True:
        try:
            await run_in_threadpool(services.runs.refresh_active)
            if time.monotonic() >= next_expiry:
                deleted = await run_in_threadpool(services.runs.expire_work)
                if deleted:
                    log.info("Deleted %d expired work files", deleted)
                next_expiry = time.monotonic() + WORK_EXPIRY_SECONDS
        except Exception:  # keep polling; a transient Batch or storage error must not stop reconciliation
            log.exception("Run refresh failed")
        await asyncio.sleep(REFRESH_SECONDS)
