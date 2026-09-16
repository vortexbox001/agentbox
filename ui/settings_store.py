"""Read/write instance settings (spec 012, contracts/settings.md).

The Settings page's server-backed store over ``$AGENTBOX_CONFIG/settings.yaml``. Today it owns the
``retention`` block (the nightly prune job reads the same file). Unknown keys are preserved on
write, so future settings sections extend the same file.
"""
from __future__ import annotations

import os
from typing import Optional

import yaml

import config

MODES = ("keep_forever", "prune_after_days")
DEFAULT_RETENTION = {"mode": "keep_forever", "days": None}

# Run governors (spec 013 US5). The twin of orchestrator/governors.DEFAULT_GOVERNORS, pinned by a
# parity test; the live values are the settings.yaml file. Sane upper bounds keep a typo from
# authoring an absurd cap.
DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}
GOVERNOR_CAPS = {"max_runs_per_hour": 10000, "max_chain_depth": 1000}


class RetentionError(ValueError):
    """An invalid retention policy (bad mode, or missing/invalid days)."""


class GovernorError(ValueError):
    """An invalid governor value (not a positive integer, or over the sane cap)."""


def _path() -> str:
    return config.SETTINGS_FILE


def read_settings() -> dict:
    """The whole settings document ({} when the file is absent or empty)."""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except OSError:
        return {}


def read_retention() -> dict:
    """The retention block, normalized to ``{mode, days}`` with defaults for absent/invalid."""
    block = (read_settings().get("retention") or {})
    mode = block.get("mode") if block.get("mode") in MODES else "keep_forever"
    days = block.get("days")
    if mode == "prune_after_days":
        days = days if isinstance(days, int) and not isinstance(days, bool) and days >= 1 else None
    else:
        days = None
    return {"mode": mode, "days": days}


def validate_retention(mode: str, days: Optional[int]) -> dict:
    """Validate + normalize a retention policy, or raise :class:`RetentionError`."""
    if mode not in MODES:
        raise RetentionError(f"mode must be one of {MODES}")
    if mode == "prune_after_days":
        if isinstance(days, bool) or not isinstance(days, int) or days < 1:
            raise RetentionError("days must be an integer >= 1 when mode is prune_after_days")
        return {"mode": mode, "days": days}
    return {"mode": mode, "days": None}


def write_retention(mode: str, days: Optional[int] = None) -> dict:
    """Persist the retention block, preserving every other key in the file (contracts/settings.md)."""
    policy = validate_retention(mode, days)
    doc = read_settings()
    block = {"mode": policy["mode"]}
    if policy["days"] is not None:
        block["days"] = policy["days"]
    doc["retention"] = block
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)
    return policy


# --- Governors (spec 013 US5, contracts/ui-settings-and-form.md §5) ---------

def _governor_value(block: dict, key: str) -> int:
    """One governor, normalized to a positive int with a per-key fallback to the default."""
    v = block.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v > GOVERNOR_CAPS[key]:
        return DEFAULT_GOVERNORS[key]
    return v


def read_governors() -> dict:
    """The governors block, normalized to ``{max_runs_per_hour, max_chain_depth}`` with defaults for
    absent/invalid keys (twin of orchestrator/governors.load_governors)."""
    block = (read_settings().get("governors") or {})
    if not isinstance(block, dict):
        block = {}
    return {key: _governor_value(block, key) for key in DEFAULT_GOVERNORS}


def validate_governors(max_runs_per_hour, max_chain_depth) -> dict:
    """Validate + normalize both governors, or raise :class:`GovernorError`. Each must be an integer
    ``>= 1`` and ``<=`` its sane cap."""
    values = {"max_runs_per_hour": max_runs_per_hour, "max_chain_depth": max_chain_depth}
    out = {}
    for key, v in values.items():
        if isinstance(v, bool) or not isinstance(v, int):
            raise GovernorError(f"{key} must be a whole number")
        if v < 1:
            raise GovernorError(f"{key} must be at least 1")
        if v > GOVERNOR_CAPS[key]:
            raise GovernorError(f"{key} must be at most {GOVERNOR_CAPS[key]}")
        out[key] = v
    return out


def write_governors(max_runs_per_hour, max_chain_depth) -> dict:
    """Persist the governors block, preserving every other key in the file (same pattern as
    ``write_retention``)."""
    governors = validate_governors(max_runs_per_hour, max_chain_depth)
    doc = read_settings()
    doc["governors"] = dict(governors)
    os.makedirs(os.path.dirname(_path()), exist_ok=True)
    with open(_path(), "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)
    return governors
