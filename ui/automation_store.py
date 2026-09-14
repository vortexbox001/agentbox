"""Read, validate, and write per-agent triggers for the Automation view (spec 006).

Spec 005 kept agent triggering in a standalone trigger directory; spec 006 folds it
back ONTO each agent's ``triggers:`` block. So this module now reads triggers off every agent
file (``per_agent_view``) and writes edits straight onto ``agents/*.yaml`` via ``agents_store``
(``write``) — there is no separate trigger store any more.

Each agent contributes one row per kind its nature entitles it to: an ``asset`` row (asset
kind) and/or a ``job`` row (job kind), grouped as one unit. Each schedule is editable
on-demand ↔ cron independently. The five-field cron rule is duplicated from the orchestrator
deliberately (research R6) and pinned to it by a shared test; the partition Null-Action
``fallback`` marker is computed the same way the orchestrator wires it.
"""
from __future__ import annotations

import glob
import os

import yaml

import config
import agents_store


class AutomationError(Exception):
    """A rejected automation edit; ``field`` names the offending agent for the UI."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


def is_valid_cron(value) -> bool:
    """Five fields, no @-macros — the trigger cron rule (contract agent-model §3).

    Twin of ``orchestrator/factory.py:is_valid_cron`` (separate containers, no shared import);
    this UI copy additionally runs ``croniter.is_valid`` as the stricter authoring guard.
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s or s.startswith("@"):
        return False
    if len(s.split()) != 5:
        return False
    from croniter import croniter
    return croniter.is_valid(s)


def partition_on_cron_supported() -> bool:
    """Whether ``on_cron`` can target the right partition on the installed Dagster.

    Twin of ``orchestrator/factory.py:partition_on_cron_supported`` so the Automation page's
    ``fallback`` marker agrees with what the orchestrator actually wired (FR-015). Primary path
    by default; ``AGENTBOX_PARTITION_FALLBACK=1`` forces the documented fallback.
    """
    return os.environ.get("AGENTBOX_PARTITION_FALLBACK", "").lower() not in ("1", "true", "yes")


def known_agent_names() -> set[str]:
    """Every agent name from agents/*.yaml — disabled included (contract §3).

    Templates live in the product examples tree now (R7), not the instance agents dir, so
    none are expected here; a stray ``_``-prefixed file (e.g. one a fresh-install copied in)
    is skipped so a trigger can never target it — mirroring ``per_agent_view``.
    """
    names: set[str] = set()
    for path in glob.glob(os.path.join(config.AGENTS_DIR, "*.yaml")):
        if os.path.basename(path).startswith("_"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(cfg, dict) and cfg.get("name"):
            names.add(cfg["name"])
    return names


def _kinds_and_schedules(agent: dict) -> tuple[list[str], list[dict]]:
    """The kind(s) an agent's nature entitles it to and one schedule row per kind."""
    is_asset = bool(agent.get("asset"))
    is_job = agent.get("job") is True
    kinds: list[str] = []
    schedules: list[dict] = []
    if is_asset:
        kinds.append("asset")
        cron = agent.get("asset_schedule") or None
        partition = agent.get("partition") or "none"
        fallback = bool(cron) and partition == "daily" and not partition_on_cron_supported()
        schedules.append({"kind": "asset", "cron": cron, "fallback": fallback})
    if is_job:
        kinds.append("job")
        schedules.append({"kind": "job", "cron": agent.get("job_schedule") or None, "fallback": False})
    return kinds, schedules


def per_agent_view() -> list[dict]:
    """One row per NON-template agent (disabled included) with its per-kind schedule rows.

    Each row: ``{name, harness, enabled, kinds, schedules:[{kind, cron, fallback}]}`` — ``cron``
    is null when that schedule is on-demand, and ``fallback`` marks an asset row whose partition
    ``on_cron`` fell back to a job schedule (contract ui-automation §2).
    """
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(config.AGENTS_DIR, "*.yaml"))):
        stem = os.path.basename(path)[:-5]
        if stem.startswith("_"):
            continue  # defensive: templates live in the examples tree now (R7), not here
        info = agents_store.read_agent(stem)
        agent = info.get("agent") or {}
        kinds, schedules = _kinds_and_schedules(agent)
        rows.append({
            "name": info.get("name") or stem,
            "harness": agent.get("harness"),
            # `enabled` controls whether Dagster registers the agent at all — a disabled agent's
            # trigger is inert until it is enabled (surfaced as a badge in the view). Default True.
            "enabled": agent.get("enabled", True) is not False,
            "kinds": kinds,
            "schedules": schedules,
        })
    return rows


def validate(triggers: dict, known: set[str] | None = None) -> None:
    """Validate an incoming per-agent trigger set before writing (contract ui-automation §2).

    ``triggers`` maps an agent name to ``{"asset_schedule"?, "job_schedule"?}`` where each value
    is a cron string or null (on-demand). Rejects an unknown agent, an invalid cron, or a
    schedule set for a kind the agent does not have — naming the offending agent. Raises
    AutomationError.
    """
    known = known_agent_names() if known is None else known
    for name, spec in triggers.items():
        if name not in known:
            raise AutomationError(f'"{name}" names no agent — no agents/*.yaml declares it', field=name)
        if not isinstance(spec, dict):
            raise AutomationError(f'{name}: trigger must be a map of asset_schedule/job_schedule', field=name)
        agent = agents_store.read_agent(name).get("agent") or {}
        is_asset = bool(agent.get("asset"))
        is_job = agent.get("job") is True
        for key, kind_on, kind_msg in (
            ("asset_schedule", is_asset, "asset_schedule applies only when the agent is an asset"),
            ("job_schedule", is_job, "job_schedule applies only when the agent has a job"),
        ):
            if key not in spec:
                continue
            cron = spec[key]
            if cron in (None, ""):
                continue  # clearing a schedule (on-demand) is always allowed
            if not kind_on:
                raise AutomationError(f"{name}: {kind_msg}", field=name)
            if not is_valid_cron(cron):
                raise AutomationError(
                    f'{name}: invalid cron "{cron}" — five fields, no @-macros', field=name,
                )


def write(triggers: dict) -> list[str]:
    """Write each per-agent trigger edit ONTO its agent file via ``agents_store`` (FR-020).

    Only the keys present in each agent's spec are changed; a cron sets the schedule, a null/blank
    clears it (on-demand). The other schedule and every other field are left untouched. Returns
    the names of the agents whose files were rewritten.
    """
    written: list[str] = []
    for name, spec in triggers.items():
        info = agents_store.read_agent(name)
        agent = dict(info.get("agent") or {})
        for key in ("asset_schedule", "job_schedule"):
            if key not in spec:
                continue
            value = spec[key]
            if value in (None, ""):
                agent.pop(key, None)
            else:
                agent[key] = value
        agents_store.write_agent(name, agent)
        written.append(name)
    return written
