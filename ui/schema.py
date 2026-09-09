"""The one source of truth for the agent file format.

Every field's harness applicability, choices, default, and explanation lives here.
This module drives the form, server-side validation, the YAML emitter (comments
included), and the ``GET /api/schema`` payload the browser renders from.

There is no database in this feature: ``agents/*.yaml`` plus this module *is* the
data model. Schema evolution is handled the file-based way (research R12): every
emitted file carries ``# agentbox-schema: <N>``; ``MIGRATIONS`` brings older files
up to the current version in memory on read; unknown keys are preserved untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Callable

import yaml

import config

# Current schema version, stamped into every emitted file. Bump when a migration
# is added below. Files without the stamp are read as version 0.
SCHEMA_VERSION = 1

# Ordered, forward-only migrations. Each pair is (target_version, fn) where fn
# transforms a definition dict from target_version - 1 to target_version. Pure
# dict -> dict, applied on read (never mutating the file until the user saves).
MIGRATIONS: list[tuple[int, Callable[[dict], dict]]] = []


class SchemaTooNew(Exception):
    """A file stamped with a schema version newer than this UI understands."""

    def __init__(self, version: int):
        self.version = version
        super().__init__(f"written by a newer agentbox (schema {version})")


# --- Sections -------------------------------------------------------------
# FR-002 order. The emitter writes them in this order; "Unmanaged" is appended
# by the emitter for keys the schema does not define and is not a form section.
SECTIONS: list[dict] = [
    {"id": "identity", "label": "Identity"},
    {"id": "model", "label": "Model"},
    {"id": "prompt_output", "label": "Prompt & output"},
    {"id": "workspace", "label": "Workspace"},
    {"id": "execution", "label": "Execution"},
    {"id": "scheduling", "label": "Scheduling"},
    {"id": "resources", "label": "Container resources"},
    {"id": "environment", "label": "Environment"},
]

_ALL = ["claude-code", "pi", "api", "codex"]


@dataclass
class SchemaField:
    id: str
    section: str
    label: str
    type: str  # string|int|number|bool|enum|list|map|path|cron
    help: str
    harnesses: list[str]
    required: bool = False
    default: object = None
    choices: list | None = None
    choice_source: str | None = None  # "litellm_aliases" | "prompts"
    pattern: str | None = None
    min: float | None = None
    max: float | None = None


# --- Fields ---------------------------------------------------------------
# One SchemaField per key in data-model.md, in section + display order. The help
# strings state what the field does, its valid values, and its default; they are
# emitted verbatim as the YAML comments and shown in the form.
FIELDS: list[SchemaField] = [
    # Identity
    SchemaField(
        "name", "identity", "Name", "string",
        "Unique kebab-case identifier. Becomes the Dagster job agent_<name> (hyphens become underscores).",
        _ALL, required=True, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    ),
    SchemaField(
        "enabled", "identity", "Enabled", "bool",
        "Disabled agents are skipped when Dagster loads the workspace. true or false; default true.",
        _ALL, required=True, default=True, choices=[True, False],
    ),
    SchemaField(
        "harness", "identity", "Harness", "enum",
        "Which runtime runs this agent; determines the available fields and models. One of claude-code, pi, api, codex.",
        _ALL, required=True, choices=list(_ALL),
    ),
    # Model
    SchemaField(
        "model", "model", "Model", "string",
        "Model the harness talks to.",
        _ALL,
    ),
    SchemaField(
        "effort", "model", "Effort", "enum",
        "Reasoning/thinking effort level.",
        ["claude-code", "pi", "codex"],
    ),
    SchemaField(
        "fallback_model", "model", "Fallback model", "string",
        "Model to use if the primary is overloaded.",
        ["claude-code"],
    ),
    SchemaField(
        "max_tokens", "model", "Max tokens", "int",
        "Cap on response tokens. 1 to 200000; default 1024.",
        ["api"], default=1024, min=1, max=200000,
    ),
    # Prompt & output
    SchemaField(
        "prompt_file", "prompt_output", "Prompt file", "string",
        "File in prompts/ read at launch and given to the agent as its prompt.",
        _ALL, required=True, choice_source="prompts",
    ),
    SchemaField(
        "output_dir", "prompt_output", "Output directory", "path",
        "Host directory mounted at /output; every run writes its result files here.",
        _ALL, required=True,
    ),
    SchemaField(
        "append_system_prompt", "prompt_output", "Append system prompt", "string",
        "Extra text appended to the system prompt.",
        ["claude-code", "pi", "codex"],
    ),
    # Workspace
    SchemaField(
        "workspace", "workspace", "Workspace", "path",
        "Host directory mounted at /workspace; scratch space for the run. Default /data/workspaces/<name>.",
        ["claude-code", "pi", "codex"],
    ),
    SchemaField(
        "wipe_workspace", "workspace", "Wipe workspace", "bool",
        "Empty the workspace before every run so each run starts clean. true or false; default false.",
        ["claude-code", "pi", "codex"], default=False, choices=[True, False],
    ),
    # Execution
    SchemaField(
        "timeout_seconds", "execution", "Timeout (seconds)", "int",
        "The run is killed after this many seconds. 1 to 86400; default 900.",
        _ALL, default=900, min=1, max=86400,
    ),
    SchemaField(
        "max_turns", "execution", "Max turns", "int",
        "Cap on agentic turns. 1 to 1000; default 10.",
        ["claude-code"], default=10, min=1, max=1000,
    ),
    SchemaField(
        "permission_mode", "execution", "Permission mode", "enum",
        "Claude Code permission mode.",
        ["claude-code"],
        choices=["default", "acceptEdits", "auto", "bypassPermissions", "dontAsk", "plan"],
    ),
    SchemaField(
        "allowed_tools", "execution", "Allowed tools", "list",
        "Tool allowlist.",
        ["claude-code", "pi"],
    ),
    SchemaField(
        "disallowed_tools", "execution", "Disallowed tools", "list",
        "Tool denylist (pi has no such flag).",
        ["claude-code"],
    ),
    SchemaField(
        "mcp_config", "execution", "MCP config", "path",
        "Path to an MCP server config JSON inside the container.",
        ["claude-code"],
    ),
    # Scheduling
    SchemaField(
        "schedule", "scheduling", "Schedule (cron)", "cron",
        "Cron expression for automatic runs; leave empty for manual-only. Five fields, e.g. 0 7 * * *.",
        _ALL, default="",
    ),
    # Container resources
    SchemaField(
        "network", "resources", "Network", "enum",
        "Docker network: agentnet-isolated (LiteLLM only, no internet), agentnet (LiteLLM + internet), "
        "bridge (full internet — needed by claude-code and codex). Default depends on harness.",
        _ALL, required=True, choices=["agentnet-isolated", "agentnet", "bridge"],
    ),
    SchemaField(
        "memory", "resources", "Memory", "string",
        "Container memory limit (e.g. 512m, 1g). Default 1g.",
        _ALL, default="1g", pattern=r"^\d+[kmg]$",
    ),
    SchemaField(
        "cpus", "resources", "CPUs", "number",
        "Container CPU limit (e.g. 1.5). 0.1 to 64; default 1.5.",
        _ALL, default=1.5, min=0.1, max=64,
    ),
    # Environment
    SchemaField(
        "env_file", "environment", "Env file", "path",
        "Host path to an env file passed to the container (keeps secrets off the command line). Applies to every harness.",
        _ALL,
    ),
    SchemaField(
        "env", "environment", "Environment variables", "map",
        "Environment variables for the container. ${NAME} forwards the host variable by name without exposing its value.",
        _ALL,
    ),
]

FIELDS_BY_ID: dict[str, SchemaField] = {f.id: f for f in FIELDS}

# The always-written set (contract agent-yaml.md §4): these are emitted even when
# unset so the file documents the essentials.
ALWAYS_WRITTEN = {"name", "enabled", "harness", "prompt_file", "output_dir", "network", "schedule"}


# --- Harnesses ------------------------------------------------------------
HARNESSES: list[dict] = [
    {
        "id": "claude-code",
        "label": "Claude Code",
        "description": "Runs the Claude Code CLI in a container with a workspace and tool access.",
        "image": "agentbox/agent-claude",
        "model_rule": {"choices": ["sonnet", "opus", "haiku", "fable"], "custom": "claude-id", "blank_ok": True},
        "effort_choices": ["low", "medium", "high", "xhigh", "max"],
        "default_network": "bridge",
    },
    {
        "id": "pi",
        "label": "pi",
        "description": "Runs pi, a minimal coding agent with a full tool loop, against the LiteLLM proxy.",
        "image": "agentbox/agent-pi",
        "model_rule": {"choice_source": "litellm_aliases", "custom": "provider-model", "blank_ok": True},
        "effort_choices": ["off", "minimal", "low", "medium", "high", "xhigh", "max"],
        "default_network": "agentnet",
    },
    {
        "id": "api",
        "label": "API (LiteLLM)",
        "description": "Lightweight agent that sends a prompt to LiteLLM and writes the response.",
        "image": "agentbox/agent-python",
        "model_rule": {"choice_source": "litellm_aliases", "custom": "none", "blank_ok": False},
        "effort_choices": [],
        "default_network": "agentnet-isolated",
    },
    {
        "id": "codex",
        "label": "Codex",
        "description": "Runs OpenAI's Codex CLI (codex exec) non-interactively in /workspace with its default tools.",
        "image": "agentbox/agent-codex",
        "model_rule": {"choices": [], "custom": "any", "blank_ok": True},
        "effort_choices": ["none", "minimal", "low", "medium", "high", "xhigh"],
        "default_network": "bridge",
        "model_suggestions": ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.3-codex-spark"],
    },
]

HARNESS_BY_ID: dict[str, dict] = {h["id"]: h for h in HARNESSES}

_LITELLM_FALLBACK = ["cheap", "smart", "opus", "kimi", "kimi-k3"]

# Full claude model id, optional [1m] context suffix (research R4).
_CLAUDE_ID_RE = re.compile(r"^claude-[a-z0-9.-]+(\[1m\])?$")
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MEMORY_RE = re.compile(r"^\d+[kmg]$")


def litellm_aliases() -> list[str]:
    """Model aliases pi/api agents may use, read from litellm/config.yaml.

    Falls back to the hardcoded default set when the file is missing or unreadable
    so the form still works without the config mounted.
    """
    try:
        with open(config.LITELLM_CONFIG) as f:
            data = yaml.safe_load(f) or {}
        names = [m["model_name"] for m in data.get("model_list", []) if m.get("model_name")]
        return names or list(_LITELLM_FALLBACK)
    except (FileNotFoundError, OSError, yaml.YAMLError, AttributeError, TypeError):
        return list(_LITELLM_FALLBACK)


def resolved_model_choices(harness: str) -> list[str]:
    """The concrete list of model choices offered for a harness right now."""
    h = HARNESS_BY_ID.get(harness)
    if not h:
        return []
    rule = h["model_rule"]
    if rule.get("choice_source") == "litellm_aliases":
        return litellm_aliases()
    return list(rule.get("choices", []))


def applicable_fields(harness: str) -> list[str]:
    """Ordered field ids that apply to a harness (data-model matrix)."""
    return [f.id for f in FIELDS if harness in f.harnesses]


def _is_unset(f: SchemaField, value) -> bool:
    """Whether a value counts as "unset" for emission/validation (contract §4).

    null, empty list, and empty map are unset. An empty string is a real value
    only for ``schedule`` (manual-only) and is otherwise unset.
    """
    if value is None:
        return True
    if f.type == "list" and value == []:
        return True
    if f.type == "map" and value == {}:
        return True
    if isinstance(value, str) and value == "":
        return f.id != "schedule"
    return False


def field_help(fid: str, harness: str) -> str:
    """The comment text for a field, with per-harness detail appended.

    The base help is harness-agnostic; model, effort, and allowed_tools gain a
    harness-specific clause so the emitted file documents the accepted values.
    """
    base = FIELDS_BY_ID[fid].help
    extra = _HARNESS_HELP.get((fid, harness))
    return f"{base} {extra}" if extra else base


_HARNESS_HELP: dict[tuple[str, str], str] = {
    ("model", "claude-code"): "claude-code: an alias (sonnet, opus, haiku, fable) or a full claude-... id; blank for the CLI default.",
    ("model", "pi"): "pi: a LiteLLM alias from litellm/config.yaml, or provider/model.",
    ("model", "api"): "api: a LiteLLM alias from litellm/config.yaml.",
    ("model", "codex"): "codex: any codex model id; blank for codex's default.",
    ("effort", "claude-code"): "claude-code: low, medium, high, xhigh, or max.",
    ("effort", "pi"): "pi: off, minimal, low, medium, high, xhigh, or max.",
    ("effort", "codex"): "codex: none, minimal, low, medium, high, or xhigh.",
    ("allowed_tools", "claude-code"): "claude-code: any tool names (e.g. Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch).",
    ("allowed_tools", "pi"): "pi: any of read, write, edit, bash, grep, find, ls.",
}


def _validate_model(agent: dict, harness: str, errors: dict) -> None:
    model = agent.get("model")
    h = HARNESS_BY_ID.get(harness)
    if not h:
        return
    rule = h["model_rule"]
    blank = model is None or model == ""
    if blank:
        if not rule.get("blank_ok"):
            errors["model"] = f"model is required for the {harness} harness"
        return
    model = str(model)
    choices = resolved_model_choices(harness)
    if model in choices:
        return
    custom = rule.get("custom")
    if custom == "claude-id":
        if not _CLAUDE_ID_RE.match(model):
            errors["model"] = (
                f"invalid model for the {harness} harness: use an alias "
                "(sonnet, opus, haiku, fable) or a claude-... id, optionally with [1m]"
            )
    elif custom == "provider-model":
        if "/" not in model:
            errors["model"] = (
                f"invalid model for the {harness} harness: use a LiteLLM alias "
                f"({', '.join(choices)}) or a provider/model string"
            )
    elif custom == "any":
        pass  # any non-empty string is accepted (codex)
    elif custom == "none":
        errors["model"] = f"invalid model for the {harness} harness: must be one of {', '.join(choices)}"


def _validate_schedule(value, errors: dict) -> None:
    from croniter import croniter

    if value is None or value == "":
        return
    s = str(value).strip()
    if s.startswith("@"):
        errors["schedule"] = "cron macros like @daily are not supported; use a 5-field expression"
    elif len(s.split()) != 5:
        errors["schedule"] = "cron must have exactly five fields (minute hour day month weekday)"
    elif not croniter.is_valid(s):
        errors["schedule"] = "not a valid cron expression"


def validate(agent: dict, *, prompt_exists: Callable[[str], bool]) -> dict[str, str]:
    """Validate an agent definition; return a map of field id -> error message.

    An empty dict means the definition is valid. ``prompt_exists`` is called with
    the ``prompt_file`` value and should account for a prompt being created in the
    same save.
    """
    errors: dict[str, str] = {}
    harness = agent.get("harness")

    # Required fields must be present and non-unset.
    for f in FIELDS:
        if not f.required:
            continue
        if harness and harness not in f.harnesses:
            continue
        if f.id not in agent or _is_unset(f, agent.get(f.id)):
            errors[f.id] = f"{f.label} is required"

    if "name" in agent and agent.get("name") and not _NAME_RE.match(str(agent["name"])):
        errors["name"] = "must be kebab-case: lowercase letters and digits separated by single hyphens"

    if harness is not None and harness not in HARNESS_BY_ID:
        errors["harness"] = f"unknown harness; must be one of {', '.join(_ALL)}"
        return errors  # can't validate harness-specific rules against an unknown harness

    applicable = set(applicable_fields(harness)) if harness else set(FIELDS_BY_ID)

    # Enums, ranges, patterns for applicable, present, non-unset fields.
    for fid in applicable:
        f = FIELDS_BY_ID[fid]
        if fid not in agent or _is_unset(f, agent.get(fid)):
            continue
        val = agent[fid]
        if fid in errors:
            continue
        if f.id == "model":
            continue  # handled below
        if f.id == "schedule":
            continue  # handled below
        if f.id == "effort":
            choices = HARNESS_BY_ID[harness]["effort_choices"] if harness else []
            if val not in choices:
                errors[fid] = f"must be one of: {', '.join(choices)}" if choices else "effort does not apply to this harness"
        elif f.type == "enum" and f.choices is not None:
            if val not in f.choices:
                errors[fid] = f"must be one of: {', '.join(str(c) for c in f.choices)}"
        elif f.type == "bool":
            if not isinstance(val, bool):
                errors[fid] = "must be true or false"
        elif f.type in ("int",):
            if not isinstance(val, int) or isinstance(val, bool):
                errors[fid] = "must be a whole number"
            elif (f.min is not None and val < f.min) or (f.max is not None and val > f.max):
                errors[fid] = f"must be between {int(f.min)} and {int(f.max)}"
        elif f.type == "number":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                errors[fid] = "must be a number"
            elif (f.min is not None and val < f.min) or (f.max is not None and val > f.max):
                errors[fid] = f"must be between {f.min} and {f.max}"
        elif f.pattern is not None:
            if not isinstance(val, str) or not re.match(f.pattern, val):
                errors[fid] = f"must match {f.pattern}"
        elif f.id == "env":
            if not isinstance(val, dict):
                errors[fid] = "must be a mapping of NAME: value"
            else:
                bad = [k for k in val if not _ENV_KEY_RE.match(str(k))]
                if bad:
                    errors[fid] = f"invalid variable name(s): {', '.join(bad)} (use A-Z, 0-9, underscore; must not start with a digit)"

    # A field that does not apply to the chosen harness must not carry a value
    # (FR-007): e.g. effort on the api harness. Reject it, naming the harness, so
    # a stale value from a harness switch can never be saved silently.
    if harness:
        for f in FIELDS:
            if f.id in applicable or f.id in errors:
                continue
            if f.id in agent and not _is_unset(f, agent.get(f.id)):
                errors[f.id] = f"{f.label} does not apply to the {harness} harness"

    if harness:
        _validate_model(agent, harness, errors)
    if "schedule" in agent:
        _validate_schedule(agent.get("schedule"), errors)

    pf = agent.get("prompt_file")
    if pf and "prompt_file" not in errors and not prompt_exists(str(pf)):
        errors["prompt_file"] = f"no such prompt file in prompts/: {pf}"

    return errors


def network_mismatch_warning(agent: dict) -> str | None:
    """A non-blocking FR-024 notice when harness and network disagree, else None."""
    harness = agent.get("harness")
    network = agent.get("network")
    if not harness or not network:
        return None
    if harness in ("claude-code", "codex") and network != "bridge":
        return (
            f"{harness} needs network: bridge to reach its provider; "
            f"{network} has no internet access"
        )
    if harness == "api" and network == "bridge":
        return "api only needs LiteLLM; bridge grants unnecessary internet access"
    return None


def apply_migrations(data: dict, from_version: int) -> dict:
    """Bring a definition dict up to the current schema version.

    Raises SchemaTooNew when the file was written by a newer UI than this one.
    """
    if from_version > SCHEMA_VERSION:
        raise SchemaTooNew(from_version)
    version = from_version
    for target, fn in MIGRATIONS:
        if version < target:
            data = fn(data)
            version = target
    return data


def _field_public(f: SchemaField) -> dict:
    out = {
        "id": f.id,
        "section": f.section,
        "label": f.label,
        "type": f.type,
        "required": f.required,
        "default": f.default,
        "choices": f.choices,
        "help": f.help,
        "harnesses": list(f.harnesses),
    }
    if f.choice_source:
        out["choice_source"] = f.choice_source
    if f.pattern:
        out["pattern"] = f.pattern
    if f.min is not None:
        out["min"] = f.min
    if f.max is not None:
        out["max"] = f.max
    return out


def _harness_public(h: dict) -> dict:
    rule = dict(h["model_rule"])
    if rule.get("choice_source") == "litellm_aliases":
        rule["choices"] = litellm_aliases()
    out = {
        "id": h["id"],
        "label": h["label"],
        "description": h["description"],
        "image": h["image"],
        "fields": applicable_fields(h["id"]),
        "model_rule": rule,
        "effort_choices": list(h["effort_choices"]),
        "default_network": h["default_network"],
    }
    if "model_suggestions" in h:
        out["model_suggestions"] = list(h["model_suggestions"])
    return out


def to_public() -> dict:
    """The GET /api/schema payload shape (contract http-api.md).

    ``litellm_aliases`` and ``prompts`` are added by the endpoint, not here.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "sections": [dict(s) for s in SECTIONS],
        "fields": [_field_public(f) for f in FIELDS],
        "harnesses": [_harness_public(h) for h in HARNESSES],
    }
