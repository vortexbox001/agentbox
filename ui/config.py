"""Runtime configuration for the agentbox UI.

Values are read from the environment at import, falling back to the in-container
paths from docker-compose. Access these as module attributes (``config.AGENTS_DIR``)
rather than importing the names directly, so tests can monkeypatch them.
"""
import os
from pathlib import Path

# Directory of agent YAML files the UI lists, creates, edits, and deletes.
AGENTS_DIR = os.environ.get("AGENTS_DIR", "/opt/agentbox/agents")

# Directory of prompt markdown files the UI lists and creates.
PROMPTS_DIR = os.environ.get("PROMPTS_DIR", "/opt/agentbox/prompts")

# Directory of automation YAML files (spec 005): agent triggers (cron/on_demand). The
# Automation view reads all files here and writes the canonical automation/migrated.yaml.
AUTOMATION_DIR = os.environ.get("AUTOMATION_DIR", "/opt/agentbox/automation")

# LiteLLM proxy config, read (never written) to discover the model aliases pi/api agents may use.
LITELLM_CONFIG = os.environ.get("LITELLM_CONFIG", "/opt/agentbox/litellm/config.yaml")

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
