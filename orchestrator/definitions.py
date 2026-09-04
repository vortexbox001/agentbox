import glob, yaml
from dagster import Definitions
from factory import build_job_and_schedule

jobs, schedules = [], []
for path in sorted(glob.glob("/opt/agentbox/agents/*.yaml")):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not cfg or not cfg.get("enabled", True):
        continue
    job_, sched = build_job_and_schedule(cfg)
    jobs.append(job_)
    if sched:
        schedules.append(sched)

defs = Definitions(jobs=jobs, schedules=schedules)
