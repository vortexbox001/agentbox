"""Agentbox control center: the FastAPI app skeleton.

Pages are server-rendered Jinja2; everything under /api returns JSON. This module
wires the app shell, static mounts, the schema endpoint the form renders from, and
the Dagster reload/status endpoints. Agent and prompt CRUD routes are added by the
user-story phases; the shell and these foundational routes are what they build on.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

import agents_store
import config
import dagster
import prompts_store
import schema
from agents_store import StorageError

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_UI_DIR, "templates")
_STATIC_DIR = os.path.join(_UI_DIR, "static")
_DESIGN_DOC = "Archon Design System.dc.html"

app = FastAPI(title="Agentbox")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def public_dagster_url(request: Request) -> str:
    """A Dagster base URL the user's browser can reach.

    The internal DAGSTER_URL points at the in-network hostname (dagster-webserver),
    which does not resolve from a browser. Prefer an explicit DAGSTER_PUBLIC_URL; else
    derive one from the request host, keeping the Dagster port from DAGSTER_URL.
    """
    if config.DAGSTER_PUBLIC_URL:
        return config.DAGSTER_PUBLIC_URL.rstrip("/")
    port = urlparse(config.DAGSTER_URL).port or 3000
    host = request.url.hostname or "localhost"
    scheme = request.url.scheme or "http"
    return f"{scheme}://{host}:{port}"


def _shell_context(request: Request, **extra) -> dict:
    ctx = {"request": request, "dagster_url": public_dagster_url(request)}
    ctx.update(extra)
    return ctx


# --- Error handling -------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(detail, status_code=exc.status_code)
        return JSONResponse({"error": "http", "message": str(detail)}, status_code=exc.status_code)
    # Pages: keep the default HTML behaviour.
    return JSONResponse({"error": "http", "message": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(StorageError)
async def _storage_error(request: Request, exc: StorageError):
    # A filesystem failure on any endpoint: name the mount and operation (507).
    return JSONResponse(
        {"error": "storage", "message": f"cannot {exc.operation} {exc.path}: {exc.os_error}"},
        status_code=507,
    )


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(
        {"error": "validation", "message": "request body failed validation", "detail": exc.errors()},
        status_code=422,
    )


# --- Design system (registered before the static mount so the exact paths win) ---
@app.get("/design-system")
async def _design_root_redirect():
    # Trailing slash so the document's relative ./support.js and ./archon-tokens.css resolve.
    return RedirectResponse("/design-system/", status_code=302)


@app.get("/design-system/")
async def _design_index():
    return FileResponse(os.path.join(config.DESIGN_SYSTEM_DIR, _DESIGN_DOC), media_type="text/html")


app.mount("/design-system", StaticFiles(directory=config.DESIGN_SYSTEM_DIR, html=False), name="design-system")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# --- Pages ----------------------------------------------------------------
@app.get("/")
async def _root_redirect():
    return RedirectResponse("/agents", status_code=302)


@app.get("/agents")
async def _agents_page(request: Request):
    # The list reflects the filesystem exactly: every non-template agent, templates
    # excluded. Row Dagster links are built in the template from the browser-facing
    # base URL (dagster_url in the shell context) plus each row's dagster_job.
    listing = agents_store.list_agents()
    return templates.TemplateResponse(
        request,
        "agents/list.html",
        _shell_context(request, title="Agents", agents=listing["agents"]),
    )


# --- API ------------------------------------------------------------------
@app.get("/api/agents")
async def _api_agents():
    # {"agents": [...non-template rows...], "templates": [{"file", "harness"}]}.
    # Broken files carry parse_error with other fields null; a file written by a
    # newer schema is reported editable: false (agents_store.list_agents).
    return JSONResponse(agents_store.list_agents())


@app.get("/api/schema")
async def _api_schema():
    payload = schema.to_public()
    payload["litellm_aliases"] = schema.litellm_aliases()
    payload["prompts"] = prompts_store.prompt_names()
    return JSONResponse(payload)


@app.post("/api/dagster/reload")
async def _api_reload():
    # Always 200: the outcome is data, not a transport failure.
    return JSONResponse(await dagster.reload())


@app.get("/api/dagster/status")
async def _api_dagster_status():
    return JSONResponse(await dagster.status())
