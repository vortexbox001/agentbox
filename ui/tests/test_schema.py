"""Tests for the schema module: field matrix, validation, migrations, aliases."""
import pytest

import schema


ALWAYS_TRUE = lambda name: True


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


# ── Migrations ──────────────────────────────────────────
def test_migrations_noop_at_current_version():
    data = {"name": "x", "harness": "api"}
    assert schema.apply_migrations(dict(data), schema.SCHEMA_VERSION) == data
    assert schema.apply_migrations(dict(data), 0) == data


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
