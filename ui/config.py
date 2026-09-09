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

# LiteLLM proxy config, read (never written) to discover the model aliases pi/api agents may use.
LITELLM_CONFIG = os.environ.get("LITELLM_CONFIG", "/opt/agentbox/litellm/config.yaml")

# Dagster webserver base URL, for the reload mutation and per-agent job deep links.
DAGSTER_URL = os.environ.get("DAGSTER_URL", "http://dagster-webserver:3000")

# The design system component library, served as static files at /design-system/.
# Defaults next to this file so it resolves both in the container and when run locally.
DESIGN_SYSTEM_DIR = os.environ.get(
    "DESIGN_SYSTEM_DIR", str(Path(__file__).resolve().parent / "design-system")
)

# How long to wait for a Dagster workspace reload before reporting it unreachable.
RELOAD_TIMEOUT_S = int(os.environ.get("RELOAD_TIMEOUT_S", "10"))
