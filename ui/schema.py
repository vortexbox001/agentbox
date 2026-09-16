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

import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Callable

import yaml

import config

# Current schema version, stamped into every emitted file. Bump when a migration
# is added below. Files without the stamp are read as version 0.
SCHEMA_VERSION = 7


def migrate_1_to_2(data: dict) -> dict:
    """Schema 1 -> 2: the optional `produces` block was added. Schema-1 files have no
    `produces`, so there is nothing to transform — this is the identity function, and
    existing files load with zero migration noise (SC-005). They are re-stamped to 2
    only when next saved from the UI."""
    return data


def migrate_2_to_3(data: dict) -> dict:
    """Schema 2 -> 3: the `schedule` field left the agent schema (spec 005). Drop any lingering
    `schedule` key on read; the dropped value is NOT turned into a trigger (FR-002). The reader
    (agents_store) logs a warning naming the file when it strips one. Schema-2 files without
    `schedule` load with zero noise. (Spec 006's `triggers:` block is the current home.)"""
    data.pop("schedule", None)
    return data


def migrate_3_to_4(data: dict) -> dict:
    """Schema 3 -> 4: an agent's nature became explicit (spec 006, contract agent-model §4).

    Under schema 3 an agent's nature was inferred: a `produces` block meant asset, its absence
    meant job. Schema 4 makes both explicit. So on read: a file with NO `produces` was a job
    under the old model — set ``job: true``. A file WITH `produces` was asset-only — leave
    ``job`` unset. A read-migration never fabricates a ``triggers`` block (schedules move onto
    the agent via the one-off carry-over script, not on read)."""
    if "produces" not in data:
        data["job"] = True
    return data


def migrate_4_to_5(data: dict) -> dict:
    """Schema 4 -> 5: `produces.checks` was added (spec 008). Checks are additive — a
    schema-4 file simply has none — so this is the identity function. Existing files load
    with zero migration noise and re-stamp to 5 only when next saved from the UI."""
    return data


def migrate_5_to_6(data: dict) -> dict:
    """Schema 5 -> 6: the layout overhaul (spec 010, FR-026). `output_dir` became optional
    with the documented default ``$AGENTBOX_DATA/outputs/<name>``, and the config/state roots
    are now resolved from the three root env vars (contracts/path-resolution.md §1) rather than
    the hard-coded ``/data`` and ``<repo>`` locations. No field is renamed or moved, so on read
    this is the identity function: a schema-5 file's explicit ``output_dir`` (and every other
    field) is preserved untouched and re-stamps to 6 only when next saved from the UI."""
    return data


def migrate_6_to_7(data: dict) -> dict:
    """Schema 6 -> 7: the dependency graph (spec 013). ``produces.depends_on`` (a list of
    upstream asset keys) and the two asset-kind triggers ``triggers.on_upstream`` /
    ``triggers.on_missing`` were added. All three are additive — a schema-6 file simply has
    none — so this is the identity function: existing files load with zero migration noise and
    re-stamp to 7 only when next saved from the UI (same posture as migrate_4_to_5/5_to_6)."""
    return data


# Ordered, forward-only migrations. Each pair is (target_version, fn) where fn
# transforms a definition dict from target_version - 1 to target_version. Pure
# dict -> dict, applied on read (never mutating the file until the user saves).
MIGRATIONS: list[tuple[int, Callable[[dict], dict]]] = [
    (2, migrate_1_to_2), (3, migrate_2_to_3), (4, migrate_3_to_4), (5, migrate_4_to_5),
    (6, migrate_5_to_6), (7, migrate_6_to_7),
]


class SchemaTooNew(Exception):
    """A file stamped with a schema version newer than this UI understands."""

    def __init__(self, version: int):
        self.version = version
        super().__init__(f"written by a newer agentbox (schema {version})")


# --- Groups & sections ----------------------------------------------------
# Groups are the form's three columns (spec 003 FR-015). A section belongs to one
# group, or to none — the lone group-less section (identity) renders in the lead
# strip while still being written first in the file. The emitter writes sections
# in this order; "Unmanaged" is appended by the emitter for keys the schema does
# not define and is not a form section.
GROUPS: list[dict] = [
    {"id": "runs", "label": "Runs"},
    {"id": "job", "label": "Job"},
    {"id": "box", "label": "Box"},
]

SECTIONS: list[dict] = [
    {"id": "identity", "label": "Identity", "group": None},
    {"id": "status", "label": "Enabled", "group": "runs"},
    {"id": "limits", "label": "Limits", "group": "runs"},
    {"id": "produces", "label": "Produces", "group": "runs"},
    {"id": "triggers", "label": "Triggers", "group": "runs"},
    {"id": "run_as_job", "label": "Job", "group": "job"},
    {"id": "prompt", "label": "Prompt", "group": "job"},
    {"id": "directories", "label": "Directories", "group": "job"},
    {"id": "environment", "label": "Environment", "group": "job"},
    {"id": "tools", "label": "Tools & permissions", "group": "job"},
    {"id": "harness_model", "label": "Harness & model", "group": "box"},
    {"id": "container", "label": "Container", "group": "box"},
]

_ALL = ["claude-code", "pi", "api", "codex"]


# The asset key an agent may declare: one or more kebab segments joined by "/".
# Deliberately duplicated in orchestrator/factory.py (research R6): the UI and the
# orchestrator run in separate containers with no shared import, and a shared-fixture
# test pins the two copies in agreement.
ASSET_KEY_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"

# Comment on the `produces:` block header line in emitted YAML (real or commented-out).
PRODUCES_BLOCK_HELP = "Declare an output asset so this agent is a tracked Dagster asset; leave commented to stay a plain job."

# Networks a check container may opt into; omitted ⇒ no network (contract check-model §2.6).
CHECK_NETWORKS = ["agentnet-isolated", "agentnet", "bridge"]

# Comment on the `produces.checks:` list header line, and the per-field comments on each check
# mapping, emitted verbatim by the YAML writer (contract check-model §5/§7 — FR-012). These are
# the authoritative wording for the checks list; the form and README track them.
CHECKS_BLOCK_HELP = (
    "Optional pass/fail checks on the produced asset (needs an asset). Each runs after the "
    "producer in a fresh, read-only container and surfaces as a Dagster asset check — green on "
    "exit 0, red otherwise, with the last 4 KB of its output attached."
)
CHECK_FIELD_HELP: dict[str, str] = {
    "name": "Required, unique within the agent; kebab-case. Names the asset check.",
    "command": "Required; a shell command line run as sh -c. Exit 0 passes; anything else fails.",
    "image": "Docker image the check runs in. Default: the agent's harness image.",
    "blocking": "true gates downstream automation on failure (ERROR); false is advisory (WARN). Default true.",
    "timeout_seconds": "Killed and failed after this many seconds. 1 to 86400; default 300.",
    "network": "Docker network for the check: agentnet-isolated, agentnet, or bridge. Default: no network.",
}

# Comment on the `triggers:` block header line in emitted YAML (real or commented-out).
TRIGGERS_BLOCK_HELP = "When this agent runs on its own. Optional per-kind cron(s); leave commented for manual/on-demand only."


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
    block: str | None = None  # nested YAML block this field belongs to, e.g. "produces"


# --- Fields ---------------------------------------------------------------
# One SchemaField per key in data-model.md, in section + display order. The help
# strings state what the field does, its valid values, and its default; they are
# emitted verbatim as the YAML comments and shown in the form.
FIELDS: list[SchemaField] = [
    # Identity (lead strip)
    SchemaField(
        "name", "identity", "Name", "string",
        "Unique kebab-case identifier. Becomes the Dagster job agent_<name> (hyphens become underscores).",
        _ALL, required=True, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
    ),
    # Enabled (Runs) — when the agent runs lives in its own `triggers:` block (spec 006), not here.
    SchemaField(
        "enabled", "status", "Enabled", "bool",
        "Whether Dagster registers this agent at all (as a job/asset). Disabled agents are "
        "skipped at load. This does NOT control scheduling — set when it runs in the Automation "
        "view. true or false; default true.",
        _ALL, required=True, default=True, choices=[True, False],
    ),
    # Limits (Runs)
    SchemaField(
        "timeout_seconds", "limits", "Timeout (seconds)", "int",
        "The run is killed after this many seconds. 1 to 86400; default 900.",
        _ALL, default=900, min=1, max=86400,
    ),
    SchemaField(
        "max_turns", "limits", "Max turns", "int",
        "Cap on agentic turns. 1 to 1000; default 10.",
        ["claude-code"], default=10, min=1, max=1000,
    ),
    # Produces (Runs) — the nested `produces` block; both fields apply to every harness.
    SchemaField(
        "asset", "produces", "Asset key", "string",
        "Asset key this agent materializes, e.g. repo-review/agentbox. Kebab segments joined by / "
        "for grouping. Leave empty to stay a plain job.",
        _ALL, pattern=ASSET_KEY_RE, block="produces",
    ),
    SchemaField(
        "partition", "produces", "Partition", "enum",
        "Partition set for the asset: none (single) or daily. A tracking label only — it does not "
        "change the run or output. Default none.",
        _ALL, default="none", choices=["none", "daily"], block="produces",
    ),
    # A list of pass/fail check objects on the produced asset (spec 008). A new list-of-objects
    # field type ("checks"): its per-item shape and validation live in `_validate_checks`, and it
    # is emitted as a nested sequence-of-mappings under `produces:` by the YAML writer.
    SchemaField(
        "checks", "produces", "Checks", "checks",
        CHECKS_BLOCK_HELP,
        _ALL, block="produces",
    ),
    # The upstream asset keys this asset depends on (spec 013). A new `list` field under the
    # `produces` block; each entry is validated against ASSET_KEY_RE, and existence + acyclicity
    # across agents are enforced at load (orchestrator) / best-effort at author time.
    SchemaField(
        "depends_on", "produces", "Depends on", "list",
        "Upstream asset keys this asset depends on (kebab segments joined by /). When on_upstream "
        "is set, a materialization of any of these fires this asset for the matching partition; "
        "each is also handed to the container as AGENTBOX_UPSTREAM_<KEY>. Needs an asset.",
        _ALL, block="produces",
    ),
    # Triggers (Runs) — the nested `triggers` block; each cron applies only to its kind.
    SchemaField(
        "asset_schedule", "triggers", "Asset schedule", "cron",
        "Cron that materializes the asset on a schedule (drives an on-cron auto-condition). "
        "Five fields, no @-macros. Applies only when the agent is an asset; blank = no schedule.",
        _ALL, block="triggers",
    ),
    # The two asset-kind event triggers (spec 013), bools under the `triggers` block. Both default
    # false (absent ⇒ off) and, like asset_schedule, apply only when the agent is an asset; they
    # live behind the same paused per-asset automation sensor.
    SchemaField(
        "on_upstream", "triggers", "On upstream", "bool",
        "Materialize this asset when any declared upstream materializes and passes its blocking "
        "checks. Applies only when the agent is an asset; starts paused behind the asset's "
        "automation sensor.",
        _ALL, default=False, choices=[True, False], block="triggers",
    ),
    SchemaField(
        "on_missing", "triggers", "On missing", "bool",
        "Materialize the current/latest partition (today for daily; the single partition when "
        "unpartitioned) when it has never been produced. Does not backfill history. Applies only "
        "when the agent is an asset; starts paused behind the asset's automation sensor.",
        _ALL, default=False, choices=[True, False], block="triggers",
    ),
    SchemaField(
        "job_schedule", "triggers", "Job schedule", "cron",
        "Cron that launches the agent's job on a schedule. Five fields, no @-macros. Applies only "
        "when the agent has a job; blank = manual/launchable only.",
        _ALL, block="triggers",
    ),
    # Job (Job group) — the explicit job flag; a job creates agent_<name>.
    SchemaField(
        "job", "run_as_job", "Create agent job", "bool",
        "Whether this agent has a Dagster job agent_<name> you can launch or schedule. true or "
        "false; default false. An agent must be an asset, a job, or both.",
        _ALL, default=False, choices=[True, False],
    ),
    # Prompt (Job)
    SchemaField(
        "prompt_file", "prompt", "Prompt file", "string",
        "File in prompts/ read at launch and given to the agent as its prompt.",
        _ALL, required=True, choice_source="prompts",
    ),
    SchemaField(
        "append_system_prompt", "prompt", "Append system prompt", "string",
        "Extra text appended to the system prompt.",
        ["claude-code", "pi", "codex"],
    ),
    # Directories (Job)
    SchemaField(
        "workspace", "directories", "Workspace", "path",
        "Host directory mounted at /workspace; scratch space for the run. Default $AGENTBOX_DATA/workspaces/<name>.",
        ["claude-code", "pi", "codex"],
    ),
    SchemaField(
        "wipe_workspace", "directories", "Wipe workspace", "bool",
        "Empty the workspace before every run so each run starts clean. true or false; default false.",
        ["claude-code", "pi", "codex"], default=False, choices=[True, False],
    ),
    SchemaField(
        "output_dir", "directories", "Output directory", "path",
        "Host directory mounted at /output; every run writes its result files here. Must fall "
        "under the data root ($AGENTBOX_DATA). Default $AGENTBOX_DATA/outputs/<name>.",
        _ALL,
    ),
    # Environment (Job)
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
    # Tools & permissions (Job)
    SchemaField(
        "permission_mode", "tools", "Permission mode", "enum",
        "Claude Code permission mode.",
        ["claude-code"],
        choices=["default", "acceptEdits", "auto", "bypassPermissions", "dontAsk", "plan"],
    ),
    SchemaField(
        "allowed_tools", "tools", "Allowed tools", "list",
        "Tool allowlist.",
        ["claude-code", "pi"],
    ),
    SchemaField(
        "disallowed_tools", "tools", "Disallowed tools", "list",
        "Tool denylist (pi has no such flag).",
        ["claude-code"],
    ),
    SchemaField(
        "mcp_config", "tools", "MCP config", "path",
        "Path to an MCP server config JSON inside the container.",
        ["claude-code"],
    ),
    # Harness & model (Box)
    SchemaField(
        "harness", "harness_model", "Harness", "enum",
        "Which runtime runs this agent; determines the available fields and models. One of claude-code, pi, api, codex.",
        _ALL, required=True, choices=list(_ALL),
    ),
    SchemaField(
        "model", "harness_model", "Model", "string",
        "Model the harness talks to.",
        _ALL,
    ),
    SchemaField(
        "effort", "harness_model", "Effort", "enum",
        "Reasoning/thinking effort level.",
        ["claude-code", "pi", "codex"],
    ),
    SchemaField(
        "fallback_model", "harness_model", "Fallback model", "string",
        "Model to use if the primary is overloaded.",
        ["claude-code"],
    ),
    SchemaField(
        "max_tokens", "harness_model", "Max tokens", "int",
        "Cap on response tokens. 1 to 200000; default 1024.",
        ["api"], default=1024, min=1, max=200000,
    ),
    # Container (Box)
    SchemaField(
        "network", "container", "Network", "enum",
        "Docker network: agentnet-isolated (LiteLLM only, no internet), agentnet (LiteLLM + internet), "
        "bridge (full internet — needed by claude-code and codex). Default depends on harness.",
        _ALL, required=True, choices=["agentnet-isolated", "agentnet", "bridge"],
    ),
    SchemaField(
        "memory", "container", "Memory", "string",
        "Container memory limit (e.g. 512m, 1g). Default 1g.",
        _ALL, default="1g", pattern=r"^\d+[kmg]$",
    ),
    SchemaField(
        "cpus", "container", "CPUs", "number",
        "Container CPU limit (e.g. 1.5). 0.1 to 64; default 1.5.",
        _ALL, default=1.5, min=0.1, max=64,
    ),
]

FIELDS_BY_ID: dict[str, SchemaField] = {f.id: f for f in FIELDS}

# The always-written set (contract agent-yaml.md §4): these are emitted even when
# unset so the file documents the essentials.
ALWAYS_WRITTEN = {"name", "enabled", "harness", "prompt_file", "output_dir", "network"}


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


def is_valid_cron(value) -> bool:
    """Five fields, no @-macros — the trigger cron rule (contract agent-model §3).

    Twin of ``orchestrator/factory.py:is_valid_cron`` (separate containers, no shared import);
    this UI copy additionally runs ``croniter.is_valid`` as the stricter authoring guard. The
    same rule the retired ``automation_store`` cron guard used.
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s or s.startswith("@"):
        return False
    if len(s.split()) != 5:
        return False
    from croniter import croniter
    return croniter.is_valid(s)


def litellm_aliases() -> list[str]:
    """Model aliases pi/api agents may use, read from the rendered LiteLLM config.

    Reads ``config.LITELLM_RENDERED`` (produced by ``litellm/generate.py`` from the product
    template + instance overlay, US6). Falls back to the hardcoded default set when the file
    is missing or unreadable so the form still works before the config is generated.
    """
    try:
        with open(config.LITELLM_RENDERED) as f:
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

    null, empty list, empty map, and empty string are all unset. (Before spec 005,
    ``schedule`` treated an empty string as a real value for manual-only runs; with
    ``schedule`` gone, an empty string is unset for every field.)
    """
    if value is None:
        return True
    if f.type in ("list", "checks") and value == []:
        return True
    if f.type == "map" and value == {}:
        return True
    if isinstance(value, str) and value == "":
        return True
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


def _validate_checks(agent: dict, is_asset: bool, errors: dict) -> None:
    """Validate the `produces.checks` list (contract check-model §2/§3, FR-010).

    A single ``checks`` error message is set on the first offending item so the form can
    surface it; the orchestrator's ``validate_checks`` is the structural backstop at load.
    Checks require a valid asset, each needs a kebab ``name`` (unique) and a non-empty
    ``command``, and the optional fields must be well-typed / in range.
    """
    if "checks" in errors:
        return
    checks = agent.get("checks")
    if checks is None or checks == []:
        return
    if not isinstance(checks, list):
        errors["checks"] = "checks must be a list of check objects"
        return
    if not is_asset:
        errors["checks"] = "checks require an asset — declare an asset key above"
        return
    seen: set[str] = set()
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            errors["checks"] = f"check #{i + 1} must be a mapping with a name and a command"
            return
        name = c.get("name")
        if not name or not isinstance(name, str):
            errors["checks"] = f"check #{i + 1} is missing a name"
            return
        if not _NAME_RE.match(name):
            errors["checks"] = f'check "{name}": name must be kebab-case (lowercase letters and digits, single hyphens)'
            return
        if name in seen:
            errors["checks"] = f'duplicate check name "{name}" — check names must be unique within the agent'
            return
        seen.add(name)
        command = c.get("command")
        if not command or not isinstance(command, str) or not command.strip():
            errors["checks"] = f'check "{name}" is missing a command'
            return
        if "image" in c and not (isinstance(c["image"], str) and c["image"].strip()):
            errors["checks"] = f'check "{name}": image must be a non-empty string'
            return
        if "blocking" in c and not isinstance(c["blocking"], bool):
            errors["checks"] = f'check "{name}": blocking must be true or false'
            return
        if "timeout_seconds" in c:
            ts = c["timeout_seconds"]
            if not isinstance(ts, int) or isinstance(ts, bool) or ts < 1 or ts > 86400:
                errors["checks"] = f'check "{name}": timeout_seconds must be a whole number between 1 and 86400'
                return
        if "network" in c and c["network"] not in CHECK_NETWORKS:
            errors["checks"] = f'check "{name}": network must be one of {", ".join(CHECK_NETWORKS)}'
            return


# Config-path fields whose value must resolve under the data root, never the product tree
# (FR-025, contract path-validation §1). mcp_config is a container-internal path and is not
# checked here.
_PATH_ROOTED_FIELDS = ("output_dir", "workspace", "env_file")


def _is_under(path: str, root: str) -> bool:
    """Whether ``path`` is ``root`` itself or lives beneath it."""
    return path == root or path.startswith(root.rstrip("/") + "/")


def _documented_default_paths(name: str, data_root: str) -> set[str]:
    """The documented default ``output_dir``/``workspace`` for ``name`` (contract §1).

    Both fall under the data root, so they already satisfy the data-root rule; listing them
    keeps the acceptance explicit and independent of any future default-path placement.
    """
    return {
        os.path.join(data_root, "outputs", name),
        os.path.join(data_root, "workspaces", name),
    }


def _validate_paths(agent: dict, applicable: set[str], errors: dict) -> None:
    """Reject config paths that point into the product tree or outside the data root (FR-025).

    For each of ``output_dir``/``workspace``/``env_file`` that is present, applicable, and not
    already flagged: a value under the product tree, or an absolute path outside the data root
    that is not a documented default, is rejected with a message naming the field (via the error
    key) and stating the data-root rule (contract path-validation §1). Omitted values and the
    documented defaults are accepted. Roots come from the UI's single resolution point
    (``config.PRODUCT_ROOT``/``config.DATA_ROOT``), read at call time so tests can monkeypatch
    them — the same "read from config" style as ``prompt_exists`` injection.
    """
    product_root = config.PRODUCT_ROOT
    data_root = config.DATA_ROOT
    name = str(agent.get("name") or "")
    defaults = _documented_default_paths(name, data_root)
    for fid in _PATH_ROOTED_FIELDS:
        if fid not in applicable or fid in errors:
            continue
        f = FIELDS_BY_ID[fid]
        if fid not in agent or _is_unset(f, agent.get(fid)):
            continue  # omitted → the documented default applies (accept)
        val = agent[fid]
        if not isinstance(val, str):
            errors[fid] = "must be a filesystem path"
            continue
        if val in defaults:
            continue  # the documented default is always accepted
        if _is_under(val, product_root):
            errors[fid] = (
                f'must fall under the data root ($AGENTBOX_DATA); "{val}" is under the product tree'
            )
        elif not _is_under(val, data_root):
            errors[fid] = (
                f'must fall under the data root ($AGENTBOX_DATA); "{val}" is outside the data root'
            )


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

    # Config paths must resolve under the data root, never the product tree (FR-025, US5).
    _validate_paths(agent, applicable, errors)

    pf = agent.get("prompt_file")
    if pf and "prompt_file" not in errors and not prompt_exists(str(pf)):
        errors["prompt_file"] = f"no such prompt file in prompts/: {pf}"

    # A produces block that names no asset is an empty declaration (contract §3 rule 2 / FR-002).
    # The asset card sends `asset` (possibly empty) when it is on; a genuinely empty declaration
    # is flagged so it cannot be saved.
    if "asset" in agent and "asset" not in errors and _is_unset(FIELDS_BY_ID["asset"], agent.get("asset")):
        errors["asset"] = "an asset declaration must name an asset"

    # An agent's nature is explicit and at-least-one (contract §3 rule 1 / FR-005).
    is_asset = not _is_unset(FIELDS_BY_ID["asset"], agent.get("asset"))
    is_job = agent.get("job") is True
    if not is_asset and not is_job and "job" not in errors:
        errors["job"] = "the agent must be an asset, a job, or both."

    # produces.checks — a list of pass/fail check objects (contract check-model §2/§3, FR-010).
    _validate_checks(agent, is_asset, errors)

    # Trigger crons: five-field shape, and each applies only to its kind (contract §3 rules 3/4).
    for sid, kind_on, kind_msg in (
        ("asset_schedule", is_asset, "asset_schedule applies only when the agent is an asset"),
        ("job_schedule", is_job, "job_schedule applies only when the agent has a job"),
    ):
        f = FIELDS_BY_ID[sid]
        if sid not in agent or _is_unset(f, agent.get(sid)) or sid in errors:
            continue
        if not kind_on:
            errors[sid] = kind_msg
        elif not is_valid_cron(agent[sid]):
            errors[sid] = "cron must have exactly five fields and no @-macros"

    # depends_on — a list of asset keys; each must match ASSET_KEY_RE and the field needs an asset
    # (contract agent-model §3 rule 1 / FR-001/FR-002). Existence + acyclicity across agents are
    # enforced at load (orchestrator §4); the UI additionally cross-checks them when it can (§3).
    dep_f = FIELDS_BY_ID["depends_on"]
    if "depends_on" in agent and not _is_unset(dep_f, agent.get("depends_on")) and "depends_on" not in errors:
        dep = agent["depends_on"]
        if not isinstance(dep, list):
            errors["depends_on"] = "depends_on must be a list of asset keys"
        elif not is_asset:
            errors["depends_on"] = "depends_on requires an asset — declare an asset key above."
        else:
            for entry in dep:
                if not isinstance(entry, str) or not re.match(ASSET_KEY_RE, entry):
                    errors["depends_on"] = (
                        f"invalid depends_on entry {entry!r} — each must be an asset key "
                        "(kebab segments joined by /)"
                    )
                    break

    # on_upstream / on_missing are asset-kind trigger flags — they apply only when the agent is an
    # asset (contract agent-model §3 rule 2 / FR-005/FR-009, mirror of the asset_schedule rule).
    # The bool type is already enforced above; here only the kind rule is added. A falsey flag is
    # off (the default), so only a truthy flag on a non-asset agent is rejected.
    for tid, msg in (
        ("on_upstream", "on_upstream applies only when the agent is an asset"),
        ("on_missing", "on_missing applies only when the agent is an asset"),
    ):
        if tid in errors:
            continue
        if agent.get(tid) is True and not is_asset:
            errors[tid] = msg

    return errors


def check_depends_on_graph(asset_key: str, depends_on: list, other_edges: dict) -> str | None:
    """Best-effort author-time cross-check of a `depends_on` graph (spec 013 §3 / FR-002/FR-003).

    Given the asset key being saved, its proposed ``depends_on``, and ``other_edges`` — the known
    graph ``{asset_key: [upstream keys]}`` of every OTHER agent — return a clear message when an
    entry names an asset key produced by no known agent, or when the new edges would form a cycle
    (direct or transitive); else ``None``. The load-time check (orchestrator ``definitions.discover``)
    remains the authority — this only lets the form tell the operator immediately.
    """
    if not depends_on:
        return None
    graph = dict(other_edges)
    graph[asset_key] = list(depends_on)
    produced = set(graph)
    for dep in depends_on:
        if dep not in produced:
            return f"depends_on names an unknown asset key: {dep}"
    # A new cycle must run through asset_key: can we get back to it by following its deps' edges?
    seen: set[str] = set()
    stack = list(depends_on)
    while stack:
        cur = stack.pop()
        if cur == asset_key:
            return f"depends_on forms a dependency cycle involving {asset_key}"
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, []))
    return None


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
    if f.block:
        out["block"] = f.block
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
        "groups": [dict(g) for g in GROUPS],
        "sections": [dict(s) for s in SECTIONS],
        "fields": [_field_public(f) for f in FIELDS],
        "harnesses": [_harness_public(h) for h in HARNESSES],
    }
