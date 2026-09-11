#!/usr/bin/env python3
"""One-off migration (spec 006): fold triggering back ONTO each agent.

Spec 005 moved agent triggers into a standalone ``automation/migrated.yaml`` (a map keyed by
agent name → ``{cron: "..."}``). Spec 006 retires that store: each agent now carries its own
``triggers:`` block. This script reads ``automation/migrated.yaml`` and, for each entry, opens
``agents/<name>.yaml``, decides the agent's kind by ``produces`` presence, and writes the cron
onto the right per-kind key:

  * asset-mode (has ``produces``) → ``triggers.asset_schedule``
  * job-mode  (no ``produces``)   → ``triggers.job_schedule`` (and ``job: true``)

Each touched file is re-emitted through the UI emitter, so its schema stamp is bumped to 4 and
its shape is canonical. Finally the whole ``automation/`` directory is removed.

Run once from the repo root: ``python3 scripts/migrate-automation-to-triggers.py``. Idempotent:
with ``automation/`` gone a re-run reports nothing to do. A named agent that does not exist is
printed and skipped, never silently dropped.
"""
import os
import shutil
import sys

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")
AUTOMATION_DIR = os.path.join(REPO_ROOT, "automation")
MIGRATED = os.path.join(AUTOMATION_DIR, "migrated.yaml")

# The emitter is the UI's; import it so a migrated file is byte-identical to a UI save.
sys.path.insert(0, os.path.join(REPO_ROOT, "ui"))


def _emit(loaded: dict) -> str:
    import agents_store  # imported lazily so the module is only needed when there is work to do
    return agents_store.emit_yaml(loaded)


def _load_migrated() -> dict:
    if not os.path.exists(MIGRATED):
        return {}
    with open(MIGRATED, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _cron_of(entry) -> str | None:
    """The cron string from an automation entry (``{cron: "..."}``), or None (on-demand)."""
    if isinstance(entry, dict):
        cron = entry.get("cron")
        if isinstance(cron, str) and cron.strip():
            return cron.strip()
    return None


def main() -> int:
    entries = _load_migrated()
    if not entries:
        # Either already migrated (automation/ gone) or nothing was ever scheduled.
        if os.path.isdir(AUTOMATION_DIR):
            shutil.rmtree(AUTOMATION_DIR)
            print("→ removed automation/ (no entries to carry over)")
        else:
            print("→ nothing to do (automation/ already removed)")
        return 0

    touched: list[str] = []
    for name, entry in entries.items():
        cron = _cron_of(entry)
        if cron is None:
            continue  # on-demand: no schedule to carry over
        path = os.path.join(AGENTS_DIR, f"{name}.yaml")
        if not os.path.isfile(path):
            print(f"! skipping {name}: no agents/{name}.yaml", file=sys.stderr)
            continue
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        block = dict(loaded.get("triggers") or {}) if isinstance(loaded.get("triggers"), dict) else {}
        if "produces" in loaded:
            block["asset_schedule"] = cron
        else:
            block["job_schedule"] = cron
            loaded["job"] = True
        loaded["triggers"] = block
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(_emit(loaded))
        touched.append(f"{name}.yaml")

    shutil.rmtree(AUTOMATION_DIR)

    if touched:
        print(f"→ carried {len(touched)} cron(s) onto agents: {', '.join(touched)}")
    else:
        print("→ no crons to carry over")
    print("→ removed automation/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
