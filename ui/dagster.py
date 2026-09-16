"""Thin async client for the Dagster webserver's GraphQL endpoint.

Reload triggers a workspace reload so a newly saved/deleted agent shows up as a
job; status backs the sidebar health block. Both map transport and Dagster-side
failures onto plain data so callers never see an exception from a reachable-or-not
Dagster: the file operation always succeeds or fails on its own.
"""
from __future__ import annotations

import datetime

import httpx

import config

_RELOAD_MUTATION = (
    "mutation { reloadWorkspace { __typename "
    "... on PythonError { message } "
    "... on UnauthorizedError { message } } }"
)


async def reload() -> dict:
    """Reload the Dagster workspace. Returns {"ok": bool, "message": str}."""
    url = f"{config.DAGSTER_URL}/graphql"
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(url, json={"query": _RELOAD_MUTATION})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"ok": False, "message": f"Dagster unreachable (timeout after {config.RELOAD_TIMEOUT_S}s)"}
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "message": f"Dagster error: {e}"}

    payload = ((data or {}).get("data") or {}).get("reloadWorkspace") or {}
    typename = payload.get("__typename", "")
    if typename in ("WorkspaceLocationEntry", "Workspace") or typename.endswith("Workspace"):
        return {"ok": True, "message": "Workspace reloaded"}
    if "message" in payload:
        return {"ok": False, "message": payload["message"]}
    if data and "errors" in data and data["errors"]:
        return {"ok": False, "message": data["errors"][0].get("message", "unknown GraphQL error")}
    # A bare successful reload with an unrecognised (but non-error) typename.
    return {"ok": True, "message": "Workspace reloaded"}


_LAUNCH_ARMS = (
    " __typename "
    "... on LaunchRunSuccess { run { runId } } "
    "... on PythonError { message } "
    "... on RunConfigValidationInvalid { errors { message } } "
    "... on PipelineNotFoundError { message } "
    "... on InvalidSubsetError { message } "
    "... on ConflictingExecutionParamsError { message } "
    "... on PresetNotFoundError { message } "
    "... on UnauthorizedError { message } "
)


async def launch(cfg: dict) -> dict:
    """Launch a run for an agent (materialize its asset, or run its job). Returns
    ``{"ok": bool, "run_id": str|None, "message": str}`` — Dagster/transport failures are plain data.

    A job (``job: true``, incl. both-kind whose ``agent_<name>`` job materializes the asset) is
    launched by job name; an asset-only agent is materialized through the implicit ``__ASSET_JOB``
    with an asset selection (a daily-partitioned asset targets today's partition, as ``on_cron``
    does).
    """
    location = config.DAGSTER_LOCATION
    repo_sel = f'repositoryLocationName: {_q(location)}, repositoryName: "__repository__"'
    name = cfg.get("name")
    asset = cfg.get("asset")
    asset = asset.strip() if isinstance(asset, str) else ""
    partition = cfg.get("partition") or "none"
    exec_meta = ""
    if cfg.get("job") is True:
        job = "agent_" + str(name).replace("-", "_")
        selector = f"{{{repo_sel}, jobName: {_q(job)}}}"
    elif asset:
        path = ", ".join(_q(s) for s in asset.split("/"))
        selector = f"{{{repo_sel}, jobName: \"__ASSET_JOB\", assetSelection: [{{path: [{path}]}}]}}"
        if partition == "daily":
            day = datetime.datetime.now().strftime("%Y-%m-%d")
            exec_meta = f', executionMetadata: {{tags: [{{key: "dagster/partition", value: {_q(day)}}}]}}'
    else:
        return {"ok": False, "run_id": None, "message": "agent is neither a job nor an asset"}

    mutation = (
        f"mutation {{ launchRun(executionParams: {{ selector: {selector}, "
        f'mode: "default", runConfigData: "{{}}"{exec_meta} }}) {{{_LAUNCH_ARMS}}} }}'
    )
    url = f"{config.DAGSTER_URL}/graphql"
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(url, json={"query": mutation})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"ok": False, "run_id": None, "message": f"Dagster unreachable: {e}"}

    if payload.get("errors"):
        return {"ok": False, "run_id": None,
                "message": payload["errors"][0].get("message", "unknown GraphQL error")}
    node = (payload.get("data") or {}).get("launchRun") or {}
    if node.get("__typename") == "LaunchRunSuccess":
        return {"ok": True, "run_id": (node.get("run") or {}).get("runId"), "message": ""}
    msg = node.get("message")
    if not msg and node.get("errors"):
        msg = "; ".join(e.get("message", "") for e in node["errors"])
    return {"ok": False, "run_id": None, "message": msg or f"launch failed ({node.get('__typename')})"}


async def status() -> dict:
    """Whether Dagster is reachable. Returns {"url": str, "reachable": bool}."""
    url = config.DAGSTER_URL
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(f"{url}/graphql", json={"query": "{ __typename }"})
            reachable = resp.status_code < 500
    except httpx.HTTPError:
        reachable = False
    return {"url": url, "reachable": reachable}


# ── Agents-list activity (one bounded aliased read) ─────────────────────────
# Every *Selector below is identified by the location + the verified repository name
# (contract dagster-activity.md §0, T002). The whole read is ONE POST that aliases each
# agent's sub-reads; any transport/parse failure collapses to reachable:false so the
# page's columns 1–5 still ship (SC-002/SC-005).
_SELECTOR = (
    'repositoryName: "__repository__", '
    'repositoryLocationName: "{location}"'
)


def _q(value: str) -> str:
    """A GraphQL string literal (only ``"`` and ``\\`` need escaping in our identifiers)."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _asset_key_path(row: dict) -> list[str] | None:
    """The asset key segments for an asset row, from its ``/assets/<key>`` dagster_path."""
    path = row.get("dagster_path") or ""
    marker = "/assets/"
    if marker not in path:
        return None
    return [seg for seg in path.split(marker, 1)[1].split("/") if seg]


def _build_query(agents: list[dict]) -> tuple[str, list[tuple[str, dict]]]:
    """Build the aliased GraphQL document and the index used to shape the response."""
    location = config.DAGSTER_LOCATION
    selector = _SELECTOR.format(location=location)
    fields: list[str] = []
    index: list[tuple[str, dict]] = []
    for i, row in enumerate(agents):
        name = row.get("name")
        meta = {"runs": f"a{i}_runs", "inst": [], "checks": None}
        job = row.get("dagster_job") or ("agent_" + str(name).replace("-", "_"))
        fields.append(
            f'{meta["runs"]}: pipelineRunsOrError(filter: {{pipelineName: {_q(job)}}}, limit: 10) '
            f'{{ __typename ... on Runs {{ results {{ runId status startTime endTime }} }} }}'
        )
        for j, cron in enumerate(row.get("crons") or []):
            dname = cron.get("dagster_name")
            if not dname:
                continue
            alias = f"a{i}_inst{j}"
            meta["inst"].append((dname, alias))
            fields.append(
                f'{alias}: instigationStateOrError(instigationSelector: '
                f'{{{selector}, name: {_q(dname)}}}) '
                f'{{ __typename ... on InstigationState {{ id selectorId status }} }}'
            )
        key = _asset_key_path(row) if (row.get("is_asset") and row.get("checks")) else None
        if key:
            alias = f"a{i}_checks"
            meta["checks"] = alias
            path = ", ".join(_q(s) for s in key)
            fields.append(
                f'{alias}: assetNodeOrError(assetKey: {{path: [{path}]}}) '
                f'{{ __typename ... on AssetNode {{ assetChecksOrError {{ __typename '
                f'... on AssetChecks {{ checks {{ name blocking '
                f'executionForLatestMaterialization {{ status evaluation {{ severity }} }} '
                f'}} }} }} }} }}'
            )
        index.append((name, meta))
    query = "query {\n" + "\n".join(fields) + "\n}"
    return query, index


def _parse_runs(node):
    """(latest_run, history) from a pipelineRunsOrError alias; nulls on any error arm."""
    if not isinstance(node, dict) or "results" not in node:
        return None, None
    results = node.get("results") or []
    history = [r.get("status") for r in results][:10]
    latest = None
    if results:
        r0 = results[0]
        latest = {
            "run_id": r0.get("runId"),
            "status": r0.get("status"),
            "start_time": r0.get("startTime"),
            "end_time": r0.get("endTime"),
        }
    return latest, history


def _check_status(execution) -> str:
    """Map a check execution onto the shared status vocabulary (FR-017, §A)."""
    if not isinstance(execution, dict):
        return "not-run"
    st = str(execution.get("status") or "").upper()
    if st == "SUCCEEDED":
        return "pass"
    if st == "FAILED":
        sev = str((execution.get("evaluation") or {}).get("severity") or "").upper()
        return "warn" if sev == "WARN" else "fail-blocking"
    if st in ("EXECUTION_FAILED",):
        return "fail-blocking"
    return "not-run"


def _parse_checks(node):
    """[{name, status}] from an assetNodeOrError alias; None on any non-AssetChecks arm."""
    if not isinstance(node, dict):
        return None
    checks_or_error = node.get("assetChecksOrError")
    if not isinstance(checks_or_error, dict) or "checks" not in checks_or_error:
        return None
    out = []
    for c in checks_or_error.get("checks") or []:
        out.append({
            "name": c.get("name"),
            "status": _check_status(c.get("executionForLatestMaterialization")),
        })
    return out


def _parse_schedules(data: dict, inst: list) -> dict:
    """{dagster_name: {running, id} | null} from the instigation aliases."""
    schedules = {}
    for dname, alias in inst:
        node = data.get(alias)
        if isinstance(node, dict) and node.get("__typename") == "InstigationState":
            status = str(node.get("status") or "").upper()
            schedules[dname] = {"running": status == "RUNNING", "id": node.get("id")}
        else:
            schedules[dname] = None  # not found / error arm → unknown (toggle disabled)
    return schedules


async def activity(agents: list[dict]) -> dict:
    """One bounded, aliased read of per-agent run/instigation/check state (FR-019, SC-005).

    Returns the ``agents-list-view.md §C`` payload keyed by agent name. Never one request per
    agent; any timeout/HTTP/parse failure returns ``{"reachable": False, "agents": {}}`` so the
    page ships columns 1–5 live and 6–8 as em-dashes.
    """
    agents = list(agents or [])
    if not agents:
        return {"reachable": True, "agents": {}}
    query, index = _build_query(agents)
    url = f"{config.DAGSTER_URL}/graphql"
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(url, json={"query": query})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"reachable": False, "agents": {}}

    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        # Whole query failed (top-level errors, no data): degrade rather than fabricate.
        return {"reachable": False, "agents": {}}

    out = {}
    for name, meta in index:
        latest, history = _parse_runs(data.get(meta["runs"]))
        out[name] = {
            "latest_run": latest,
            "history": history,
            "checks": _parse_checks(data.get(meta["checks"])) if meta["checks"] else None,
            "schedules": _parse_schedules(data, meta["inst"]),
        }
    return {"reachable": True, "agents": out}


# ── Schedule / sensor toggle (start / stop one instigator) ──────────────────
# The contract's failure signals are exactly PythonError, UnauthorizedError, and top-level
# GraphQL errors (dagster-activity.md §B); anything else is a successful flip. Start is
# selector-keyed; stop is id-keyed on this Dagster (T002), so a stop first resolves the
# InstigationState id before firing the id-keyed stop mutation.
_ERROR_ARMS = ("PythonError", "UnauthorizedError")


async def _instigation_id(client, url: str, selector: str, name: str) -> str | None:
    """Resolve the InstigationState id for the id-keyed stop mutations, or None if unknown."""
    query = (
        f"query {{ instigationStateOrError(instigationSelector: {{{selector}, name: {_q(name)}}}) "
        f"{{ __typename ... on InstigationState {{ id }} }} }}"
    )
    resp = await client.post(url, json={"query": query})
    resp.raise_for_status()
    node = ((resp.json() or {}).get("data") or {}).get("instigationStateOrError") or {}
    if node.get("__typename") == "InstigationState":
        return node.get("id")
    return None


def _mutation_outcome(payload, field: str, running: bool) -> dict:
    """Shape one mutation response into {ok, running, message} per the contract §B rule."""
    if not isinstance(payload, dict):
        return {"ok": False, "running": None, "message": "Dagster error"}
    if payload.get("errors"):
        return {"ok": False, "running": None,
                "message": payload["errors"][0].get("message", "unknown GraphQL error")}
    node = (payload.get("data") or {}).get(field) or {}
    if node.get("__typename") in _ERROR_ARMS or "message" in node:
        return {"ok": False, "running": None, "message": node.get("message", "mutation failed")}
    return {"ok": True, "running": bool(running), "message": ""}


async def set_instigation(kind: str, name: str, running: bool) -> dict:
    """Start or stop one schedule/sensor. Returns {"ok", "running", "message"} (FR-021, §B).

    ``kind`` ∈ {"schedule", "sensor"} (the §0 toggle-kind, derived by the caller from the
    store row's cron ``type``); ``name`` is the registered instigator name (``sched_<stem>``
    or ``autocond_<stem>``). Start is selector-keyed; stop is id-keyed (T002), so a stop
    resolves the InstigationState id first. Every transport/Dagster failure is plain data.
    """
    location = config.DAGSTER_LOCATION
    selector = _SELECTOR.format(location=location)
    url = f"{config.DAGSTER_URL}/graphql"
    err_arms = (
        " __typename ... on PythonError { message } ... on UnauthorizedError { message } "
    )
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            if running:
                if kind == "schedule":
                    field = "startSchedule"
                    mutation = (
                        f"mutation {{ startSchedule(scheduleSelector: "
                        f"{{{selector}, scheduleName: {_q(name)}}}) {{{err_arms}}} }}"
                    )
                else:
                    field = "startSensor"
                    mutation = (
                        f"mutation {{ startSensor(sensorSelector: "
                        f"{{{selector}, sensorName: {_q(name)}}}) {{{err_arms}}} }}"
                    )
            else:
                inst_id = await _instigation_id(client, url, selector, name)
                if not inst_id:
                    # State never resolved: the toggle should already be disabled (§C).
                    return {"ok": False, "running": None, "message": "Turn on from Dagster"}
                if kind == "schedule":
                    field = "stopRunningSchedule"
                    mutation = f"mutation {{ stopRunningSchedule(id: {_q(inst_id)}) {{{err_arms}}} }}"
                else:
                    field = "stopSensor"
                    mutation = f"mutation {{ stopSensor(id: {_q(inst_id)}) {{{err_arms}}} }}"
            resp = await client.post(url, json={"query": mutation})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"ok": False, "running": None, "message": "Dagster unreachable"}

    return _mutation_outcome(payload, field, running)
