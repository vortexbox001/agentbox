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

# Asset materializations triggered by an automation condition run under Dagster's implicit
# asset job, NOT under the agent's own `agent_<name>` pipeline, and identify their target only
# via `assetSelection`. So an asset agent's run history is read from this shared pipeline and
# filtered client-side by asset key (RunsFilter has no asset-key field on this Dagster). The
# limit is shared across every asset agent, so it is generous enough that a busy asset does not
# starve a quiet one of its last-10 history.
_ASSET_JOB_PIPELINE = "__ASSET_JOB"
_ASSET_RUNS_LIMIT = 250


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
    any_asset = False
    for i, row in enumerate(agents):
        name = row.get("name")
        asset_key = _asset_key_path(row) if row.get("is_asset") else None
        # A plain job agent (and, defensively, a parse-error row that is neither kind) reads its
        # own `agent_<name>` pipeline; an asset-only agent has no such job, so it reads runs only
        # from the shared asset job (below). A both-kind agent reads both and they are merged.
        has_job = bool(row.get("is_job")) or asset_key is None
        meta = {"runs": None, "asset_key": asset_key, "inst": [], "checks": None}
        if has_job:
            meta["runs"] = f"a{i}_runs"
            job = row.get("dagster_job") or ("agent_" + str(name).replace("-", "_"))
            fields.append(
                f'{meta["runs"]}: pipelineRunsOrError(filter: {{pipelineName: {_q(job)}}}, limit: 10) '
                f'{{ __typename ... on Runs {{ results {{ runId status startTime endTime }} }} }}'
            )
        if asset_key is not None:
            any_asset = True
        for j, cron in enumerate(row.get("crons") or []):
            dname = cron.get("dagster_name")
            if not dname:
                continue
            alias = f"a{i}_inst{j}"
            ctype = cron.get("type")
            meta["inst"].append((dname, alias, ctype))
            # A GitHub Projects sensor (spec 016) also reads its latest tick's SkipReason so the
            # Automation view can surface the held issues / first-tick report (FR-025, ui §3).
            tick_frag = (" ticks(limit: 1) { skipReason }"
                         if ctype == "project_status" else "")
            fields.append(
                f'{alias}: instigationStateOrError(instigationSelector: '
                f'{{{selector}, name: {_q(dname)}}}) '
                f'{{ __typename ... on InstigationState {{ id selectorId status{tick_frag} }} }}'
            )
        if asset_key is not None and row.get("checks"):
            alias = f"a{i}_checks"
            meta["checks"] = alias
            path = ", ".join(_q(s) for s in asset_key)
            fields.append(
                f'{alias}: assetNodeOrError(assetKey: {{path: [{path}]}}) '
                f'{{ __typename ... on AssetNode {{ assetChecksOrError {{ __typename '
                f'... on AssetChecks {{ checks {{ name blocking '
                f'executionForLatestMaterialization {{ status evaluation {{ severity }} }} '
                f'}} }} }} }} }}'
            )
        index.append((name, meta))
    if any_asset:
        # One shared read of the implicit asset job's recent runs, selecting `assetSelection` so
        # each asset agent's materializations can be bucketed by key when the response is shaped.
        fields.append(
            f'asset_runs: pipelineRunsOrError('
            f'filter: {{pipelineName: {_q(_ASSET_JOB_PIPELINE)}}}, limit: {_ASSET_RUNS_LIMIT}) '
            f'{{ __typename ... on Runs {{ results {{ runId status startTime endTime '
            f'assetSelection {{ path }} }} }} }}'
        )
    query = "query {\n" + "\n".join(fields) + "\n}"
    return query, index


def _results_of(node):
    """The ``results`` list from a pipelineRunsOrError alias, or ``[]`` on any error arm."""
    if not isinstance(node, dict) or "results" not in node:
        return []
    return node.get("results") or []


def _run_row(r: dict) -> dict:
    """One run result shaped into the ``latest_run`` payload (agents-list-view.md §C)."""
    return {
        "run_id": r.get("runId"),
        "status": r.get("status"),
        "start_time": r.get("startTime"),
        "end_time": r.get("endTime"),
    }


def _selection_has_key(run: dict, key: list[str]) -> bool:
    """Whether a ``__ASSET_JOB`` run materialized the given asset key (its ``assetSelection``)."""
    for sel in run.get("assetSelection") or []:
        if isinstance(sel, dict) and sel.get("path") == key:
            return True
    return False


def _parse_runs(node):
    """(latest_run, history) from a pipelineRunsOrError alias; nulls on any error arm.

    Dagster returns results newest-first, so the first row is the latest and the statuses are the
    history in order.
    """
    if not isinstance(node, dict) or "results" not in node:
        return None, None
    results = node.get("results") or []
    history = [r.get("status") for r in results][:10]
    latest = _run_row(results[0]) if results else None
    return latest, history


def _agent_runs(data: dict, meta: dict, asset_runs: list) -> tuple[dict | None, list | None]:
    """(latest_run, history) for one agent, merging its job pipeline and asset materializations.

    A plain job agent reads only its ``agent_<name>`` pipeline (Dagster order preserved). An asset
    agent's materializations run under ``__ASSET_JOB``, so they are taken from the shared read and
    filtered by asset key; a both-kind agent merges those with any job-launched runs and sorts the
    union newest-first (``startTime`` desc, unstarted runs last).
    """
    key = meta.get("asset_key")
    if key is None:
        return _parse_runs(data.get(meta["runs"]))
    results = [r for r in asset_runs if _selection_has_key(r, key)]
    if meta["runs"] is not None:
        results = results + _results_of(data.get(meta["runs"]))
    if not results:
        return None, None
    results.sort(key=lambda r: r.get("startTime") or 0, reverse=True)
    history = [r.get("status") for r in results][:10]
    return _run_row(results[0]), history


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


def _latest_skip_reason(node: dict) -> str | None:
    """The latest tick's SkipReason for a sensor (spec 016 — held issues / first-tick report)."""
    ticks = node.get("ticks") if isinstance(node, dict) else None
    if isinstance(ticks, list) and ticks and isinstance(ticks[0], dict):
        reason = ticks[0].get("skipReason")
        return reason or None
    return None


def _parse_schedules(data: dict, inst: list) -> dict:
    """{dagster_name: {running, id[, skip_reason]} | null} from the instigation aliases.

    A GitHub Projects sensor (spec 016) carries its latest tick's ``skip_reason`` — the held-issue
    report the Automation view surfaces (FR-025). Entries without a tick fragment omit the key."""
    schedules = {}
    for entry in inst:
        dname, alias = entry[0], entry[1]
        ctype = entry[2] if len(entry) > 2 else None
        node = data.get(alias)
        if isinstance(node, dict) and node.get("__typename") == "InstigationState":
            status = str(node.get("status") or "").upper()
            row = {"running": status == "RUNNING", "id": node.get("id")}
            if ctype == "project_status":
                row["skip_reason"] = _latest_skip_reason(node)
            schedules[dname] = row
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

    asset_runs = _results_of(data.get("asset_runs"))
    out = {}
    for name, meta in index:
        latest, history = _agent_runs(data, meta, asset_runs)
        out[name] = {
            "latest_run": latest,
            "history": history,
            "checks": _parse_checks(data.get(meta["checks"])) if meta["checks"] else None,
            "schedules": _parse_schedules(data, meta["inst"]),
        }
    return {"reachable": True, "agents": out}


# ── Runs-overview status normalisation (contract §D, research R8) ───────────
# One table folds Dagster RunStatus + the local report status into the presented set,
# and derives each presented status' tab bucket and run_status_tag intent. Read-path only:
# nothing here writes or mutates run data (constitution V).
_DAGSTER_PRESENT = {
    "SUCCESS": "succeeded",
    "FAILURE": "failed",
    "CANCELED": "cancelled",
    "CANCELING": "cancelled",
    "STARTED": "in_progress",
    "STARTING": "in_progress",
    "QUEUED": "queued",
    "NOT_STARTED": "queued",
}
_LOCAL_PRESENT = {
    "ok": "succeeded",
    "failed": "failed",
    "timeout": "timed_out",
    "running": "in_progress",
    "unknown": "unknown",
}
# Presented status → tab bucket. `unknown` maps to "" (counted under All only, never a
# sub-tab), so all ≥ in_progress + succeeded + failed (data-model, FR-005).
_TAB_OF_PRESENT = {
    "succeeded": "succeeded",
    "failed": "failed",
    "timed_out": "failed",
    "cancelled": "failed",
    "in_progress": "in_progress",
    "queued": "in_progress",
    "unknown": "",
}
# Presented status → run_status_tag intent (the tag's `status` arg). queued/unknown both
# render the neutral gray idle dot.
_INTENT_OF_PRESENT = {
    "succeeded": "success",
    "failed": "failure",
    "timed_out": "error",
    "cancelled": "error",
    "in_progress": "running",
    "queued": "queued",
    "unknown": "queued",
}
_LABEL_OF_PRESENT = {
    "succeeded": "succeeded",
    "failed": "failed",
    "timed_out": "timed out",
    "cancelled": "cancelled",
    "in_progress": "in progress",
    "queued": "queued",
    "unknown": "unknown",
}


def _present_status(dagster_status, local_status) -> str:
    """Fold a Dagster RunStatus (preferred, when known) + the local report status into the
    presented set {succeeded, failed, timed_out, cancelled, queued, in_progress, unknown}."""
    ds = str(dagster_status or "").upper()
    if ds in _DAGSTER_PRESENT:
        return _DAGSTER_PRESENT[ds]
    return _LOCAL_PRESENT.get(str(local_status or "").lower() or "unknown", "unknown")


def _status_tab(present: str) -> str:
    """The tab bucket for a presented status; `""` means All-only (not a sub-tab)."""
    return _TAB_OF_PRESENT.get(present, "")


def _status_intent(present: str) -> str:
    """The run_status_tag intent (`status` arg) for a presented status."""
    return _INTENT_OF_PRESENT.get(present, "queued")


def _status_label(present: str) -> str:
    """A human label for a presented status (e.g. `timed_out` → "timed out")."""
    return _LABEL_OF_PRESENT.get(present, present)


# ── Runs-overview enrichment read (contract §C, research R6) ────────────────
# One bounded, batched read of specific run ids → true status + Target + Launched by +
# Checks. Capped at N so a very large filtered history cannot make a single render
# unbounded (research R1); rows beyond the cap stay last-known. Every transport/parse/
# non-Runs arm collapses to plain data so the caller never sees an exception.
RUNS_STATUS_CAP = 500

_RUN_STATUS_FIELDS = (
    "runId status startTime endTime "
    "assetSelection { path } "
    "pipelineName "
    "tags { key value }"
)

# Per-run Checks come from a SECOND read: a Run only carries check *handles* (name + assetKey),
# never their execution status, so the status lives on the AssetNode. This sub-selection mirrors
# the Agents-overview read (contract §C) but also pulls the execution's `runId` so each check
# attaches to the exact run that produced the latest materialization — older runs of the same
# asset correctly show `—` rather than borrowing the newest run's result.
# spec 017 R5: additive selection of each execution's timestamp + one-line detail (evaluation
# description → severity) so the run-detail Checks section can show a recorded time and detail.
# Additive/best-effort — absent fields degrade to "—" and every failure arm still collapses to {}.
_ASSET_CHECKS_SUBQUERY = (
    "{ __typename ... on AssetNode { assetChecksOrError { __typename "
    "... on AssetChecks { checks { name executionForLatestMaterialization "
    "{ runId status timestamp evaluation { severity description } } } } } } }"
)


def _check_detail(execution: dict) -> str:
    """One-line detail for a check row (spec 017): evaluation description → severity → "—"."""
    evaluation = execution.get("evaluation") if isinstance(execution, dict) else None
    evaluation = evaluation or {}
    return evaluation.get("description") or evaluation.get("severity") or "—"


def _check_recorded(execution: dict) -> str:
    """Recorded time for a check row (spec 017), or "—" when the timestamp is absent."""
    ts = execution.get("timestamp") if isinstance(execution, dict) else None
    if not ts:
        return "—"
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%b %-d, %-I:%M %p")
    except (OverflowError, OSError, ValueError, TypeError):
        return "—"


def _run_target(run: dict):
    """Target for a run: the asset key (`a/b`) when it materialised one, else the job name."""
    for sel in run.get("assetSelection") or []:
        if isinstance(sel, dict) and sel.get("path"):
            return "/".join(sel["path"])
    return run.get("pipelineName") or None


def _run_launched_by(tags) -> dict:
    """Launched-by from run tags: dagster/schedule_name → schedule, sensor_name → sensor,
    else a manual launch (data-model)."""
    by = {}
    for t in tags or []:
        if isinstance(t, dict):
            by[t.get("key")] = t.get("value")
    if by.get("dagster/schedule_name"):
        return {"kind": "schedule", "name": by["dagster/schedule_name"]}
    if by.get("dagster/sensor_name"):
        return {"kind": "sensor", "name": by["dagster/sensor_name"]}
    return {"kind": "manual", "name": None}


async def _run_checks_by_id(asset_keys: list[list[str]]) -> dict:
    """Second bounded read: for each distinct asset key among the enriched runs, the latest
    check executions grouped by the run that produced them → ``{run_id: [{name, status}]}``.
    One GraphQL POST (aliased per distinct key); every transport/parse/non-``AssetChecks`` arm
    collapses to ``{}`` so Checks simply degrade to ``—`` and never break status/target/launched-by."""
    seen: list[list[str]] = []
    for k in asset_keys:
        if k and k not in seen:
            seen.append(k)
    if not seen:
        return {}
    fields = []
    for i, path in enumerate(seen):
        p = ", ".join(_q(s) for s in path)
        fields.append(f"c{i}: assetNodeOrError(assetKey: {{path: [{p}]}}) {_ASSET_CHECKS_SUBQUERY}")
    query = "query {\n" + "\n".join(fields) + "\n}"
    url = f"{config.DAGSTER_URL}/graphql"
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(url, json={"query": query})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return {}
    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        return {}
    by_run: dict[str, list] = {}
    for i in range(len(seen)):
        node = data.get(f"c{i}")
        if not isinstance(node, dict):
            continue
        checks_or_error = node.get("assetChecksOrError")
        if not isinstance(checks_or_error, dict) or "checks" not in checks_or_error:
            continue
        for c in checks_or_error.get("checks") or []:
            ex = c.get("executionForLatestMaterialization")
            if not isinstance(ex, dict):
                continue
            rid = ex.get("runId")
            if not rid:
                continue
            by_run.setdefault(rid, []).append({
                "name": c.get("name"),
                "status": _check_status(ex),
                "detail": _check_detail(ex),
                "recorded": _check_recorded(ex),
            })
    return by_run


async def run_status(run_ids: list[str]) -> dict:
    """One bounded, batched read of specific run ids → status/target/launched-by, plus a second
    bounded read for per-run Checks (contract §C, research R6). Returns the *Enrichment payload*
    ``{"reachable": bool, "runs": {run_id: {...}}}``. The first POST fetches run status/target/
    launched-by; a second POST (see ``_run_checks_by_id``) resolves Checks, which live on the
    AssetNode rather than the Run. Every transport/parse/non-``Runs`` arm of the first read
    collapses to ``{"reachable": False, "runs": {}}`` so the caller falls back to last-known for
    every row; a failed second read only degrades Checks to ``—``. A requested id absent from the
    results is simply omitted (the caller treats it as last-known)."""
    ids = [r for r in (run_ids or []) if r][:RUNS_STATUS_CAP]
    if not ids:
        return {"reachable": True, "runs": {}}
    id_list = ", ".join(_q(r) for r in ids)
    query = (
        "query { runsOrError(filter: {runIds: [" + id_list + "]}, limit: "
        + str(RUNS_STATUS_CAP) + ") { __typename ... on Runs { results { "
        + _RUN_STATUS_FIELDS + " } } } }"
    )
    url = f"{config.DAGSTER_URL}/graphql"
    try:
        async with httpx.AsyncClient(timeout=config.RELOAD_TIMEOUT_S) as client:
            resp = await client.post(url, json={"query": query})
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"reachable": False, "runs": {}}

    data = (payload or {}).get("data")
    if not isinstance(data, dict):
        return {"reachable": False, "runs": {}}
    node = data.get("runsOrError")
    if not isinstance(node, dict) or node.get("__typename") != "Runs" or "results" not in node:
        # A PythonError / non-Runs arm, or top-level errors: degrade rather than fabricate.
        return {"reachable": False, "runs": {}}

    out = {}
    asset_keys = []
    for r in node.get("results") or []:
        rid = r.get("runId")
        if not rid:
            continue
        out[rid] = {
            "status": r.get("status"),
            "start_time": r.get("startTime"),
            "end_time": r.get("endTime"),
            "target": _run_target(r),
            "launched_by": _run_launched_by(r.get("tags")),
            "checks": None,
        }
        for sel in r.get("assetSelection") or []:
            if isinstance(sel, dict) and sel.get("path"):
                asset_keys.append(sel["path"])
    # Second bounded read: resolve per-run Checks off the AssetNode and attach by run id.
    checks_by_id = await _run_checks_by_id(asset_keys)
    for rid, checks in checks_by_id.items():
        if rid in out:
            out[rid]["checks"] = checks or None
    return {"reachable": True, "runs": out}


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
