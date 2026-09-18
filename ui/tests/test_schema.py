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
        # under the default data root ($AGENTBOX_DATA=/data/agentbox) so validate() is clean
        # both with and without the `settings` fixture (which repoints the data root to /data).
        "prompt_file": "p.md", "output_dir": "/data/agentbox/outputs/an-agent",
        "network": schema.HARNESS_BY_ID[harness]["default_network"],
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


# The old top-level `schedule` field is gone (spec 005). Spec 006 put per-kind cron fields
# (asset_schedule / job_schedule) back on the agent, in its `triggers:` block; their five-field
# rule is exercised by the trigger tests below and in test_automation_store.py.


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
    assert pub["schema_version"] == 8
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


# ── depends_on + the two asset-kind triggers (spec 013, contract agent-model §2/§3) ──
def test_depends_on_and_triggers_present_in_fields():
    for fid, block in (("depends_on", "produces"), ("on_upstream", "triggers"),
                       ("on_missing", "triggers")):
        f = schema.FIELDS_BY_ID[fid]
        assert f.block == block and f.section == block
        assert f.harnesses == schema._ALL
    assert schema.FIELDS_BY_ID["depends_on"].type == "list"
    assert schema.FIELDS_BY_ID["on_upstream"].type == "bool"
    assert schema.FIELDS_BY_ID["on_missing"].type == "bool"
    assert schema.FIELDS_BY_ID["on_upstream"].default is False
    assert schema.FIELDS_BY_ID["on_missing"].default is False


def test_public_payload_exposes_depends_on_and_triggers():
    pub = schema.to_public()
    by_id = {f["id"]: f for f in pub["fields"]}
    assert by_id["depends_on"]["type"] == "list" and by_id["depends_on"]["block"] == "produces"
    assert by_id["on_upstream"]["type"] == "bool" and by_id["on_upstream"]["block"] == "triggers"
    assert by_id["on_missing"]["type"] == "bool" and by_id["on_missing"]["block"] == "triggers"
    for h in pub["harnesses"]:
        assert {"depends_on", "on_upstream", "on_missing"} <= set(h["fields"])


def test_depends_on_accepts_asset_key_entries():
    a = _base("api", asset="refined/daily", depends_on=["notes/daily", "extras/daily"])
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


def test_depends_on_rejects_bad_entry_naming_it():
    a = _base("api", asset="refined/daily", depends_on=["notes/daily", "Bad Key"])
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "depends_on" in errors and "Bad Key" in errors["depends_on"]


def test_depends_on_requires_an_asset():
    a = _base("api", job=True, depends_on=["notes/daily"])
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "depends_on" in errors


def test_on_upstream_and_on_missing_apply_only_to_assets():
    a = _base("api", job=True, on_upstream=True, on_missing=True)
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "on_upstream" in errors and "on_missing" in errors


def test_on_upstream_and_on_missing_ok_for_asset():
    a = _base("api", asset="refined/daily", on_upstream=True, on_missing=True)
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


def test_trigger_flags_must_be_bool():
    a = _base("api", asset="refined/daily", on_upstream="yes")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "on_upstream" in errors


# ── author-time depends_on cross-check (spec 013 §3, US4) ──
def test_check_graph_accepts_acyclic_known_refs():
    others = {"notes/daily": [], "extras/daily": []}
    assert schema.check_depends_on_graph("refined/daily", ["notes/daily", "extras/daily"], others) is None


def test_check_graph_blocks_unknown_asset_key():
    others = {"notes/daily": []}
    msg = schema.check_depends_on_graph("refined/daily", ["ghost/daily"], others)
    assert msg and "ghost/daily" in msg


def test_check_graph_blocks_direct_cycle():
    # saving b/x depends_on c/y while c/y already depends_on b/x forms a cycle.
    others = {"c/y": ["b/x"]}
    msg = schema.check_depends_on_graph("b/x", ["c/y"], others)
    assert msg and "cycle" in msg


def test_check_graph_blocks_self_cycle():
    msg = schema.check_depends_on_graph("a/b", ["a/b"], {})
    assert msg and "cycle" in msg


def test_check_graph_none_when_no_depends_on():
    assert schema.check_depends_on_graph("a/b", [], {"x/y": []}) is None


def test_validate_rejects_bad_partition():
    a = _base("api", asset="repo-review/agentbox", partition="hourly")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "partition" in errors


def test_validate_no_asset_key_is_not_an_error():
    # A plain agent (job) has no produces error on the asset field.
    a = _base("api", job=True)
    assert "asset" not in schema.validate(a, prompt_exists=ALWAYS_TRUE)


# ── produces.checks validation (spec 008, contract check-model §2/§3) ──
def _with_checks(checks, **over):
    return _base("api", asset="verify/checks", checks=checks, **over)


def test_checks_field_shape():
    f = schema.FIELDS_BY_ID["checks"]
    assert f.section == "produces" and f.block == "produces" and f.type == "checks"


def test_validate_accepts_valid_checks():
    a = _with_checks([
        {"name": "has-output", "command": "test -n \"$(ls /output)\""},
        {"name": "advisory", "command": "false", "blocking": False},
        {"name": "slow", "command": "sleep 1", "timeout_seconds": 2, "network": "agentnet"},
    ])
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


def test_validate_rejects_checks_without_asset():
    a = _base("api", job=True, checks=[{"name": "c", "command": "true"}])
    assert "checks" in schema.validate(a, prompt_exists=ALWAYS_TRUE)


def test_validate_rejects_check_missing_name_or_command():
    assert "checks" in schema.validate(_with_checks([{"command": "true"}]), prompt_exists=ALWAYS_TRUE)
    assert "checks" in schema.validate(_with_checks([{"name": "c"}]), prompt_exists=ALWAYS_TRUE)
    assert "checks" in schema.validate(_with_checks([{"name": "c", "command": "  "}]), prompt_exists=ALWAYS_TRUE)


def test_validate_rejects_bad_check_name():
    assert "checks" in schema.validate(_with_checks([{"name": "Bad Name", "command": "true"}]),
                                       prompt_exists=ALWAYS_TRUE)


def test_validate_rejects_duplicate_check_names():
    a = _with_checks([{"name": "c", "command": "true"}, {"name": "c", "command": "false"}])
    assert "checks" in schema.validate(a, prompt_exists=ALWAYS_TRUE)


def test_validate_rejects_bad_check_optional_fields():
    assert "checks" in schema.validate(
        _with_checks([{"name": "c", "command": "true", "timeout_seconds": 0}]), prompt_exists=ALWAYS_TRUE)
    assert "checks" in schema.validate(
        _with_checks([{"name": "c", "command": "true", "timeout_seconds": 999999}]), prompt_exists=ALWAYS_TRUE)
    assert "checks" in schema.validate(
        _with_checks([{"name": "c", "command": "true", "network": "wan"}]), prompt_exists=ALWAYS_TRUE)
    assert "checks" in schema.validate(
        _with_checks([{"name": "c", "command": "true", "blocking": "yes"}]), prompt_exists=ALWAYS_TRUE)


def test_validate_empty_checks_list_is_fine():
    a = _base("api", asset="verify/checks", checks=[])
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


# ── Job flag + triggers block (spec 006, contract agent-model §1/§2/§3) ──
def test_job_field_shape():
    f = schema.FIELDS_BY_ID["job"]
    assert f.section == "run_as_job" and f.type == "bool"
    assert f.default is False
    assert "job" not in schema.ALWAYS_WRITTEN


def test_trigger_fields_shape():
    for sid in ("asset_schedule", "job_schedule"):
        f = schema.FIELDS_BY_ID[sid]
        assert f.section == "triggers" and f.block == "triggers" and f.type == "cron"
    for h in ("claude-code", "pi", "api", "codex"):
        fields = schema.applicable_fields(h)
        assert "job" in fields and "asset_schedule" in fields and "job_schedule" in fields


def test_triggers_section_is_a_runs_card_and_job_is_a_job_card():
    triggers = next(s for s in schema.SECTIONS if s["id"] == "triggers")
    job = next(s for s in schema.SECTIONS if s["id"] == "run_as_job")
    assert triggers == {"id": "triggers", "label": "Triggers", "group": "runs"}
    assert job == {"id": "run_as_job", "label": "Job", "group": "job"}


def test_public_payload_exposes_job_and_triggers():
    by_id = {f["id"]: f for f in schema.to_public()["fields"]}
    assert by_id["job"]["type"] == "bool"
    assert by_id["asset_schedule"]["type"] == "cron" and by_id["asset_schedule"]["block"] == "triggers"
    assert by_id["job_schedule"]["type"] == "cron" and by_id["job_schedule"]["block"] == "triggers"


# Rule 1 — nature invariant (FR-005)
def test_nature_invariant_requires_asset_or_job():
    neither = _base("api")  # no produces, no job
    errors = schema.validate(neither, prompt_exists=ALWAYS_TRUE)
    assert errors.get("job") == "the agent must be an asset, a job, or both."
    # A job satisfies it; so does an asset; so does both.
    assert "job" not in schema.validate(_base("api", job=True), prompt_exists=ALWAYS_TRUE)
    assert "job" not in schema.validate(_base("api", asset="a/b"), prompt_exists=ALWAYS_TRUE)
    assert "job" not in schema.validate(_base("api", asset="a/b", job=True), prompt_exists=ALWAYS_TRUE)


# Rule 3 — cron shape on the trigger fields
def test_trigger_cron_shape_validated():
    bad = _base("api", job=True, job_schedule="@daily")
    assert "job_schedule" in schema.validate(bad, prompt_exists=ALWAYS_TRUE)
    ok = _base("api", job=True, job_schedule="30 2 * * *")
    assert "job_schedule" not in schema.validate(ok, prompt_exists=ALWAYS_TRUE)
    bad_asset = _base("api", asset="a/b", asset_schedule="1 2 3")
    assert "asset_schedule" in schema.validate(bad_asset, prompt_exists=ALWAYS_TRUE)


# Rule 4 — a schedule whose kind is off is rejected by name
def test_asset_schedule_on_non_asset_is_rejected():
    a = _base("api", job=True, asset_schedule="30 2 * * *")  # a job, not an asset
    assert "asset_schedule" in schema.validate(a, prompt_exists=ALWAYS_TRUE)


def test_job_schedule_on_non_job_is_rejected():
    a = _base("api", asset="a/b", job_schedule="30 2 * * *")  # an asset, no job
    assert "job_schedule" in schema.validate(a, prompt_exists=ALWAYS_TRUE)


# ── Config-path validation against the roots (US5, contract path-validation §1) ──
def _paths_settings(monkeypatch):
    """Pin the product/data roots the path rule reads, independent of the ambient env."""
    import config
    monkeypatch.setattr(config, "PRODUCT_ROOT", "/opt/agentbox")
    monkeypatch.setattr(config, "DATA_ROOT", "/data/agentbox")
    return config


def test_output_dir_under_product_tree_rejected(monkeypatch):
    # R-PV-1 (SC-006): an output_dir under the product tree is rejected, naming the field
    # (the error key) and stating the data-root rule.
    _paths_settings(monkeypatch)
    a = _base("api", output_dir="/opt/agentbox/outputs/x")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "output_dir" in errors
    assert "$AGENTBOX_DATA" in errors["output_dir"]
    assert "product tree" in errors["output_dir"]


@pytest.mark.parametrize("field", ["output_dir", "workspace", "env_file"])
def test_field_under_product_tree_rejected(monkeypatch, field):
    # R-PV-1: each of the three path fields is rejected under the product tree.
    _paths_settings(monkeypatch)
    a = _base("claude-code", **{field: "/opt/agentbox/x"})
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert field in errors and "product tree" in errors[field]


def test_path_outside_data_root_rejected(monkeypatch):
    # R-PV-1: an absolute path that is neither under the data root nor a documented default.
    _paths_settings(monkeypatch)
    a = _base("api", output_dir="/mnt/elsewhere/x")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "output_dir" in errors and "$AGENTBOX_DATA" in errors["output_dir"]


@pytest.mark.parametrize("field", ["output_dir", "workspace", "env_file"])
def test_path_under_data_root_accepted(monkeypatch, field):
    # R-PV-2: a path under the data root is accepted for each field.
    _paths_settings(monkeypatch)
    a = _base("claude-code", **{field: f"/data/agentbox/custom/{field}"})
    assert field not in schema.validate(a, prompt_exists=ALWAYS_TRUE)


@pytest.mark.parametrize("field", ["output_dir", "workspace", "env_file"])
def test_path_omitted_accepted(monkeypatch, field):
    # R-PV-2: an omitted path is accepted (the documented default applies).
    _paths_settings(monkeypatch)
    a = _base("claude-code")
    a.pop(field, None)
    assert field not in schema.validate(a, prompt_exists=ALWAYS_TRUE)


def test_documented_default_paths_accepted(monkeypatch):
    # R-PV-2: the documented defaults ($AGENTBOX_DATA/outputs|workspaces/<name>) are accepted.
    _paths_settings(monkeypatch)
    a = _base("claude-code", output_dir="/data/agentbox/outputs/an-agent",
              workspace="/data/agentbox/workspaces/an-agent")
    errors = schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert "output_dir" not in errors and "workspace" not in errors


def test_output_dir_no_longer_required(monkeypatch):
    # FR-026: output_dir is optional now (was required=True); an agent omitting it is valid.
    _paths_settings(monkeypatch)
    a = _base("api", job=True)
    a.pop("output_dir", None)
    assert "output_dir" not in schema.validate(a, prompt_exists=ALWAYS_TRUE)
    assert schema.FIELDS_BY_ID["output_dir"].required is False


# ── Migrations ──────────────────────────────────────────
def test_schema_version_is_eight():
    assert schema.SCHEMA_VERSION == 8


def test_migrate_6_to_7_is_identity():
    # spec 013: produces.depends_on + triggers.on_upstream/on_missing are additive, so 6->7 leaves
    # a schema-6 file untouched (identity), same posture as migrate_4_to_5 / migrate_5_to_6.
    data = {"name": "x", "harness": "api", "produces": {"asset": "a/b"},
            "triggers": {"asset_schedule": "0 6 * * *"}}
    assert schema.migrate_6_to_7(dict(data)) == data


def test_migrate_4_to_5_is_identity():
    # spec 008: produces.checks is additive, so 4->5 leaves a schema-4 file untouched.
    data = {"name": "x", "harness": "api", "produces": {"asset": "a/b"}}
    assert schema.migrate_4_to_5(dict(data)) == data


def test_migrate_5_to_6_is_identity():
    # spec 010 FR-026: output_dir became optional and roots are env-resolved, but no field is
    # renamed or moved, so 5->6 leaves a schema-5 file (explicit output_dir included) untouched.
    data = {"name": "x", "harness": "api", "output_dir": "/data/agentbox/outputs/x",
            "produces": {"asset": "a/b"}}
    assert schema.migrate_5_to_6(dict(data)) == data


def test_migrate_2_to_3_drops_schedule(settings):
    # spec 005 FR-002: `schedule` left the schema; the 2->3 migration drops any lingering key
    # and does NOT turn it into a trigger. The 3->4 migration then makes the (produces-less)
    # agent an explicit job (spec 006). A schema-2 file without `schedule` is likewise made a job.
    assert schema.apply_migrations({"name": "x", "harness": "api", "schedule": "0 7 * * *"}, 2) \
        == {"name": "x", "harness": "api", "job": True}
    assert schema.apply_migrations({"name": "x", "harness": "api"}, 2) \
        == {"name": "x", "harness": "api", "job": True}


def test_migrate_3_to_4_infers_job_when_no_produces(settings):
    # No `produces` block -> the file was a job under the old model; make it explicit (FR).
    assert schema.apply_migrations({"name": "x", "harness": "api"}, 3) \
        == {"name": "x", "harness": "api", "job": True}


def test_migrate_3_to_4_leaves_asset_as_asset_only(settings):
    # A `produces` block -> asset-only under the old model; `job` is NOT set, and no `triggers`
    # block is ever fabricated on read (the carry-over script fills schedules).
    data = {"name": "x", "harness": "api", "produces": {"asset": "a/b"}}
    migrated = schema.apply_migrations(dict(data), 3)
    assert "job" not in migrated
    assert "triggers" not in migrated


def test_migrations_noop_at_current_version():
    data = {"name": "x", "harness": "api", "job": True}
    assert schema.apply_migrations(dict(data), schema.SCHEMA_VERSION) == data
    # From version 0 the produces-less agent is made an explicit job by 3->4.
    assert schema.apply_migrations({"name": "x", "harness": "api"}, 0) \
        == {"name": "x", "harness": "api", "job": True}


def test_migrate_1_to_2_is_identity(settings):
    # SC-005: a schema-1 agent (no produces) migrates to 2 unchanged; the 3->4 step then makes
    # it an explicit job. No produces/asset is fabricated.
    data = {"name": "x", "harness": "api", "model": "cheap",
            "prompt_file": "p.md", "output_dir": "/o"}
    migrated = schema.apply_migrations(dict(data), 1)
    assert migrated == dict(data, job=True)
    assert "produces" not in migrated and "asset" not in migrated


def test_schema_too_new_raises():
    with pytest.raises(schema.SchemaTooNew):
        schema.apply_migrations({}, schema.SCHEMA_VERSION + 1)


def test_schema_6_file_reads_as_7_and_restamps_only_on_save(settings):
    # spec 013: a schema-6 file migrates to 7 in memory with unchanged fields (zero migration
    # noise), keeps its `# agentbox-schema: 6` header until the UI next saves it, and re-stamps
    # to 7 on that save.
    import os

    import agents_store as st

    path = os.path.join(settings.AGENTS_DIR, "was-six.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# agentbox-schema: 6\nname: was-six\nharness: api\nmodel: cheap\n"
                "prompt_file: p.md\noutput_dir: /data/outputs/was-six\n"
                "network: agentnet-isolated\njob: true\n")
    before = open(path).read()

    info = st.read_agent("was-six")
    assert info["parse_error"] is None
    assert info["schema_version"] == 6                        # the file's own stamp is unchanged
    assert info["agent"]["output_dir"] == "/data/outputs/was-six"  # fields preserved
    assert open(path).read() == before                        # read never rewrote the file

    st.write_agent("was-six", info["agent"])                  # saving re-stamps to the current version
    assert "# agentbox-schema: 8" in open(path).read()


# ── litellm aliases ─────────────────────────────────────
def test_litellm_aliases_reads_config(settings):
    aliases = schema.litellm_aliases()
    assert "cheap" in aliases and "kimi" in aliases


def test_litellm_aliases_fallback_when_missing(settings, monkeypatch):
    monkeypatch.setattr(schema.config, "LITELLM_RENDERED", "/nonexistent/litellm.rendered.yaml")
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
    "enabled": "status",
    "timeout_seconds": "limits",
    "max_turns": "limits",
    "asset": "produces",
    "partition": "produces",
    "checks": "produces",
    "depends_on": "produces",
    "asset_schedule": "triggers",
    "on_upstream": "triggers",
    "on_missing": "triggers",
    "job_schedule": "triggers",
    "owner": "project_status",
    "project": "project_status",
    "status": "project_status",
    "label": "project_status",
    "repo": "project_status",
    "interval_seconds": "project_status",
    "job": "run_as_job",
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


# ── spec 016: the GitHub Projects trigger (on_project_status) ───────────────

def _ps_base(**ps):
    """A valid job agent carrying the on_project_status block's flat fields."""
    a = _base("api", job=True)
    a.update(ps)
    return a


def test_project_status_group_present_in_fields():
    by_id = {f.id: f for f in schema.FIELDS}
    for fid in schema.PROJECT_STATUS_FIELDS:
        assert fid in by_id, fid
        assert by_id[fid].section == "project_status"
        assert by_id[fid].block == "triggers.on_project_status"
    assert {"id": "project_status", "label": "GitHub Projects", "group": "runs"} in schema.SECTIONS


def test_project_status_group_in_public_payload():
    pub = schema.to_public()
    by_id = {f["id"]: f for f in pub["fields"]}
    for fid in schema.PROJECT_STATUS_FIELDS:
        assert by_id[fid]["section"] == "project_status"
    assert {"id": "project_status", "label": "GitHub Projects", "group": "runs"} in pub["sections"]


def test_validate_requires_owner_project_status_when_block_on():
    errors = schema.validate(_ps_base(label="brief"), prompt_exists=ALWAYS_TRUE)
    assert errors["owner"] and errors["project"] and errors["status"]


def test_validate_rejects_non_positive_project():
    errors = schema.validate(_ps_base(owner="o", project=0, status="In progress"),
                             prompt_exists=ALWAYS_TRUE)
    assert errors["project"] == "project must be a positive integer."


def test_validate_rejects_interval_below_thirty():
    errors = schema.validate(_ps_base(owner="o", project=1, status="In progress", interval_seconds=10),
                             prompt_exists=ALWAYS_TRUE)
    assert errors["interval_seconds"] == "interval_seconds must be an integer of at least 30."


def test_validate_rejects_bad_repo_shape():
    errors = schema.validate(_ps_base(owner="o", project=1, status="In progress", repo="notfull"),
                             prompt_exists=ALWAYS_TRUE)
    assert errors["repo"] == "repo must be a full owner/repo name."


def test_validate_accepts_a_full_valid_block():
    a = _ps_base(owner="vortexbox001", project=1, status="In progress", label="brief",
                 repo="vortexbox001/agentbox", interval_seconds=60)
    assert schema.validate(a, prompt_exists=ALWAYS_TRUE) == {}


def test_validate_block_off_needs_no_fields():
    # No on_project_status field set → block off → no error (a plain job agent).
    assert schema.validate(_base("api", job=True), prompt_exists=ALWAYS_TRUE) == {}


def test_migrate_7_to_8_is_identity():
    data = {"name": "x", "harness": "api", "produces": {"asset": "a/b"},
            "triggers": {"on_project_status": {"owner": "o", "project": 1, "status": "In progress"}}}
    assert schema.migrate_7_to_8(dict(data)) == data


def test_schema_version_is_eight_and_migration_registered():
    assert schema.SCHEMA_VERSION == 8
    assert (8, schema.migrate_7_to_8) in schema.MIGRATIONS
