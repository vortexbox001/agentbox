"""
Dagster entry point — auto-discovers agent YAML files and registers them as jobs.

Each YAML in /opt/agentbox/agents/ becomes a Dagster job that launches an
ephemeral Docker container via factory.build_job_and_schedule(). Agents with
a cron schedule also get a ScheduleDefinition so Dagster can trigger them
automatically.

Files with enabled: false are skipped (useful for templates and disabled agents).
"""

import glob, yaml
from dagster import Definitions
from factory import build_job_and_schedule

jobs, schedules = [], []

# Auto-discover every agent YAML and register a job (+ optional schedule) for each.
for path in sorted(glob.glob("/opt/agentbox/agents/*.yaml")):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not cfg or not cfg.get("enabled", True):
        continue
    job_, sched = build_job_and_schedule(cfg)
    jobs.append(job_)
    if sched:
        schedules.append(sched)

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

defs = Definitions(jobs=jobs, schedules=schedules)
