"""Run-retention prune logic (spec 012, contracts/settings.md, FR-026/FR-027).

For each run directory older than the configured horizon, remove ONLY ``events.jsonl`` and
``transcript.jsonl``. ``report.json``, ``context.json``, and the run's ``/output`` artifacts are
never touched, so a pruned run still opens (its Conversation tab shows a "pruned" note). Under the
default ``keep_forever`` policy the prune is a no-op.

The retention policy is read from ``settings.yaml`` (mirrors ``ui/settings_store``; the two run in
separate containers with no shared import).
"""
from __future__ import annotations

import datetime
import os
from typing import Optional

import yaml

import paths

_MODES = ("keep_forever", "prune_after_days")
# Only these two files are ever removed by retention (contracts/run-directory.md).
_PRUNABLE = (paths.RUN_EVENTS, paths.RUN_TRANSCRIPT)


def load_retention(settings_file: Optional[str] = None) -> dict:
    """The retention policy from settings.yaml, normalized to ``{mode, days}`` with defaults."""
    path = settings_file or paths.SETTINGS_FILE
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {"mode": "keep_forever", "days": None}
    block = doc.get("retention") or {}
    mode = block.get("mode") if block.get("mode") in _MODES else "keep_forever"
    days = block.get("days")
    if mode == "prune_after_days" and isinstance(days, int) and not isinstance(days, bool) and days >= 1:
        return {"mode": mode, "days": days}
    return {"mode": "keep_forever", "days": None}


def prune_runs(policy: Optional[dict] = None, now: Optional[datetime.date] = None,
               runs_root: Optional[str] = None) -> dict:
    """Prune conversation files from run directories older than the horizon.

    Returns ``{pruned, files_removed, skipped}``. ``keep_forever`` (or an invalid policy) →
    ``skipped: True`` and nothing removed (FR-025 default).
    """
    policy = policy or load_retention()
    if policy.get("mode") != "prune_after_days" or not policy.get("days"):
        return {"pruned": 0, "files_removed": 0, "skipped": True}
    days = int(policy["days"])
    today = now or datetime.date.today()
    horizon = today - datetime.timedelta(days=days)  # runs dated before this are pruned
    root = runs_root or paths.RUNS_ROOT
    pruned = removed = 0
    if not os.path.isdir(root):
        return {"pruned": 0, "files_removed": 0, "skipped": False}
    for agent in os.listdir(root):
        agent_dir = os.path.join(root, agent)
        if not os.path.isdir(agent_dir):
            continue
        for date in os.listdir(agent_dir):
            date_dir = os.path.join(agent_dir, date)
            if not os.path.isdir(date_dir):
                continue
            try:
                d = datetime.date.fromisoformat(date)
            except ValueError:
                continue
            if d >= horizon:
                continue  # within the retention window — keep
            for run_id in os.listdir(date_dir):
                run_dir = os.path.join(date_dir, run_id)
                if not os.path.isdir(run_dir):
                    continue
                r = 0
                for fn in _PRUNABLE:
                    fp = os.path.join(run_dir, fn)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                            r += 1
                        except OSError:
                            pass
                if r:
                    pruned += 1
                    removed += r
    return {"pruned": pruned, "files_removed": removed, "skipped": False}
