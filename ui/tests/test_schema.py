"""Tests for the schema module: field matrix, validation, migrations, aliases."""
import re

import pytest

import schema


ALWAYS_TRUE = lambda name: True

# The asset-key regex is stated once per package (research R6). These shared fixtures are
# duplicated verbatim in orchestrator/tests/test_factory.py so the two copies cannot drift.
ASSET_KEY_EXPECTED_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"
ASSET_KEY_ACCEPT = ["repo-review/agentbox", "code-map/agentbox", "a", "a-b/c-d/e", "x1/y2"]
ASSET_KEY_REJECT = ["Bad Key", "", "/leading", "trailing/", "Repo/Agentbox", "a//b",
                    "a_b", "a b", "-x", "x-", "a-/b"]


def test_asset_key_regex_pinned_to_shared_fixtures():
    assert schema.ASSET_KEY_RE == ASSET_KEY_EXPECTED_RE
    for s in ASSET_KEY_ACCEPT:
        assert re.match(schema.ASSET_KEY_RE, s), f"should accept {s!r}"
    for s in ASSET_KEY_REJECT:
        assert not re.match(schema.ASSET_KEY_RE, s), f"should reject {s!r}"


def _base(harness, **over):
    """A minimal valid agent for a harness, overridable per test."""
    a = {
        "name": "an-agent", "enabled": True, "harness": harness,
        "prompt_file": "p.md", "output_dir": "/data/outputs/an-agent",
        "network": schema.HARNESS_BY_ID[harness]["default_network"], "schedule": "",
    }
    if harness == "api":
        a["model"] = "cheap"
    elif harness == "pi":
        a["model"] = "smart"
    elif harness == "claude-code":
        a["model"] = "sonnet"
    a.update(over)
    return a


# ── Field applicability matrix (data-model.md) ──────────
def test_env_file_applies_to_all_harnesses():
    for h in ("claude-code", "pi", "api", "codex"):
        assert "env_file" in schema.applicable_fields(h)
        assert "env" in schema.applicable_fields(h)


def test_effort_absent_for_api_present_elsewhere():
    assert "effort" not in schema.applicable_fields("api")
    for h in ("claude-code", "pi", "codex"):
        assert "effort" in schema.applicable_fields(h)


def test_allowed_tools_absent_for_codex_and_api():
    assert "allowed_tools" not in schema.applicable_fields("codex")
    assert "allowed_tools" not in schema.applicable_fields("api")
    assert "allowed_tools" in schema.applicable_fields("claude-code")
    assert "allowed_tools" in schema.applicable_fields("pi")


def test_api_field_set_matches_factory_branches():
    fields = set(schema.applicable_fields("api"))
    assert "max_tokens" in fields
    assert "workspace" not in fields
    assert "append_system_prompt" not in fields
    assert "max_turns" not in fields


def test_claude_only_fields():
    cc = set(schema.applicable_fields("claude-code"))
    for fid in ("fallback_model", "max_turns", "permission_mode", "disallowed_tools", "mcp_config"):
        assert fid in cc
    # none of these leak to other harnesses
    for h in ("pi", "api", "codex"):
        assert not ({"fallback_model", "max_turns", "permission_mode", "mcp_config"} & set(schema.applicable_fields(h)))


# ── Model rule table (research R4) ──────────────────────
@pytest.mark.parametrize("harness,model,ok", [
    ("claude-code", "sonnet", True),
    ("claude-code", "claude-opus-4-8[1m]", True),
    ("claude-code", "claude-sonnet-5", True),
    ("claude-code", "gpt-4", False),
    ("claude-code", "", True),            # blank = CLI default
    ("pi", "kimi", True),                 # a LiteLLM alias
    ("pi", "openai/gpt-x", True),         # provider/model passthrough
    ("pi", "nonsense", False),            # not an alias and no slash
    ("pi", "", True),
    ("api", "cheap", True),
    ("api", "openai/gpt-x", False),       # api is select-only
    ("api", "", False),                   # api requires a model
    ("codex", "gpt-6-astra", True),       # any non-empty string
    ("codex", "", True),                  # blank = codex default
])
def test_model_rule(settings, harness, model, ok):
    agent = _base(harness, model=model)
    errors = schema.validate(agent, prompt_exists=ALWAYS_TRUE)
    assert ("model" not in errors) == ok, errors


# ── Cron table (research R6) ────────────────────────────
@pytest.mark.parametrize("expr,ok", [
    ("0 7 * * *", True),
    ("*/30 * * * *", True),
    ("", True),                # manual-only
    ("@daily", False),         # macros rejected
    ("0 0 7 * * *", False),    # 6 fields rejected
    ("nonsense here now ok", False),
])
def test_cron(settings, expr, ok):
    agent = _base("api", schedule=expr)
    errors = schema.validate(agent, prompt_exists=ALWAYS_TRUE)
    assert ("schedule" not in errors) == ok, errors


# ── Other validation ────────────────────────────────────
def test_memory_pattern_and_ranges(settings):
    bad = _base("api", memory="lots", cpus=100, timeout_seconds=0, max_tokens=999999)
    errors = schema.validate(bad, prompt_exists=ALWAYS_TRUE)
    assert "memory" in errors and "cpus" in errors and "timeout_seconds" in errors and "max_tokens" in errors


def test_name_pattern(settings):
    assert "name" in schema.validate(_base("api", name="Not Valid"), prompt_exists=ALWAYS_TRUE)
    assert "name" not in schema.validate(_base("api", name="ok-name-9"), prompt_exists=ALWAYS_TRUE)


def test_env_key_pattern(settings):
    errors = schema.validate(_base("api", env={"lower_case": "x", "GOOD": "y"}), prompt_exists=ALWAYS_TRUE)
    assert "env" in errors


def test_prompt_existence_uses_callable(settings):
    agent = _base("api", prompt_file="missing.md")
    assert "prompt_file" in schema.validate(agent, prompt_exists=lambda n: False)
    assert "prompt_file" not in schema.validate(agent, prompt_exists=lambda n: True)


def test_unknown_harness_reported(settings):
    errors = schema.validate({"name": "x", "harness": "bogus", "prompt_file": "p.md",
                              "output_dir": "/o", "network": "agentnet", "enabled": True},
                             prompt_exists=ALWAYS_TRUE)
    assert "harness" in errors


# ── Produces block (US3, contract schema-and-yaml §2/§5) ─
def test_produces_section_is_a_runs_card():
    sec = next((s for s in schema.SECTIONS if s["id"] == "produces"), None)
    assert sec == {"id": "produces", "label": "Produces", "group": "runs"}


def test_asset_and_partition_apply_to_every_harness():
    for h in ("claude-code", "pi", "api", "codex"):
        fields = schema.applicable_fields(h)
        assert "asset" in fields and "partition" in fields


def test_asset_field_shape():
    f = schema.FIELDS_BY_ID["asset"]
    assert f.section == "produces" and f.block == "produces"
    assert f.type == "string"
    assert f.pattern == schema.ASSET_KEY_RE
    assert "repo-review/agentbox" in f.help


def test_partition_field_shape():
    f = schema.FIELDS_BY_ID["partition"]
    assert f.section == "produces" and f.block == "produces"
    assert f.type == "enum"
    assert f.choices == ["none", "daily"]
    assert f.default == "none"


def test_public_payload_exposes_produces():
    pub = schema.to_public()
    assert pub["schema_version"] == 2
    assert {"id": "produces", "label": "Produces", "group": "runs"} in pub["sections"]
    by_id = {f["id"]: f for f in pub["fields"]}
    assert by_id["asset"]["pattern"] == schema.ASSET_KEY_RE
    assert by_id["partition"]["choices"] == ["none", "daily"]
    # every harness's field list carries both
    for h in pub["harnesses"]:
        assert "asset" in h["fields"] and "partition" in h["fields"]


# ── Validation of the produces block (US4, contract §4) ──
def test_validate_accepts_valid_asset_and_partition():
    a = _base("api", asset="repo-review/agentbox", partition="daily")
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


def test_validate_rejects_bad_asset_key():
    a = _base("api", asset="Bad Key")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "asset" in errors


def test_validate_rejects_empty_declaration():
    # produces present but no asset (surfaced by the reader as an empty asset).
    a = _base("api", asset="")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "asset" in errors


def test_validate_rejects_bad_partition():
    a = _base("api", asset="repo-review/agentbox", partition="hourly")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "partition" in errors


def test_validate_no_asset_key_is_not_an_error():
    # A plain agent (no asset field at all) stays a job with no produces error.
    a = _base("api")
    assert "asset" not in schema.validate(a, prompt_exists=ALWAYS_TRUE)


# ── Migrations ──────────────────────────────────────────
def test_schema_version_is_two():
    assert schema.SCHEMA_VERSION == 2


def test_migrations_noop_at_current_version():
    data = {"name": "x", "harness": "api"}
    assert schema.apply_migrations(dict(data), schema.SCHEMA_VERSION) == data
    assert schema.apply_migrations(dict(data), 0) == data


def test_migrate_1_to_2_is_identity(settings):
    # SC-005: a schema-1 agent (no produces) migrates to 2 unchanged, no transform.
    data = {"name": "x", "harness": "api", "model": "cheap",
            "prompt_file": "p.md", "output_dir": "/o"}
    migrated = schema.apply_migrations(dict(data), 1)
    assert migrated == data
    assert "produces" not in migrated and "asset" not in migrated


def test_schema_too_new_raises():
    with pytest.raises(schema.SchemaTooNew):
        schema.apply_migrations({}, schema.SCHEMA_VERSION + 1)


# ── litellm aliases ─────────────────────────────────────
def test_litellm_aliases_reads_config(settings):
    aliases = schema.litellm_aliases()
    assert "cheap" in aliases and "kimi" in aliases


def test_litellm_aliases_fallback_when_missing(settings, monkeypatch):
    monkeypatch.setattr(schema.config, "LITELLM_CONFIG", "/nonexistent/config.yaml")
    assert schema.litellm_aliases() == ["cheap", "smart", "opus", "kimi", "kimi-k3"]


# ── Network mismatch warnings (FR-024) ──────────────────
@pytest.mark.parametrize("harness,network,warns", [
    ("claude-code", "bridge", False),
    ("claude-code", "agentnet-isolated", True),
    ("codex", "agentnet", True),
    ("pi", "agentnet", False),
    ("api", "agentnet-isolated", False),
    ("api", "bridge", True),
])
def test_network_mismatch_warning(harness, network, warns):
    msg = schema.network_mismatch_warning({"harness": harness, "network": network})
    assert (msg is not None) == warns


# ── Public payload shape ────────────────────────────────
def test_to_public_shape(settings):
    pub = schema.to_public()
    assert {"sections", "fields", "harnesses"} <= set(pub)
    assert len(pub["harnesses"]) == 4
    pi = next(h for h in pub["harnesses"] if h["id"] == "pi")
    # pi's model choices are resolved from the live litellm alias list
    assert "cheap" in pi["model_rule"]["choices"]
    cc = next(h for h in pub["harnesses"] if h["id"] == "claude-code")
    assert cc["model_rule"]["choices"] == ["sonnet", "opus", "haiku", "fable"]


# ── Groups, sections, and field re-homing (003 data-model.md) ──
# The section each field must live in after the 003 regrouping (data-model.md
# "Field re-homing"). Every managed field appears exactly once.
_FIELD_SECTION = {
    "name": "identity",
    "enabled": "schedule",
    "schedule": "schedule",
    "timeout_seconds": "limits",
    "max_turns": "limits",
    "asset": "produces",
    "partition": "produces",
    "prompt_file": "prompt",
    "append_system_prompt": "prompt",
    "workspace": "directories",
    "wipe_workspace": "directories",
    "output_dir": "directories",
    "env_file": "environment",
    "env": "environment",
    "permission_mode": "tools",
    "allowed_tools": "tools",
    "disallowed_tools": "tools",
    "mcp_config": "tools",
    "harness": "harness_model",
    "model": "harness_model",
    "effort": "harness_model",
    "fallback_model": "harness_model",
    "max_tokens": "harness_model",
    "network": "container",
    "memory": "container",
    "cpus": "container",
}


def test_groups_are_runs_job_box_in_order():
    assert [g["id"] for g in schema.GROUPS] == ["runs", "job", "box"]
    assert [g["label"] for g in schema.GROUPS] == ["Runs", "Job", "Box"]


def test_every_section_group_is_valid_and_one_is_lead():
    group_ids = {g["id"] for g in schema.GROUPS}
    lead = [s for s in schema.SECTIONS if s["group"] is None]
    assert [s["id"] for s in lead] == ["identity"]   # exactly one, and it is identity
    for s in schema.SECTIONS:
        assert s["group"] is None or s["group"] in group_ids, s


def test_every_field_section_names_a_section():
    section_ids = {s["id"] for s in schema.SECTIONS}
    for f in schema.FIELDS:
        assert f.section in section_ids, f"{f.id} → unknown section {f.section}"


def test_fields_contiguous_by_section_in_sections_order():
    order = [s["id"] for s in schema.SECTIONS]
    seen: list[str] = []
    for f in schema.FIELDS:
        if not seen or seen[-1] != f.section:
            seen.append(f.section)
    # Each section id appears once in FIELDS, in SECTIONS order (contiguous blocks).
    assert seen == [sid for sid in order if any(fl.section == sid for fl in schema.FIELDS)]
    assert seen == order   # every section has at least one field


def test_field_re_homing_matches_data_model():
    assert {f.id for f in schema.FIELDS} == set(_FIELD_SECTION)
    for f in schema.FIELDS:
        assert f.section == _FIELD_SECTION[f.id], f"{f.id} in {f.section}, expected {_FIELD_SECTION[f.id]}"


def test_to_public_exposes_groups_and_section_group():
    pub = schema.to_public()
    assert [g["id"] for g in pub["groups"]] == ["runs", "job", "box"]
    for s in pub["sections"]:
        assert "group" in s
    identity = next(s for s in pub["sections"] if s["id"] == "identity")
    assert identity["group"] is None
