"""
Dagster entry point — auto-discovers agent YAML files and registers each as the
Dagster definitions its explicitly-declared nature calls for (spec 006).

An agent's nature is now EXPLICIT, not inferred (spec 006 replaces spec 004's
produces-presence inference). Each enabled agent carries two independent flags:

  * **asset** — a valid ``produces`` block ⇒ a tracked Dagster asset.
  * **job**   — ``job: true`` ⇒ a Dagster job ``agent_<name>``.

At least one must be set. The three kinds route as:

  * asset-only ⇒ ``build_asset`` (materialize by hand / on its schedule); no job.
  * job-only   ⇒ ``build_job`` (a plain op job ``agent_<name>``); no asset.
  * both       ⇒ ``build_asset`` PLUS ``build_materializing_job`` — ``agent_<name>``
                 becomes the asset's materializing job, so every run records against
                 the one asset (FR-006).

*When* an agent runs lives on the agent too, in a ``triggers:`` block:

  * ``asset_schedule`` (asset kind) ⇒ ``AutomationCondition.on_cron`` on the asset
    plus a paused per-asset sensor ``autocond_<name>``.
  * ``job_schedule`` (job kind) ⇒ a ``ScheduleDefinition`` ``sched_<name>`` on the
    agent's job (plain or materializing). A new schedule starts paused; the unchanged
    ``sched_<name>`` / ``autocond_<name>`` names let Dagster preserve each trigger's
    prior on/off state across a reload (FR-012/FR-014).

Spec 005's standalone trigger directory, its on-demand keyword, and its
``migrate-schedules.py`` are retired: there is NO separate trigger store to load here.

Files with ``enabled: false`` are skipped. A file with an invalid/conflicting
``produces`` block, or one that is neither an asset nor a job, is rejected by name and
skipped; every other agent still loads (FR-010).
"""

import glob, os, logging, yaml
from dagster import Definitions
import paths
import factory
from factory import (
    build_job, build_schedule, build_asset, build_materializing_job,
    build_asset_automation_sensor, validate_asset_key, validate_checks, validate_depends_on,
    partition_on_cron_supported, build_prune_job, build_prune_schedule, RejectAgent,
)

log = logging.getLogger("agentbox.definitions")

# Agent YAMLs live under the config root (FR-002); derived from the single resolution point.
AGENTS_GLOB = paths.AGENTS_GLOB


def _triggers(cfg: dict) -> tuple[str | None, str | None]:
    """Read ``(asset_schedule, job_schedule)`` off an agent's ``triggers`` block.

    An absent block, a non-mapping block, or a blank value yields ``None`` for that
    schedule (no trigger of that kind). Triggering is read ONLY from here (FR-009).
    """
    block = cfg.get("triggers")
    if not isinstance(block, dict):
        return None, None
    asset_schedule = block.get("asset_schedule") or None
    job_schedule = block.get("job_schedule") or None
    return (
        asset_schedule if isinstance(asset_schedule, str) and asset_schedule.strip() else None,
        job_schedule if isinstance(job_schedule, str) and job_schedule.strip() else None,
    )


def _event_triggers(cfg: dict) -> tuple[bool, bool]:
    """Read ``(on_upstream, on_missing)`` off an agent's ``triggers`` block (spec 013, FR-004/008).

    The two asset-kind event triggers default false (absent ⇒ off); only a value of ``True``
    enables one. An absent or non-mapping ``triggers`` block yields both off.
    """
    block = cfg.get("triggers")
    if not isinstance(block, dict):
        return False, False
    return block.get("on_upstream") is True, block.get("on_missing") is True


def _detect_cycles(graph: dict[str, list[str]]) -> tuple[set[str], list[list[str]]]:
    """DFS over the asset-key graph; return (keys on any cycle, the cycle paths for logging).

    A cycle path names its assets joined by ``->`` (e.g. ``b/x -> c/y -> b/x``). Only edges whose
    target is itself a produced key are followed — dangling edges are handled separately. Self-loops
    (an asset depending on itself) are reported as a length-1 cycle.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}
    on_cycle: set[str] = set()
    cycles: list[list[str]] = []
    stack: list[str] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        stack.append(u)
        for v in graph.get(u, []):
            if v not in graph:
                continue  # dangling — handled by the dangling pass, not a cycle
            if color[v] == GRAY:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
                on_cycle.update(stack[i:])
            elif color[v] == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for k in graph:
        if color[k] == WHITE:
            dfs(k)
    return on_cycle, cycles


def _reject_bad_graph(pending_assets: list[tuple], rejected_files: set) -> None:
    """Reject dangling-ref and cyclic assets (and their dependents) in-place (spec 013 §4).

    Builds the asset-key graph from every surviving pending asset's ``depends_on``, then: (1) rejects
    any asset naming an unknown upstream key (naming the key); (2) rejects every asset on a cycle
    (naming the assets); (3) cascades to a fixpoint so an asset whose upstream was rejected is
    rejected too. Rejected assets are added to ``rejected_files`` so their asset def, sensor, and job
    are skipped — no automation runs against a bad graph. Every unrelated asset still loads.
    """
    surviving = [
        (file, cfg, list(depends_on))
        for (file, name, cfg, asset_def, a_s, j_s, is_job, on_up, on_mi, depends_on) in pending_assets
        if file not in rejected_files
    ]
    produced = {cfg["produces"]["asset"] for (file, cfg, deps) in surviving}
    file_by_key = {cfg["produces"]["asset"]: file for (file, cfg, deps) in surviving}
    deps_by_key = {cfg["produces"]["asset"]: deps for (file, cfg, deps) in surviving}

    rejected_keys: set[str] = set()

    # 1) Dangling references: an upstream key produced by no surviving asset (FR-002 / US4 #3).
    for key, deps in deps_by_key.items():
        for dep in deps:
            if dep not in produced:
                log.warning("%s: depends_on names unknown asset key %r", file_by_key[key], dep)
                rejected_keys.add(key)

    # 2) Cycles: every asset on a cycle, naming the assets in it (FR-003 / US4 #1).
    on_cycle, cycles = _detect_cycles(deps_by_key)
    for cycle in cycles:
        log.warning("dependency cycle: %s", " -> ".join(cycle))
    rejected_keys |= on_cycle

    # 3) Cascade to a fixpoint: an asset whose upstream was rejected now dangles ⇒ reject too.
    changed = True
    while changed:
        changed = False
        for key, deps in deps_by_key.items():
            if key in rejected_keys:
                continue
            bad = next((d for d in deps if d in rejected_keys), None)
            if bad is not None:
                log.warning("%s: depends_on upstream %r was rejected — cascading rejection",
                            file_by_key[key], bad)
                rejected_keys.add(key)
                changed = True

    for key in rejected_keys:
        rejected_files.add(file_by_key[key])


def discover(agents_glob: str = AGENTS_GLOB) -> dict:
    """Load every enabled agent, classify its nature, and wire it and its triggers.

    Returns ``{"jobs": [...], "schedules": [...], "assets": [...], "sensors": [...]}``. Each
    agent file is built inside a try/except so one bad file (invalid ``produces``, or neither
    asset nor job) costs only itself and is logged by name (FR-010); every other agent loads.
    """
    jobs, schedules, assets, sensors = [], [], [], []
    # (file, name, cfg, asset_def, asset_schedule, job_schedule) — assets are collected first so
    # duplicate keys can be rejected before their sensors / materializing jobs are added.
    pending_assets: list[tuple] = []
    files_by_key: dict[str, list[str]] = {}

    for path in sorted(glob.glob(agents_glob)):
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if not cfg:
            continue
        name = cfg.get("name")
        if not cfg.get("enabled", True):
            continue
        file = "agents/" + os.path.basename(path)
        asset_schedule, job_schedule = _triggers(cfg)
        on_upstream, on_missing = _event_triggers(cfg)
        try:
            # produces.checks are rejected here — without a valid asset, or malformed — before
            # any nature routing, so one bad checks file is skipped by name (FR-010, contract §6).
            validate_checks(cfg, file)
            is_asset = "produces" in cfg
            is_job = cfg.get("job") is True
            if not is_asset and not is_job:
                raise RejectAgent(
                    file,
                    "agent is neither an asset nor a job — declare a `produces` block, set "
                    "`job: true`, or both (FR-005)",
                )
            if is_asset:
                asset_key = validate_asset_key(cfg, file)  # raises RejectAgent, naming the file
                # depends_on shape backstop (spec 013, contract §5); existence + acyclicity are
                # enforced across all agents below once every produced key is known.
                depends_on = validate_depends_on(cfg, file)
                asset_def = build_asset(cfg, file, cron=asset_schedule, depends_on=depends_on,
                                        on_upstream=on_upstream, on_missing=on_missing)
                pending_assets.append((file, name, cfg, asset_def, asset_schedule, job_schedule,
                                       is_job, on_upstream, on_missing, depends_on))
                files_by_key.setdefault(asset_key, []).append(file)
            else:
                # Job-only: a plain op job, optionally scheduled by its own job_schedule.
                job_def = build_job(cfg)
                jobs.append(job_def)
                if job_schedule:
                    schedules.append(build_schedule(job_def, job_schedule))
        except RejectAgent as e:
            log.warning("skipping %s", e)
            continue

    # Reject every file that shares an asset key with another (FR-010); load everything else.
    dup_keys = {key: files for key, files in files_by_key.items() if len(files) > 1}
    rejected_files = {f for files in dup_keys.values() for f in files}
    for key, files in dup_keys.items():
        log.warning('asset key "%s" declared by %s — all rejected', key, ", ".join(files))

    # Dependency graph: reject dangling refs + cycles at load, before any automation runs (spec 013
    # §4 / FR-002/FR-003 / US4). Only assets that survived the duplicate-key check participate; the
    # offending assets (and any that transitively depend on them) are skipped and named, while every
    # unrelated agent still loads (the resilient skip-and-log loader, R5).
    _reject_bad_graph(pending_assets, rejected_files)

    for (file, name, cfg, asset_def, asset_schedule, job_schedule, is_job,
         on_upstream, on_missing, depends_on) in pending_assets:
        if file in rejected_files:
            continue
        assets.append(asset_def)
        partition = (cfg.get("produces") or {}).get("partition", "none")
        partitioned = partition == "daily"

        # Partition Null-Action fallback (FR-015): when `on_cron` cannot target the correct
        # partition on the installed Dagster, drive the schedule from a partition-filling job
        # on the asset's materializing job instead of the on_cron sensor.
        fallback = (
            bool(asset_schedule) and partitioned and not partition_on_cron_supported()
        )

        # The paused per-asset autocond sensor is created whenever ANY asset-kind trigger drives a
        # sensor-run automation condition (spec 013, R4) — asset_schedule (outside the on_cron
        # partition fallback), on_upstream, or on_missing. `factory` owns the gate predicate; here
        # we only decide whether to call build_asset_automation_sensor. In the on_cron fallback the
        # cron is driven by a schedule, not the sensor, so it does not count toward the gate.
        sensor_cron = None if fallback else asset_schedule
        if factory.asset_has_automation_condition(
            {"name": name}, cron=sensor_cron, on_upstream=on_upstream, on_missing=on_missing,
            partitioned=partitioned,
        ):
            sensors.append(build_asset_automation_sensor({"name": name}, asset_def))

        # A both-kind agent has agent_<name> as its materializing job; the fallback also needs
        # such a job (defining one for an asset-only agent) to carry the partition-filling schedule.
        materializing_job = None
        if is_job or fallback:
            materializing_job = build_materializing_job(cfg, asset_def)
            jobs.append(materializing_job)

        if is_job and job_schedule:
            schedules.append(build_schedule(materializing_job, job_schedule))

        if fallback:
            log.warning(
                "%s: on_cron cannot target the daily partition of asset %s on this Dagster — "
                "falling back to a partition-filling schedule sched_%s on its materializing job "
                "(FR-015)",
                file, cfg["produces"]["asset"], name.replace("-", "_"),
            )
            schedules.append(build_schedule(materializing_job, asset_schedule))

    return {"jobs": jobs, "schedules": schedules, "assets": assets, "sensors": sensors}


_discovered = discover()
jobs = _discovered["jobs"]
schedules = _discovered["schedules"]
assets = _discovered["assets"]
sensors = _discovered["sensors"]

# Nightly run-retention prune job (spec 012 US5): generic infrastructure, not per-agent code.
# A no-op under the default keep_forever policy; the Settings page's retention block drives it.
_prune_job = build_prune_job()
jobs.append(_prune_job)
schedules.append(build_prune_schedule(_prune_job))

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
#         ["find", paths.OUTPUTS_ROOT, "-type", "f", "-mtime", "+30", "-delete"],
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
