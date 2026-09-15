"""Runtime configuration for the agentbox UI.

Values are read from the environment at import, falling back to the in-container
paths from docker-compose. Access these as module attributes (``config.AGENTS_DIR``)
rather than importing the names directly, so tests can monkeypatch them.
"""
import os
from pathlib import Path

# --- Root resolution (FR-002, SC-009) ----------------------------------------
# The UI's single root-resolution point: the three root env vars are read *once* here and
# every config/state path derives from them — no other UI module reads a root env var or
# carries a literal /opt/agentbox path. This module mirrors orchestrator/paths.py (the two
# processes run in separate containers with no shared import); a shared-fixture parity test
# pins the duplicated constants (root names, default subpaths) in agreement.

# Product tree (the repo checkout) — read-only; the anchor the FR-025 "under the product tree"
# path-validation check needs. ui/config.py -> ui/ -> product root; overridable for tests.
PRODUCT_ROOT = os.environ.get("AGENTBOX_PRODUCT_ROOT") or str(Path(__file__).resolve().parent.parent)

# The three roots (contracts/path-resolution.md §1), read once at import.
CONFIG_ROOT = os.environ.get("AGENTBOX_CONFIG") or os.path.join(PRODUCT_ROOT, "config")
DATA_ROOT = os.environ.get("AGENTBOX_DATA") or "/data/agentbox"
DAGSTER_ROOT = os.environ.get("DAGSTER_HOME") or "/data/dagster"

# Directory of agent YAML files the UI lists, creates, edits, and deletes — under the config
# root, so UI edits never touch the product tree (FR-007). Explicit env override wins.
AGENTS_DIR = os.environ.get("AGENTS_DIR") or os.path.join(CONFIG_ROOT, "agents")

# Directory of prompt markdown files the UI lists and creates — under the config root.
PROMPTS_DIR = os.environ.get("PROMPTS_DIR") or os.path.join(CONFIG_ROOT, "prompts")

# Product-owned sample trees (read-only). The template picker sources starters from here, not
# from the instance agents dir (FR-008); TEMPLATES_DIR is the agents subtree of the examples.
EXAMPLES_DIR = os.environ.get("EXAMPLES_DIR") or os.path.join(PRODUCT_ROOT, "examples", "config")
TEMPLATES_DIR = os.environ.get("TEMPLATES_DIR") or os.path.join(EXAMPLES_DIR, "agents")

# The GENERATED LiteLLM config the proxy loads (produced by litellm/generate.py from the
# product template + instance overlay, under the config root). This is the single source the
# UI reads to discover the model aliases pi/api agents may use (never written by the UI).
LITELLM_RENDERED = os.environ.get("LITELLM_RENDERED") or os.path.join(CONFIG_ROOT, "litellm.rendered.yaml")

# Dagster webserver base URL for server-side calls (the reload mutation, status).
# This is the in-network hostname; it is reachable container-to-container, NOT from
# a browser, so it must not be used for links the user clicks.
DAGSTER_URL = os.environ.get("DAGSTER_URL", "http://dagster-webserver:3000")

# Browser-facing Dagster base URL for links the user clicks (sidebar, job deep links).
# Leave empty to derive it from the incoming request's host with the Dagster port, so
# it works whether the UI is reached via the host IP, localhost, or a hostname. Set it
# explicitly when Dagster is served behind a different host/proxy than this UI.
DAGSTER_PUBLIC_URL = os.environ.get("DAGSTER_PUBLIC_URL", "")

# Dagster code-location name, which is part of every job URL:
# <base>/locations/<location>/jobs/<job>. With no explicit location_name in
# orchestrator/workspace.yaml, Dagster names the location after the loaded file.
DAGSTER_LOCATION = os.environ.get("DAGSTER_LOCATION", "definitions.py")

# The design system component library, served as static files at /design-system/.
# Defaults next to this file so it resolves both in the container and when run locally.
DESIGN_SYSTEM_DIR = os.environ.get(
    "DESIGN_SYSTEM_DIR", str(Path(__file__).resolve().parent / "design-system")
)

# How long to wait for a Dagster workspace reload before reporting it unreachable.
RELOAD_TIMEOUT_S = int(os.environ.get("RELOAD_TIMEOUT_S", "10"))
