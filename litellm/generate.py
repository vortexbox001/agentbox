#!/usr/bin/env python3
"""Generate the rendered LiteLLM config from the product template plus the instance overlay.

Deep-merges the instance overlay (``$AGENTBOX_CONFIG/litellm.overlay.yaml``) over the
product template (``litellm/config.template.yaml``) and writes the result to
``$AGENTBOX_CONFIG/litellm.rendered.yaml`` — the sole config the LiteLLM container mounts
and loads (FR-014/FR-016, R6). The template owns the alias tier *names* features depend on;
the overlay owns each tier's concrete ``model``/``api_base``/``api_key``/pricing.

``api_key`` values stay as ``os.environ/<NAME>`` references in the rendered file and are
**never** expanded to a secret value (Constitution III). Before writing, every ``api_key:
os.environ/<NAME>`` the merged config references must be present in the environment; if any
is missing the generator exits non-zero naming the missing key(s) and writes nothing
(FR-017, R-LL-2), so no config ever ships whose only failure is at first request.

Runs on demand (``python3 litellm/generate.py``) and at stack start (a compose init step
that completes before the LiteLLM container loads its config).
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import yaml

# This file lives at ``<product>/litellm/generate.py``; the template is its sibling.
PRODUCT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "config.template.yaml"

_ENV_PREFIX = "os.environ/"


def config_root() -> Path:
    """The instance-configuration root (contracts/path-resolution.md §1).

    Read from ``AGENTBOX_CONFIG`` on each call so a monkeypatched env or a per-invocation
    override takes effect; defaults to ``<product>/config``.
    """
    return Path(os.environ.get("AGENTBOX_CONFIG") or (PRODUCT_ROOT / "config"))


def _deep_merge(base, over):
    """Recursively merge ``over`` onto ``base`` (over wins); scalars/lists are replaced."""
    if isinstance(base, dict) and isinstance(over, dict):
        merged = dict(base)
        for key, value in over.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(over)


def _merge_model_list(base_list, over_list):
    """Merge two ``model_list`` sequences keyed by ``model_name`` (overlay wins per tier).

    Template order is preserved; overlay-only models are appended in overlay order.
    """
    by_name: dict = {}
    order: list = []
    for model in base_list or []:
        name = model.get("model_name")
        by_name[name] = copy.deepcopy(model)
        order.append(name)
    for model in over_list or []:
        name = model.get("model_name")
        if name in by_name:
            by_name[name] = _deep_merge(by_name[name], model)
        else:
            by_name[name] = copy.deepcopy(model)
            order.append(name)
    return [by_name[name] for name in order]


def merge_config(template: dict, overlay: dict) -> dict:
    """Deep-merge ``overlay`` over ``template``, merging ``model_list`` per tier by name."""
    template = template or {}
    overlay = overlay or {}
    merged = _deep_merge(template, overlay)
    if template.get("model_list") or overlay.get("model_list"):
        merged["model_list"] = _merge_model_list(
            template.get("model_list"), overlay.get("model_list")
        )
    return merged


def referenced_env_keys(cfg: dict) -> list[str]:
    """Every ``<NAME>`` in an ``api_key: os.environ/<NAME>`` reference, in first-seen order."""
    keys: list[str] = []
    for model in (cfg or {}).get("model_list") or []:
        value = (model.get("litellm_params") or {}).get("api_key")
        if isinstance(value, str) and value.startswith(_ENV_PREFIX):
            name = value[len(_ENV_PREFIX):]
            if name and name not in keys:
                keys.append(name)
    return keys


def render() -> dict:
    """Load template + overlay and return the merged config (no env check, no write)."""
    template = yaml.safe_load(TEMPLATE.read_text()) or {}
    overlay_path = config_root() / "litellm.overlay.yaml"
    if not overlay_path.exists():
        raise FileNotFoundError(
            f"litellm overlay not found at {overlay_path}; copy examples/config/"
            "litellm.overlay.yaml into the config root."
        )
    overlay = yaml.safe_load(overlay_path.read_text()) or {}
    return merge_config(template, overlay)


def main() -> int:
    try:
        merged = render()
    except FileNotFoundError as exc:
        print(f"litellm/generate.py: {exc}", file=sys.stderr)
        return 1

    missing = [name for name in referenced_env_keys(merged) if name not in os.environ]
    if missing:
        print(
            "litellm/generate.py: missing required environment variable(s): "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print("litellm/generate.py: no rendered config written.", file=sys.stderr)
        return 1

    out = config_root() / "litellm.rendered.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# GENERATED by litellm/generate.py — do not edit.\n"
        "# Source: litellm/config.template.yaml (product) + litellm.overlay.yaml (instance).\n"
    )
    out.write_text(header + yaml.safe_dump(merged, sort_keys=False))
    print(f"litellm/generate.py: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
