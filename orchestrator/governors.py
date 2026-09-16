"""Run governors reader (spec 013 US5, contracts/orchestrator-model.md §6).

The orchestrator side of the two instance-level governors that bound automated trigger chains:
``max_runs_per_hour`` (a rolling 60-minute window) and ``max_chain_depth``. The live values come
from ``settings.yaml`` — the same file the UI's Settings page writes and the prune job's retention
block already uses; only the fallback defaults are duplicated here (the twin of
``ui/settings_store.DEFAULT_GOVERNORS``, pinned by a parity test, research R10).
"""
from __future__ import annotations

from typing import Optional

import yaml

import paths

# The fallback when the file/block/key is absent or invalid. Twin of ui/settings_store; pinned by
# orchestrator/tests/test_paths_parity.py.
DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}


def _positive_int(value) -> Optional[int]:
    """``value`` when it is a positive int (not a bool), else ``None`` (fall back to the default)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def load_governors(settings_file: Optional[str] = None) -> dict:
    """The governors block from ``settings.yaml``, normalized to
    ``{max_runs_per_hour, max_chain_depth}`` with a per-key fallback to ``DEFAULT_GOVERNORS`` when
    the file/block/key is absent or invalid (contract §6)."""
    path = settings_file or paths.SETTINGS_FILE
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        doc = {}
    block = doc.get("governors") if isinstance(doc, dict) else None
    block = block if isinstance(block, dict) else {}
    out = {}
    for key, default in DEFAULT_GOVERNORS.items():
        out[key] = _positive_int(block.get(key)) or default
    return out
