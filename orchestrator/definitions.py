"""
Dagster entry point — auto-discovers agent YAML files and registers each as a
Dagster job or, when the file declares a `produces` block, a Dagster asset.

Each YAML in /opt/agentbox/agents/ becomes either a job that launches an ephemeral
Docker container via factory.build_job() (spec 005), or — when it carries `produces` —
an asset built by factory.build_asset() that materializes via the SAME container launch.

*When* an agent runs is a separate concern (spec 005): triggering is read from
/opt/agentbox/automation/*.yaml — maps keyed by agent name, each value a `cron` or
`on_demand` trigger. A job-mode agent's cron becomes a ScheduleDefinition; an asset-mode
agent's cron becomes an AutomationCondition.on_cron on the asset plus a per-asset
automation sensor. An agent with no entry is on-demand.

Files with enabled: false are skipped (useful for templates and disabled agents).
A file with an invalid or conflicting `produces` block is rejected by name and skipped;
every other agent still loads (FR-012/FR-019). An automation entry naming an agent that
does not exist, or a duplicate/invalid trigger, FAILS the reload with a naming message
(FR-009/FR-010/FR-011).
"""

import glob, os, logging, yaml
from dagster import Definitions
from factory import (
    build_job, build_schedule, build_asset, build_asset_automation_sensor,
    validate_asset_key, is_valid_cron, RejectAgent,
)

log = logging.getLogger("agentbox.definitions")

AGENTS_GLOB = "/opt/agentbox/agents/*.yaml"
AUTOMATION_GLOB = "/opt/agentbox/automation/*.yaml"


class RejectAutomation(Exception):
    """An automation file/entry is invalid; the message names the offending entry and file.

    Unlike a bad `produces` block (which skips one agent, FR-012), a bad automation entry
    FAILS the whole reload (FR-009/FR-010/FR-011) — the management UI already refuses to
    write one, so its only source is a hand-edit the operator should hear about loudly.
    """


def load_automation(glob_pattern: str = AUTOMATION_GLOB):
    """Read and merge automation/*.yaml into a normalized trigger map.

    Returns ``(triggers, sources)`` where ``triggers`` maps an agent name to
    ``{"cron": str}`` or ``{"on_demand": True}`` and ``sources`` maps an agent name to the
    file its entry came from (for naming messages). Applies SYNTACTIC validation (contract
    automation-format §3): duplicate key across files (FR-011), both/invalid triggers
    (FR-005/FR-009). An entry with neither trigger degrades to on-demand. The semantic
    unknown-agent check (FR-010) happens in ``discover`` where agent names are known.
    """
    triggers: dict[str, dict] = {}
    sources: dict[str, str] = {}

    for path in sorted(glob.glob(glob_pattern)):
        file = "automation/" + os.path.basename(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data:
            continue
        if not isinstance(data, dict):
            raise RejectAutomation(f"{file}: top level must be a map keyed by agent name")
        for name, value in data.items():
            if name in sources:
                raise RejectAutomation(
                    f'automation entry "{name}" is declared by both {sources[name]} and {file} '
                    f"(FR-011) — an agent may have at most one trigger"
                )
            trigger = _normalize_trigger(name, value, file)
            if trigger is not None:  # None == on-demand; only cron entries are stored
                triggers[name] = trigger
            sources[name] = file
    return triggers, sources


def _normalize_trigger(name: str, value, file: str):
    """One entry's value → ``{"cron": str}`` (stored) or ``None`` (on-demand). Raises on invalid."""
    if value is None:
        return None  # `agent:` with no value == on-demand
    if not isinstance(value, dict):
        raise RejectAutomation(f'{file}: automation entry "{name}" must be a map with one trigger')
    has_cron = "cron" in value and value.get("cron") not in (None, "")
    has_on_demand = bool(value.get("on_demand"))
    if has_cron and has_on_demand:
        raise RejectAutomation(
            f'{file}: automation entry "{name}" declares both cron and on_demand — pick one (FR-005)'
        )
    if has_cron:
        cron = value["cron"]
        if not is_valid_cron(cron):
            raise RejectAutomation(
                f'{file}: automation entry "{name}" has invalid cron "{cron}" — '
                f"five fields, no @-macros (FR-009)"
            )
        return {"cron": str(cron)}
    return None  # on_demand: true, or neither key → on-demand


def discover(agents_glob: str = AGENTS_GLOB, automation_glob: str = AUTOMATION_GLOB) -> dict:
    """Load every enabled agent, read triggers from automation/, and wire them.

    Returns ``{"jobs": [...], "schedules": [...], "assets": [...], "sensors": [...]}``. Each
    agent file is built inside a try/except so one bad `produces` block costs only itself
    (FR-012). Automation errors (dup/invalid/unknown entry) fail the whole reload by design.
    """
    jobs, schedules, assets, sensors = [], [], [], []
    # (file, name, asset_def, cron) — assets are collected first so duplicate keys can be
    # rejected before their sensors are added (FR-019).
    pending_assets: list[tuple[str, str, object, str | None]] = []
    files_by_key: dict[str, list[str]] = {}
    known_names: set[str] = set()

    triggers, sources = load_automation(automation_glob)

    for path in sorted(glob.glob(agents_glob)):
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if not cfg:
            continue
        name = cfg.get("name")
        if name:
            known_names.add(name)  # every agent file, incl. disabled/templates (FR-010, contract §3)
        if not cfg.get("enabled", True):
            continue
        file = "agents/" + os.path.basename(path)
        if "schedule" in cfg:  # stray key after the migration; ignore it, warn by name (FR-002/R7)
            log.warning("%s still carries a `schedule` key — ignored; triggering comes from automation/", file)
        cron = triggers.get(name, {}).get("cron")
        try:
            if "produces" in cfg:
                asset_key = validate_asset_key(cfg, file)  # raises RejectAgent, naming the file
                asset_def = build_asset(cfg, file, cron=cron)
                pending_assets.append((file, name, asset_def, cron))
                files_by_key.setdefault(asset_key, []).append(file)
            else:
                job_def = build_job(cfg)
                jobs.append(job_def)
                if cron:
                    schedules.append(build_schedule(job_def, cron))
        except RejectAgent as e:
            log.warning("skipping %s", e)
            continue

    # Every automation entry must name a known agent (FR-010) — fail the reload if not.
    for entry_name, entry_file in sources.items():
        if entry_name not in known_names:
            raise RejectAutomation(
                f'{entry_file}: automation entry "{entry_name}" names no agent — '
                f"no agents/*.yaml declares that name (FR-010)"
            )

    # Reject every file that shares an asset key with another (FR-019); load everything else.
    dup_keys = {key: files for key, files in files_by_key.items() if len(files) > 1}
    rejected_files = {f for files in dup_keys.values() for f in files}
    for key, files in dup_keys.items():
        log.warning('asset key "%s" declared by %s — all rejected', key, ", ".join(files))
    for file, name, asset_def, cron in pending_assets:
        if file in rejected_files:
            continue
        assets.append(asset_def)
        if cron:  # an asset-mode agent with a cron gets a paused per-asset automation sensor (FR-021)
            sensors.append(build_asset_automation_sensor({"name": name}, asset_def))

    return {"jobs": jobs, "schedules": schedules, "assets": assets, "sensors": sensors}


_discovered = discover()
jobs = _discovered["jobs"]
schedules = _discovered["schedules"]
assets = _discovered["assets"]
sensors = _discovered["sensors"]

# --- Manual job definitions ---
# You can define non-agent Dagster jobs here alongside the auto-discovered ones.
#
# from dagster import job, op, ScheduleDefinition
#
# @op
# def cleanup_old_outputs(context):
#     """Remove agent output files older than 30 days."""
#     import subprocess
#     subprocess.run(
#         ["find", "/data/outputs", "-type", "f", "-mtime", "+30", "-delete"],
#         check=True,
#     )
#     context.log.info("Cleaned up old output files")
#
# @job
# def maintenance_cleanup():
#     cleanup_old_outputs()
#
# jobs.append(maintenance_cleanup)
# schedules.append(ScheduleDefinition(
#     job=maintenance_cleanup,
#     cron_schedule="0 4 * * 0",  # Sundays at 4am
#     name="sched_maintenance_cleanup",
# ))

defs = Definitions(jobs=jobs, schedules=schedules, assets=assets, sensors=sensors)
