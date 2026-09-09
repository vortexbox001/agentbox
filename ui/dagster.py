"""Thin async client for the Dagster webserver's GraphQL endpoint.

Reload triggers a workspace reload so a newly saved/deleted agent shows up as a
job; status backs the sidebar health block. Both map transport and Dagster-side
failures onto plain data so callers never see an exception from a reachable-or-not
Dagster: the file operation always succeeds or fails on its own.
"""
from __future__ import annotations

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
