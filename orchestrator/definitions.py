"""
Dagster entry point — auto-discovers agent YAML files and registers each as a
Dagster job or, when the file declares a `produces` block, a Dagster asset.

Each YAML in /opt/agentbox/agents/ becomes either a job that launches an ephemeral
Docker container via factory.build_job_and_schedule() (with a ScheduleDefinition if
it sets a cron schedule), or — when it carries `produces` — an asset built by
factory.build_asset() that materializes via the SAME container launch.

Files with enabled: false are skipped (useful for templates and disabled agents).
A file with an invalid or conflicting `produces` block is rejected by name and
skipped; every other agent still loads (FR-012/FR-019).
"""

import glob, os, logging, yaml
from dagster import Definitions
from factory import build_job_and_schedule, build_asset, validate_asset_key, RejectAgent

log = logging.getLogger("agentbox.definitions")

AGENTS_GLOB = "/opt/agentbox/agents/*.yaml"


def discover(agents_glob: str = AGENTS_GLOB) -> dict:
    """Load every enabled agent file and route it to a job or an asset.

    Returns ``{"jobs": [...], "schedules": [...], "assets": [...]}``. Each file is
    built inside a try/except so one bad file (invalid `produces` block) costs only
    itself: it is logged by name and skipped, and every other agent still loads
    (FR-012). After per-file validation, any asset key declared by two or more files
    has all of those files rejected by name (FR-019) and everything else loads.
    """
    jobs, schedules, assets = [], [], []
    pending_assets: list[tuple[str, object]] = []  # (file, asset_def)
    files_by_key: dict[str, list[str]] = {}

    for path in sorted(glob.glob(agents_glob)):
        with open(path) as f:
            cfg = yaml.safe_load(f)
        if not cfg or not cfg.get("enabled", True):
            continue
        file = "agents/" + os.path.basename(path)
        try:
            if "produces" in cfg:
                asset_key = validate_asset_key(cfg, file)  # raises RejectAgent, naming the file
                pending_assets.append((file, build_asset(cfg, file)))
                files_by_key.setdefault(asset_key, []).append(file)
            else:
                job_, sched = build_job_and_schedule(cfg)
                jobs.append(job_)
                if sched:
                    schedules.append(sched)
        except RejectAgent as e:
            log.warning("skipping %s", e)
            continue

    # Reject every file that shares an asset key with another (FR-019): Dagster refuses a
    # Definitions carrying two assets under one key, so turn the conflict into a file-naming
    # operator message and load everything else. Keys declared by exactly one file are kept.
    dup_keys = {key: files for key, files in files_by_key.items() if len(files) > 1}
    rejected_files = {f for files in dup_keys.values() for f in files}
    for key, files in dup_keys.items():
        log.warning('asset key "%s" declared by %s — all rejected', key, ", ".join(files))
    for file, asset_def in pending_assets:
        if file not in rejected_files:
            assets.append(asset_def)

    return {"jobs": jobs, "schedules": schedules, "assets": assets}


_discovered = discover()
jobs = _discovered["jobs"]
schedules = _discovered["schedules"]
assets = _discovered["assets"]

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

defs = Definitions(jobs=jobs, schedules=schedules, assets=assets)
