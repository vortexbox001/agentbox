"""Agentbox control center: the FastAPI app skeleton.

Pages are server-rendered Jinja2; everything under /api returns JSON. This module
wires the app shell, static mounts, the schema endpoint the form renders from, and
the Dagster reload/status endpoints. Agent and prompt CRUD routes are added by the
user-story phases; the shell and these foundational routes are what they build on.
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

import agents_store
import config
import cron_text
import dagster
import prompts_store
import schema
import secret_scan
from agents_store import StorageError
from prompts_store import PromptValidationError

_UI_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_UI_DIR, "templates")
_STATIC_DIR = os.path.join(_UI_DIR, "static")

app = FastAPI(title="Agentbox")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Inline the icon sprite once per page (research R3, FR-023): base.html renders {{ icon_sprite }}
# so every <use href="#id"> resolves document-relative with no separate sprite fetch (works with
# egress blocked, SC-007). Read once at import; ui/static/icons.svg stays the single source the
# design-system sync test pins.
with open(os.path.join(_STATIC_DIR, "icons.svg"), encoding="utf-8") as _sprite_fh:
    _ICON_SPRITE = _sprite_fh.read()
templates.env.globals["icon_sprite"] = _ICON_SPRITE

# One shared cron-to-text helper (research R6, FR-016): the schedules/sensors column renders
# each cron's human label server-side, in the box timezone, so it ships with first paint.
templates.env.globals["cron_text"] = cron_text.cron_text

# Operational logging (T050): one INFO line per mutating action so an operator can
# trace what the UI wrote. Env values are never logged — only stems and outcomes.
# Uvicorn configures its own loggers, not the root, so attach a handler here to make
# sure these lines actually reach stdout/stderr (and the container log).
logger = logging.getLogger("agentbox.ui")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _unsafe_name(value: str) -> bool:
    """True when a user-supplied stem/filename must be refused before any FS access.

    A separator (``/``, ``\\``), ``..``, or a leading dot could escape the mount or
    address a dotfile, so every route path-checks its stem/filename first (FR-010a).
    A rejected agent stem is reported as "no such agent" (404); a rejected prompt
    filename is a validation error (400) — the callers apply the right status.
    """
    return (not value) or value[0] == "." or "/" in value or "\\" in value or ".." in value


def public_dagster_url(request: Request) -> str:
    """A Dagster base URL the user's browser can reach.

    The internal DAGSTER_URL points at the in-network hostname (dagster-webserver),
    which does not resolve from a browser, and its 3000 is the *container* port. The
    browser reaches the host-published port, DAGSTER_HOST_PORT.

    Prefer an explicit DAGSTER_PUBLIC_URL (composed as ``{host base}:{DAGSTER_HOST_PORT}``
    when it carries no port of its own); else derive one from the request host with
    DAGSTER_HOST_PORT.
    """
    if config.DAGSTER_PUBLIC_URL:
        return _compose_public_base(config.DAGSTER_PUBLIC_URL, config.DAGSTER_HOST_PORT)
    host = request.url.hostname or "localhost"
    scheme = request.url.scheme or "http"
    return f"{scheme}://{host}:{config.DAGSTER_HOST_PORT}"


def _compose_public_base(value: str, default_port: str) -> str:
    """Normalize a configured DAGSTER_PUBLIC_URL into a browser-usable base.

    Tolerates a bare host base (no scheme, no port) and an accidental doubled scheme
    (``http://http://host``). Appends ``:default_port`` only when no port is present,
    so an explicit port in DAGSTER_PUBLIC_URL (e.g. behind a 443 proxy) is preserved.
    """
    value = value.strip().rstrip("/")
    # Collapse a doubled scheme like "http://http://10.0.0.100".
    while (m := re.match(r"(?i)^(https?://)(?=https?://)", value)):
        value = value[len(m.group(1)):]
    if not re.match(r"(?i)^https?://", value):
        value = "http://" + value
    parsed = urlparse(value)
    if parsed.port is None and parsed.hostname:
        parsed = parsed._replace(netloc=f"{parsed.hostname}:{default_port}")
        value = urlunparse(parsed).rstrip("/")
    return value


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
# The old dark-theme reference doc and its inline assets are gone (spec 009 FR-001);
# the in-repo design-system bundle is served here at /design-system/. With html=True
# the mount serves the bundle's own index.html — the specimen gallery that renders every
# component and foundation from _ds_manifest.json on the current design — at
# /design-system/ (FR-003, US3/T018, T034).
@app.get("/design-system")
async def _design_root_redirect():
    # Trailing slash so the bundle's relative asset paths resolve under the mount.
    return RedirectResponse("/design-system/", status_code=302)


app.mount("/design-system", StaticFiles(directory=config.DESIGN_SYSTEM_DIR, html=True), name="design-system")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# --- Pages ----------------------------------------------------------------
@app.get("/")
async def _root_redirect():
    return RedirectResponse("/agents", status_code=302)


# The tabbed list's five tabs, in render order (contract agents-list-view §B). Ids are the
# lowercase URL `?tab=` values; counts are computed server-side and correct with Dagster down.
_TAB_IDS = ("all", "assets", "jobs", "scheduled", "disabled")


def _tab_counts(rows: list[dict]) -> dict:
    """Server-side tab counts (FR-013). Both-kind agents count in both Assets and Jobs."""
    return {
        "all": len(rows),
        "assets": sum(1 for r in rows if r.get("is_asset")),
        "jobs": sum(1 for r in rows if r.get("is_job")),
        "scheduled": sum(1 for r in rows if r.get("crons")),
        "disabled": sum(1 for r in rows if r.get("enabled") is False),
    }


@app.get("/agents")
async def _agents_page(request: Request):
    # The list reflects the filesystem exactly: every non-template agent, templates
    # excluded. Columns 1–5 render from the store row (Schedules/Sensors renders the pills,
    # icon, and cron-to-text label live; only the toggle state and columns 6–8 fill after
    # first paint via GET /api/agents/activity). Row Dagster links are built in the template
    # from the browser-facing base URL (dagster_url) plus each row's dagster_path.
    listing = agents_store.list_agents()
    rows = listing["agents"]
    active_tab = (request.query_params.get("tab") or "all").lower()
    if active_tab not in _TAB_IDS:
        active_tab = "all"
    return templates.TemplateResponse(
        request,
        "agents/list.html",
        _shell_context(
            request,
            title="Agents",
            agents=rows,
            tab_counts=_tab_counts(rows),
            active_tab=active_tab,
        ),
    )


@app.get("/agents/new")
async def _agents_new_page(request: Request):
    # The schema-driven create form. ?from=<template-file> pre-fills from a template
    # (the JS reads GET /api/agents/{from}). The page itself is side-effect free.
    from_stem = request.query_params.get("from") or ""
    # A traversal/dotfile ?from= can never name a template: drop it before it reaches
    # the client's GET /api/agents/{from} (FR-010a).
    if from_stem and _unsafe_name(from_stem):
        from_stem = ""
    return templates.TemplateResponse(
        request,
        "agents/form.html",
        _shell_context(
            request,
            title="New agent",
            mode="create",
            from_template=from_stem,
            breadcrumb_leaf="New",
        ),
    )


@app.get("/agents/{name}")
async def _agents_edit_page(request: Request, name: str):
    # The edit form for one agent. Fields are rendered client-side (agent-form.js
    # reads GET /api/agents/{name}); the server sets the mode/stem the module needs,
    # and renders the error banner + raw file block for a broken or too-new file.
    # A file written by a newer schema (editable is false) shows no form at all —
    # only the banner, the raw contents, and the Delete action.
    if _unsafe_name(name):
        return templates.TemplateResponse(
            request,
            "404.html",
            _shell_context(request, title="Not found", breadcrumb_leaf="Not found", missing=name),
            status_code=404,
        )
    try:
        info = agents_store.read_agent(name)
    except FileNotFoundError:
        return templates.TemplateResponse(
            request,
            "404.html",
            _shell_context(request, title="Not found", breadcrumb_leaf="Not found", missing=name),
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "agents/form.html",
        _shell_context(
            request,
            title=info["name"],
            mode="edit",
            stem=name,
            from_template="",
            breadcrumb_leaf=info["name"],
            editable=info["editable"],
            show_form=info["editable"],
            parse_error=info["parse_error"],
            raw=info["raw"],
            name_mismatch=info["name_mismatch"],
            dagster_path=info["dagster_path"],
            dagster_kind=info["dagster_kind"],
        ),
    )


# --- API ------------------------------------------------------------------
@app.get("/api/agents")
async def _api_agents():
    # {"agents": [...non-template rows...], "templates": [{"file", "harness"}]}.
    # Broken files carry parse_error with other fields null; a file written by a
    # newer schema is reported editable: false (agents_store.list_agents).
    return JSONResponse(agents_store.list_agents())


@app.get("/api/agents/activity")
async def _api_agents_activity():
    # Dagster-derived columns 6–8 + pill toggle state, filled after first paint. Always 200:
    # the outcome is data (mirroring /api/dagster/status). One bounded aliased read; a
    # reachable:false payload leaves the client's columns 6–8 as em-dashes (contract §C).
    listing = agents_store.list_agents()
    return JSONResponse(await dagster.activity(listing["agents"]))


def _normalise_prompt_filename(new_prompt: dict | None) -> str | None:
    """The .md filename a new_prompt block will produce, or None when absent."""
    if not new_prompt:
        return None
    fn = str(new_prompt.get("filename") or "").strip()
    if not fn:
        return None
    return fn if fn.endswith(".md") else f"{fn}.md"


def _prompt_exists_factory(pending_name: str | None):
    """A prompt_exists predicate that also accepts a prompt created in the same save."""

    def _exists(pf: str) -> bool:
        return (pending_name is not None and pf == pending_name) or prompts_store.exists(pf)

    return _exists


def _stored_agent(stem: str) -> dict | None:
    """Read back the just-written definition so the response reflects the file."""
    try:
        return agents_store.read_agent(stem)["agent"]
    except FileNotFoundError:
        return None


async def _write_agent(request: Request, stem_from_path: str | None) -> JSONResponse:
    """Shared create/update pipeline (contract POST/PUT /api/agents).

    ``stem_from_path`` is None for create (name comes from the body) and the path
    segment for update. On update the file must already exist, the name (the
    filename identity) cannot change, and keys the UI does not manage are carried
    over from the stored file when the payload omits them.
    """
    body = await request.json()
    agent = dict(body.get("agent") or {})
    new_prompt = body.get("new_prompt")
    confirmed = set(body.get("confirm_not_secret") or [])
    reload_requested = bool(body.get("reload_dagster", True))
    is_update = stem_from_path is not None

    # Path-check the update stem before any filesystem access (FR-010a): an unsafe
    # stem behaves as "no such agent". Create's stem comes from the body and is
    # validated by the schema's name pattern.
    if is_update and _unsafe_name(stem_from_path):
        return JSONResponse(
            {"error": "not_found", "message": f"agents/{stem_from_path}.yaml does not exist"},
            status_code=404,
        )

    if is_update:
        try:
            existing = agents_store.read_agent(stem_from_path)
        except FileNotFoundError:
            return JSONResponse(
                {"error": "not_found", "message": f"agents/{stem_from_path}.yaml does not exist"},
                status_code=404,
            )
        # The filename is the agent's identity: an edit can never rename it.
        payload_name = agent.get("name")
        if payload_name is not None and str(payload_name) != stem_from_path:
            return JSONResponse(
                {"error": "validation",
                 "fields": {"name": "name cannot be changed; delete and recreate"}},
                status_code=400,
            )
        agent["name"] = stem_from_path
        # Preserve keys the UI does not know when the payload leaves them out.
        if "unmanaged" not in agent:
            loaded = existing.get("agent") or {}
            if loaded.get("unmanaged"):
                agent["unmanaged"] = loaded["unmanaged"]

    pending_prompt = _normalise_prompt_filename(new_prompt)
    if pending_prompt:
        agent["prompt_file"] = pending_prompt

    # Validation (400). A prompt created in this same save counts as existing.
    errors = schema.validate(agent, prompt_exists=_prompt_exists_factory(pending_prompt))
    if errors:
        return JSONResponse({"error": "validation", "fields": errors}, status_code=400)

    # Secret confirmation (409). ${NAME} passthrough is never flagged. Checked
    # before any file is written so a confirm-and-retry never leaves an orphaned
    # prompt behind.
    flagged = [k for k in secret_scan.flagged_keys(agent.get("env") or {}) if k not in confirmed]
    if flagged:
        return JSONResponse(
            {"error": "secret_confirmation_required", "flagged": flagged},
            status_code=409,
        )

    # Create the inline prompt first (write #1), then point the agent at it.
    created_prompt: str | None = None
    if new_prompt:
        try:
            created_prompt = prompts_store.create_prompt(new_prompt.get("filename"), new_prompt.get("content"))
        except FileExistsError as e:
            return JSONResponse({"error": "prompt_exists", "message": str(e)}, status_code=409)
        except PromptValidationError as e:
            return JSONResponse(
                {"error": "validation", "fields": {"new_prompt": str(e)}}, status_code=400
            )
        logger.info("event=prompt_created file=%s", created_prompt)
        agent["prompt_file"] = created_prompt

    # Agent write (write #2). On create, refuse to overwrite an existing file. If a
    # prompt was just created, the file already landed: say so in the message so the
    # user knows about the partial two-write (CHK045), and the form can refresh its
    # selector rather than silently orphaning the prompt.
    stem = str(agent.get("name"))
    if not is_update and agents_store.agent_exists(stem):
        message = f"agents/{stem}.yaml already exists"
        if created_prompt:
            message += f"; the prompt `{created_prompt}` was created"
        return JSONResponse({"error": "exists", "message": message}, status_code=409)

    agents_store.write_agent(stem, agent)

    warning = schema.network_mismatch_warning(agent)
    warnings = [warning] if warning else []

    if reload_requested:
        outcome = await dagster.reload()
        reload_result = {"requested": True, "ok": outcome["ok"], "message": outcome["message"]}
    else:
        reload_result = {"requested": False, "ok": None, "message": None}

    logger.info(
        "event=%s stem=%s reload_ok=%s",
        "agent_updated" if is_update else "agent_created",
        stem,
        reload_result["ok"],
    )

    return JSONResponse(
        {
            "agent": _stored_agent(stem),
            "file": f"{stem}.yaml",
            "warnings": warnings,
            "reload": reload_result,
        },
        status_code=200 if is_update else 201,
    )


@app.post("/api/agents")
async def _api_create_agent(request: Request):
    # Create a new agent file, optionally an inline prompt, optionally reload Dagster.
    return await _write_agent(request, None)


@app.put("/api/agents/{name}")
async def _api_update_agent(name: str, request: Request):
    # Rewrite an existing agent file; same pipeline as create, keyed by the path stem.
    return await _write_agent(request, name)


@app.delete("/api/agents/{name}")
async def _api_delete_agent(name: str, request: Request):
    # Remove agents/<name>.yaml only; workspace and output directories are never
    # touched (the store's delete_agent removes the single file). reload_dagster
    # (query or JSON body, default true) drives an optional workspace reload whose
    # outcome mirrors create/update's reload shape. 404 when the file is absent.
    if _unsafe_name(name):
        return JSONResponse(
            {"error": "not_found", "message": f"agents/{name}.yaml does not exist"},
            status_code=404,
        )

    reload_requested = True
    qp = request.query_params.get("reload_dagster")
    if qp is not None:
        reload_requested = qp.lower() not in ("false", "0", "no")
    else:
        try:
            body = await request.json()
        except Exception:
            body = None
        if isinstance(body, dict) and "reload_dagster" in body:
            reload_requested = bool(body["reload_dagster"])

    try:
        deleted = agents_store.delete_agent(name)
    except FileNotFoundError:
        return JSONResponse(
            {"error": "not_found", "message": f"agents/{name}.yaml does not exist"},
            status_code=404,
        )

    if reload_requested:
        outcome = await dagster.reload()
        reload_result = {"requested": True, "ok": outcome["ok"], "message": outcome["message"]}
    else:
        reload_result = {"requested": False, "ok": None, "message": None}

    logger.info("event=agent_deleted stem=%s reload_ok=%s", name, reload_result["ok"])

    return JSONResponse({"deleted": deleted, "reload": reload_result})


@app.post("/api/agents/preview")
async def _api_preview_agent(request: Request):
    # Return the exact YAML a save would write. No file write, no secret check.
    body = await request.json()
    agent = dict(body.get("agent") or {})
    errors = schema.validate(agent, prompt_exists=prompts_store.exists)
    if errors:
        return JSONResponse({"error": "validation", "fields": errors}, status_code=400)
    warning = schema.network_mismatch_warning(agent)
    return JSONResponse(
        {"yaml": agents_store.emit_yaml(agent), "warnings": [warning] if warning else []}
    )


@app.get("/api/agents/{name}")
async def _api_read_agent(name: str):
    # Full stored definition for the edit form and ?from= template pre-fill.
    if _unsafe_name(name):
        return JSONResponse(
            {"error": "not_found", "message": f"agents/{name}.yaml does not exist"},
            status_code=404,
        )
    try:
        info = agents_store.read_agent(name)
    except FileNotFoundError:
        return JSONResponse(
            {"error": "not_found", "message": f"agents/{name}.yaml does not exist"},
            status_code=404,
        )
    return JSONResponse({
        "agent": info["agent"],
        "file": info["file"],
        "parse_error": info["parse_error"],
        "raw": info["raw"],
        "name_mismatch": info["name_mismatch"],
        "editable": info["editable"],
    })


@app.get("/api/templates/{name}")
async def _api_read_template(name: str):
    # Full definition of a product-owned starter, read from the examples tree, for the
    # create form's ?from= pre-fill (FR-008). Templates no longer live in the instance
    # agents dir, so the picker reads them here rather than from GET /api/agents/{name}.
    if _unsafe_name(name):
        return JSONResponse(
            {"error": "not_found", "message": f"template {name} does not exist"},
            status_code=404,
        )
    try:
        info = agents_store.read_template(name)
    except FileNotFoundError:
        return JSONResponse(
            {"error": "not_found", "message": f"template {name} does not exist"},
            status_code=404,
        )
    return JSONResponse({
        "agent": info["agent"],
        "file": info["file"],
        "parse_error": info["parse_error"],
        "raw": info["raw"],
        "name_mismatch": info["name_mismatch"],
        "editable": info["editable"],
    })


@app.get("/api/prompts")
async def _api_prompts():
    # Every prompt file with size + modified; the selector's source (SC-005).
    return JSONResponse({"prompts": prompts_store.list_prompts()})


@app.get("/api/prompts/{filename:path}")
async def _api_prompt(filename: str):
    # The :path capture lets an unsafe value (a separator, .., or leading dot) reach
    # the handler so it is refused as 400 here rather than mis-routed to 404 (FR-010a).
    if _unsafe_name(filename):
        return JSONResponse(
            {"error": "validation", "message": "prompt filename must not contain / \\ or .."},
            status_code=400,
        )
    try:
        content = prompts_store.read_prompt(filename)
    except PromptValidationError:
        return JSONResponse(
            {"error": "validation", "message": "prompt filename must not contain / \\ or .."},
            status_code=400,
        )
    except FileNotFoundError:
        return JSONResponse(
            {"error": "not_found", "message": f"prompts/{filename} does not exist"},
            status_code=404,
        )
    return JSONResponse({"filename": filename, "content": content})


@app.post("/api/prompts")
async def _api_create_prompt(request: Request):
    # Standalone prompt creation (the form also creates prompts inline on save).
    body = await request.json()
    try:
        created = prompts_store.create_prompt(body.get("filename"), body.get("content"))
    except FileExistsError as e:
        return JSONResponse({"error": "exists", "message": str(e)}, status_code=409)
    except PromptValidationError as e:
        return JSONResponse({"error": "validation", "message": str(e)}, status_code=400)
    logger.info("event=prompt_created file=%s", created)
    return JSONResponse({"filename": created}, status_code=201)


@app.get("/api/schema")
async def _api_schema():
    payload = schema.to_public()
    payload["litellm_aliases"] = schema.litellm_aliases()
    payload["prompts"] = prompts_store.prompt_names()
    return JSONResponse(payload)


@app.post("/api/dagster/reload")
async def _api_reload():
    # Always 200: the outcome is data, not a transport failure.
    outcome = await dagster.reload()
    logger.info("event=dagster_reloaded ok=%s", outcome.get("ok"))
    return JSONResponse(outcome)


@app.get("/api/dagster/status")
async def _api_dagster_status():
    return JSONResponse(await dagster.status())
