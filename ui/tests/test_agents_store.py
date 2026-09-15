"""Tests for agents_store: the YAML emitter, round-trips, and file CRUD."""
import glob
import os

import pytest
import yaml

import agents_store as st
import schema


# The definitions the checked-in golden files were generated from (one per harness). These are
# generic, self-contained sample agents — not real instance agents — so the emitter regression
# suite never leans on product-instance data (spec 010).
GOLDEN = {
    "claude-code": {"name": "sample-claude-code", "enabled": True, "harness": "claude-code",
        "model": "claude-opus-4-8[1m]", "effort": "high", "fallback_model": "claude-opus-4-8[1m]",
        "prompt_file": "hello-example.md", "output_dir": "/data/outputs/sample-claude-code",
        "workspace": "/data/workspaces/sample-claude-code", "wipe_workspace": True,
        "max_turns": 50, "permission_mode": "default", "allowed_tools": ["Read", "Write", "Bash"],
        "timeout_seconds": 1800, "network": "bridge", "memory": "1g", "cpus": 1.5, "job": True,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "example-user", "GITHUB_REPONAME": "example-repo"}},
    "pi": {"name": "sample-pi", "enabled": True, "harness": "pi", "model": "kimi", "effort": "max",
        "prompt_file": "hello-example.md", "output_dir": "/data/outputs/sample-pi",
        "workspace": "/data/workspaces/sample-pi", "wipe_workspace": True,
        "timeout_seconds": 1800, "allowed_tools": ["read", "write", "bash"],
        "network": "agentnet", "memory": "1g", "cpus": 1.5, "job": True,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "example-user"}},
    "api": {"name": "sample-api", "enabled": True, "harness": "api", "model": "cheap", "max_tokens": 1024,
        "prompt_file": "hello-example.md", "output_dir": "/data/outputs/sample-api",
        "timeout_seconds": 600, "network": "agentnet-isolated", "memory": "1g", "cpus": 1.5, "job": True,
        "env_file": "/data/credentials/agent-secrets.env", "env": {"GITHUB_USER": "example-user"}},
    "codex": {"name": "sample-codex", "enabled": True, "harness": "codex", "model": "gpt-6-astra", "effort": "high",
        "prompt_file": "hello-example.md", "output_dir": "/data/outputs/sample-codex",
        "workspace": "/data/workspaces/sample-codex", "wipe_workspace": True,
        "timeout_seconds": 1800, "network": "bridge", "memory": "1g", "cpus": 1.5, "job": True,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "example-user", "GITHUB_REPONAME": "example-repo"}},
}

_GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _normalize(loaded):
    out = {}
    for k, v in loaded.items():
        f = schema.FIELDS_BY_ID.get(k)
        if f is not None and schema._is_unset(f, v):
            continue
        out[k] = v
    return out


@pytest.mark.parametrize("harness", list(GOLDEN))
def test_golden_file_matches_emitter(settings, harness):
    with open(os.path.join(_GOLDEN_DIR, f"{harness}.yaml"), encoding="utf-8") as f:
        expected = f.read()
    assert st.emit_yaml(GOLDEN[harness]) == expected


# ── Produces block (US3, contract schema-and-yaml §3/§7) ─
def test_produces_block_commented_when_no_asset(settings):
    text = st.emit_yaml(GOLDEN["api"])
    assert "# --- Produces ---" in text
    assert "#produces:" in text
    assert "#  asset:  #" in text
    assert "#  partition: none  #" in text
    # commented block never yields a real produces mapping
    assert yaml.safe_load(text).get("produces") is None


def test_produces_block_emitted_when_asset_set(settings):
    cfg = dict(GOLDEN["api"], asset="repo-review/agentbox", partition="daily")
    text = st.emit_yaml(cfg)
    loaded = yaml.safe_load(text)
    assert loaded["produces"] == {"asset": "repo-review/agentbox", "partition": "daily"}
    # one help-text comment per field (asset, partition) plus the block header
    assert "produces:  #" in text
    assert "  asset: repo-review/agentbox  #" in text
    assert "  partition: daily  #" in text


def test_produces_block_sits_in_the_runs_section(settings):
    cfg = dict(GOLDEN["api"], asset="repo-review/agentbox", partition="daily")
    text = st.emit_yaml(cfg)
    lines = text.splitlines()
    prod = lines.index("# --- Produces ---")
    limits = lines.index("# --- Limits ---")
    prompt = lines.index("# --- Prompt ---")
    assert limits < prod < prompt  # Produces is a Runs card, after Limits, before Prompt


def test_produces_block_round_trips_byte_stable(settings):
    cfg = dict(GOLDEN["api"], asset="reports/sample", partition="daily")
    once = st.emit_yaml(cfg)
    st.write_agent("sample-api", cfg)
    info = st.read_agent("sample-api")
    agent = info["agent"]
    assert agent["asset"] == "reports/sample"
    assert agent["partition"] == "daily"
    # asset/partition are managed, never routed to unmanaged
    assert "produces" not in (agent.get("unmanaged") or {})
    assert st.emit_yaml(agent) == once


# ── produces.checks list (spec 008, contract check-model §5) ──
_CHECKS = [
    {"name": "has-output", "command": "test -n \"$(ls /output)\""},
    {"name": "advisory-fail", "command": "false", "blocking": False},
    {"name": "slow", "command": "sleep 60", "timeout_seconds": 2, "network": "agentnet",
     "image": "agentbox/agent-python:latest"},
]


def test_checks_emitted_as_nested_sequence_under_produces(settings):
    cfg = dict(GOLDEN["api"], asset="verify/checks", checks=_CHECKS)
    text = st.emit_yaml(cfg)
    loaded = yaml.safe_load(text)
    # the nested checks list round-trips to exactly the input mappings
    assert loaded["produces"]["asset"] == "verify/checks"
    assert loaded["produces"]["checks"] == _CHECKS
    assert "  checks:  #" in text          # header comment on the list
    assert "    - name: has-output" in text


def test_checks_round_trip_byte_stable(settings):
    cfg = dict(GOLDEN["api"], name="verify-checks", asset="verify/checks", checks=_CHECKS)
    once = st.emit_yaml(cfg)
    st.write_agent("verify-checks", cfg)
    agent = st.read_agent("verify-checks")["agent"]
    assert agent["checks"] == _CHECKS            # lifted into the flat model, unchanged
    assert "produces" not in (agent.get("unmanaged") or {})
    assert "checks" not in (agent.get("unmanaged") or {})
    assert st.emit_yaml(agent) == once           # re-emit is byte-identical


def test_checks_not_emitted_without_asset(settings):
    # checks are children of produces; with no asset the produces block is commented and
    # carries no checks line (contract §5).
    cfg = dict(GOLDEN["api"]); cfg.pop("asset", None); cfg["checks"] = _CHECKS
    text = st.emit_yaml(cfg)
    assert "checks:" not in text


def test_checks_validate_emit_read_are_consistent(settings):
    # The round-trip a save performs: validate → emit → read back → validate again.
    cfg = dict(GOLDEN["api"], asset="verify/checks", checks=_CHECKS)
    assert schema.validate(cfg, prompt_exists=lambda _p: True) == {}
    st.write_agent("verify-checks", cfg)
    agent = st.read_agent("verify-checks")["agent"]
    agent2 = dict(agent, harness="api")
    assert schema.validate(agent2, prompt_exists=lambda _p: True) == {}


def test_asset_less_produces_read_as_empty_declaration(settings):
    # A hand-written asset-less produces: surfaces as a present-but-empty asset so the
    # form/validate can flag it, and is not dropped into unmanaged.
    import os, config
    path = os.path.join(config.AGENTS_DIR, "handwritten.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# agentbox-schema: 2\nname: handwritten\nharness: api\n"
                "output_dir: /o\nprompt_file: p.md\nproduces:\n  partition: daily\n")
    agent = st.read_agent("handwritten")["agent"]
    assert agent["asset"] == ""
    assert "produces" not in (agent.get("unmanaged") or {})


# ── Job flag + triggers block (spec 006, contract agent-model §1/§2/§5) ─
def test_job_line_real_when_job_and_commented_otherwise(settings):
    job_text = st.emit_yaml(GOLDEN["api"])  # job: True
    assert "\njob: true  #" in job_text
    # An asset-only agent (no job): the job line is a commented placeholder.
    asset_only = dict(GOLDEN["api"]); asset_only.pop("job"); asset_only["asset"] = "a/b"
    txt = st.emit_yaml(asset_only)
    assert "\n#job:  #" in txt
    assert yaml.safe_load(txt).get("job") is None


def test_triggers_block_commented_when_no_schedule(settings):
    text = st.emit_yaml(GOLDEN["api"])  # job-only, no schedule
    assert "# --- Triggers ---" in text
    assert "#triggers:" in text
    assert "#  job_schedule:" in text
    assert "asset_schedule" not in text  # off-kind omitted for a job-only agent
    assert yaml.safe_load(text).get("triggers") is None


def test_triggers_block_real_when_schedule_set(settings):
    cfg = dict(GOLDEN["api"], job_schedule="30 2 * * *")
    text = st.emit_yaml(cfg)
    loaded = yaml.safe_load(text)
    assert loaded["triggers"] == {"job_schedule": "30 2 * * *"}
    assert "triggers:  #" in text
    assert "  job_schedule: 30 2 * * *  #" in text


def test_triggers_block_omits_off_kind_schedule(settings):
    # An asset-only agent shows only asset_schedule; job_schedule is omitted.
    asset_only = dict(GOLDEN["api"]); asset_only.pop("job")
    cfg = dict(asset_only, asset="repo-review/x", asset_schedule="20 17 * * *")
    text = st.emit_yaml(cfg)
    assert "  asset_schedule: 20 17 * * *  #" in text
    assert "job_schedule" not in text
    assert yaml.safe_load(text)["triggers"] == {"asset_schedule": "20 17 * * *"}


def test_both_kind_agent_shows_both_schedules(settings):
    cfg = dict(GOLDEN["api"], asset="repo-review/x", asset_schedule="20 17 * * *", job_schedule="30 2 * * *")
    loaded = yaml.safe_load(st.emit_yaml(cfg))
    assert loaded["triggers"] == {"asset_schedule": "20 17 * * *", "job_schedule": "30 2 * * *"}
    assert loaded["job"] is True
    assert loaded["produces"]["asset"] == "repo-review/x"


def test_triggers_and_job_round_trip(settings):
    cfg = dict(GOLDEN["api"], name="both-kind", asset="repo-review/x",
               asset_schedule="20 17 * * *", job_schedule="30 2 * * *")
    once = st.emit_yaml(cfg)
    st.write_agent("both-kind", cfg)
    agent = st.read_agent("both-kind")["agent"]
    assert agent["asset_schedule"] == "20 17 * * *"
    assert agent["job_schedule"] == "30 2 * * *"
    assert agent["job"] is True
    # schedules are managed, never routed to unmanaged
    assert "triggers" not in (agent.get("unmanaged") or {})
    assert st.emit_yaml(agent) == once


def test_triggers_section_after_produces_before_job(settings):
    text = st.emit_yaml(dict(GOLDEN["api"], asset="a/b", asset_schedule="20 17 * * *", job_schedule="30 2 * * *"))
    lines = text.splitlines()
    prod = lines.index("# --- Produces ---")
    trig = lines.index("# --- Triggers ---")
    job = lines.index("# --- Job ---")
    prompt = lines.index("# --- Prompt ---")
    assert prod < trig < job < prompt


@pytest.mark.parametrize("harness", list(GOLDEN))
def test_emitted_section_headers_follow_schema_order(settings, harness):
    """The `# --- <label> ---` headers appear in schema.SECTIONS label order, and
    `name:` is the first key line of the file (003 contract schema-and-yaml.md §2)."""
    text = st.emit_yaml(GOLDEN[harness])
    headers = [ln[6:-4].strip() for ln in text.splitlines() if ln.startswith("# --- ")]
    section_labels = [s["label"] for s in schema.SECTIONS]
    # The emitted headers are a subsequence of the schema's section labels (a card
    # is skipped when it has no applicable value), in the same relative order.
    positions = [section_labels.index(h) for h in headers if h in section_labels]
    assert positions == sorted(positions), headers
    first_key = next(ln for ln in text.splitlines() if ln and not ln.startswith("#"))
    assert first_key.startswith("name:"), first_key


def test_repo_agents_round_trip(settings):
    """Every real agents/*.yaml and every examples-tree template survives emit + reload.

    Templates moved to the examples tree (R7), so they are globbed from TEMPLATES_DIR now.
    """
    paths = sorted(glob.glob(os.path.join(settings.AGENTS_DIR, "*.yaml")))
    paths += sorted(glob.glob(os.path.join(settings.TEMPLATES_DIR, "*.yaml")))
    assert paths, "no agent files copied into the temp dir"
    for path in paths:
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        emitted = st.emit_yaml(loaded)
        reloaded = yaml.safe_load(emitted)
        norm = _normalize(loaded)
        for k, v in norm.items():
            assert reloaded.get(k) == v, f"{os.path.basename(path)}: field {k} not preserved"


def test_emitting_twice_is_byte_identical(settings):
    for cfg in GOLDEN.values():
        once = st.emit_yaml(cfg)
        twice = st.emit_yaml(yaml.safe_load(once))
        assert once == twice


def test_unmanaged_keys_round_trip(settings):
    cfg = dict(GOLDEN["api"])
    cfg["unmanaged"] = {"future_key": "kept", "nested": {"a": 1}}
    reloaded = yaml.safe_load(st.emit_yaml(cfg))
    assert reloaded["future_key"] == "kept"
    assert reloaded["nested"] == {"a": 1}


def test_read_preserves_unmanaged_keys(settings):
    path = os.path.join(settings.AGENTS_DIR, "with-extra.yaml")
    with open(path, "w") as f:
        f.write("name: with-extra\nharness: api\nmodel: cheap\nprompt_file: p.md\n"
                "output_dir: /o\nnetwork: agentnet-isolated\nschedule: \"\"\nfuture_thing: 42\n")
    info = st.read_agent("with-extra")
    assert info["parse_error"] is None
    assert info["agent"]["unmanaged"] == {"future_thing": 42}


def test_name_mismatch_flagged_and_normalised(settings):
    path = os.path.join(settings.AGENTS_DIR, "file-stem.yaml")
    with open(path, "w") as f:
        f.write("name: different-name\nharness: api\nmodel: cheap\nprompt_file: p.md\n"
                "output_dir: /o\nnetwork: agentnet-isolated\nschedule: \"\"\n")
    info = st.read_agent("file-stem")
    assert info["name_mismatch"] is True
    # writing normalises name to the filename stem
    st.write_agent("file-stem", info["agent"])
    rewritten = yaml.safe_load(open(path))
    assert rewritten["name"] == "file-stem"


def test_newer_schema_version_is_parse_error(settings):
    path = os.path.join(settings.AGENTS_DIR, "from-future.yaml")
    with open(path, "w") as f:
        f.write(f"# agentbox-schema: {schema.SCHEMA_VERSION + 1}\n"
                "name: from-future\nharness: api\nmodel: cheap\nprompt_file: p.md\n"
                "output_dir: /o\nnetwork: agentnet-isolated\n")
    info = st.read_agent("from-future")
    assert info["parse_error"] is not None
    assert info["editable"] is False


def test_syntax_error_is_parse_error_with_raw(settings):
    path = os.path.join(settings.AGENTS_DIR, "broken.yaml")
    with open(path, "w") as f:
        f.write("name: broken\n  bad: : indentation\n")
    info = st.read_agent("broken")
    assert info["parse_error"] is not None
    assert info["raw"] is not None
    assert info["agent"] is None


def test_write_is_atomic_no_tmp_left(settings):
    st.write_agent("fresh", GOLDEN["api"])
    assert os.path.isfile(os.path.join(settings.AGENTS_DIR, "fresh.yaml"))
    leftovers = glob.glob(os.path.join(settings.AGENTS_DIR, "*.tmp")) + \
        glob.glob(os.path.join(settings.AGENTS_DIR, ".*.tmp"))
    assert leftovers == []


def test_write_failure_leaves_original_intact(settings, monkeypatch):
    st.write_agent("keeper", GOLDEN["api"])
    original = open(os.path.join(settings.AGENTS_DIR, "keeper.yaml")).read()

    def boom(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(st.os, "replace", boom)
    with pytest.raises(st.StorageError):
        st.write_agent("keeper", GOLDEN["codex"])
    assert open(os.path.join(settings.AGENTS_DIR, "keeper.yaml")).read() == original
    assert glob.glob(os.path.join(settings.AGENTS_DIR, ".keeper.*.tmp")) == []


def test_delete_removes_only_the_file(settings):
    st.write_agent("one", GOLDEN["api"])
    st.write_agent("two", GOLDEN["api"])
    st.delete_agent("one")
    assert not os.path.exists(os.path.join(settings.AGENTS_DIR, "one.yaml"))
    assert os.path.exists(os.path.join(settings.AGENTS_DIR, "two.yaml"))


def test_delete_missing_raises(settings):
    with pytest.raises(FileNotFoundError):
        st.delete_agent("nope")


def test_list_agents_splits_templates(settings):
    listed = st.list_agents()
    files = {a["file"] for a in listed["agents"]}
    template_files = {t["file"] for t in listed["templates"]}
    assert "hello-example.yaml" in files
    assert all(not f.startswith("_") for f in files)
    assert any(f.startswith("_") for f in template_files)


def test_templates_listed_from_examples_tree(settings, tmp_agents, tmp_templates):
    """Picker templates come from the examples tree; instance agents are never templates (R7, FR-008).

    An instance agent (no ``_``) is listed as an agent, never as a template. A stray
    ``_``-prefixed file in the instance dir (e.g. one a fresh install copied in) is kept out
    of the agent list and is not offered as a template — the examples tree is the only
    template source. The examples tree's own non-template sample agents (``hello-example.yaml``)
    are not offered as templates either.
    """
    (tmp_agents / "my-real-agent.yaml").write_text(
        "name: my-real-agent\nharness: pi\nprompt_file: p.md\noutput_dir: /data/outputs/x\n",
        encoding="utf-8",
    )
    (tmp_agents / "_stray.yaml").write_text(
        "name: stray\nharness: pi\nprompt_file: p.md\noutput_dir: /data/outputs/y\n",
        encoding="utf-8",
    )
    listed = st.list_agents()
    agent_files = {a["file"] for a in listed["agents"]}
    template_files = {t["file"] for t in listed["templates"]}

    # Templates are the examples-tree ``_``-prefixed starters only.
    assert "_template-pi.yaml" in template_files
    assert template_files and all(f.startswith("_") for f in template_files)
    assert "hello-example.yaml" not in template_files  # a sample agent, not a picker template

    # Instance agents: a real one is listed; a stray ``_`` file is neither an agent nor a template.
    assert "my-real-agent.yaml" in agent_files
    assert "_stray.yaml" not in agent_files
    assert "_stray.yaml" not in template_files


def test_read_template_reads_from_examples_tree(settings):
    """read_template resolves against the examples tree, not the instance agents dir (R7)."""
    info = st.read_template("_template-pi")
    assert info["file"] == "_template-pi.yaml"
    assert info["agent"]["harness"] == "pi"
    # The same stem is not an instance agent.
    with pytest.raises(FileNotFoundError):
        st.read_agent("_template-pi")


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")
def test_read_only_dir_raises_storage_error(settings, tmp_path, monkeypatch):
    ro = tmp_path / "ro-agents"
    ro.mkdir()
    monkeypatch.setattr(settings, "AGENTS_DIR", str(ro))
    os.chmod(ro, 0o500)
    try:
        with pytest.raises(st.StorageError) as ei:
            st.write_agent("blocked", GOLDEN["api"])
        assert ei.value.operation == "write"
    finally:
        os.chmod(ro, 0o700)


# ── Config edits stay under the config root, never the product tree (US4, SC-007) ──
def test_write_lands_under_config_root_not_product_tree(settings, tmp_path, monkeypatch):
    # SC-007: with the config root on its own path (as when a separate git repo is checked
    # out there), a create/edit writes under config.AGENTS_DIR — derived from CONFIG_ROOT —
    # and no write path can reach the product tree.
    cfg_root = tmp_path / "config-repo"
    agents_dir = cfg_root / "agents"
    agents_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_ROOT", str(cfg_root))
    monkeypatch.setattr(settings, "AGENTS_DIR", str(agents_dir))

    path = st.write_agent("in-config-repo", GOLDEN["api"])
    assert path.startswith(str(cfg_root) + os.sep)
    assert (agents_dir / "in-config-repo.yaml").is_file()
    # nothing was written under the product tree
    assert not path.startswith(settings.PRODUCT_ROOT + os.sep)
    assert not os.path.exists(os.path.join(settings.PRODUCT_ROOT, "agents", "in-config-repo.yaml"))


# ── Path safety on the filename stem (FR-010a, CHK041) ──
@pytest.mark.parametrize("bad", ["../secret", "..", "a/b", "a\\b", "../../etc/passwd"])
def test_unsafe_stem_is_never_addressable(settings, bad):
    # Traversal or a separator is refused the same way at every store entry point.
    assert st.agent_exists(bad) is False
    with pytest.raises(FileNotFoundError):
        st.read_agent(bad)
    with pytest.raises(FileNotFoundError):
        st.delete_agent(bad)
    with pytest.raises(ValueError):
        st.write_agent(bad, {"name": bad, "harness": "pi", "prompt_file": "p.md",
                             "output_dir": "/x", "model": "cheap"})


# ── A migration that raises surfaces as a parse error (R12, CHK024) ──
def test_migration_failure_is_parse_error_and_leaves_file(settings, monkeypatch):
    path = os.path.join(settings.AGENTS_DIR, "needs-migration.yaml")
    open(path, "w").write("name: needs-migration\nharness: pi\nprompt_file: hello-example.md\n")
    before = open(path).read()

    def boom(data, from_version):
        raise RuntimeError("bad migration")

    monkeypatch.setattr(schema, "apply_migrations", boom)
    info = st.read_agent("needs-migration")
    assert info["agent"] is None
    assert "schema migration failed" in info["parse_error"]
    assert info["raw"] is not None
    assert open(path).read() == before          # read never rewrote the file


# ── Tabbed-list row fields: is_asset / is_job / crons / checks (spec 011 US1, contract §A) ──
def _write_both_kind(settings):
    """A both-kind agent with an asset+job schedule and one declared check (via the emitter)."""
    cfg = dict(GOLDEN["api"], name="both-kind", asset="reports/bk", job=True,
               asset_schedule="0 17 * * *", job_schedule="30 2 * * *",
               checks=[{"name": "has-output"}])
    st.write_agent("both-kind", cfg)


def test_list_rows_carry_kind_flags(settings):
    rows = {r["name"]: r for r in st.list_agents()["agents"]}
    # The example instance corpus: one asset agent and one job agent, neither scheduled.
    asset_row = rows["hello-asset-example"]
    assert asset_row["is_asset"] is True and asset_row["is_job"] is False
    assert asset_row["crons"] == [] and asset_row["checks"] == []
    job_row = rows["hello-example"]
    assert job_row["is_job"] is True and job_row["is_asset"] is False


def test_list_rows_carry_crons_with_canonical_names(settings):
    _write_both_kind(settings)
    bk = {r["name"]: r for r in st.list_agents()["agents"]}["both-kind"]
    assert bk["is_asset"] is True and bk["is_job"] is True
    by_type = {c["type"]: c for c in bk["crons"]}
    assert set(by_type) == {"asset_schedule", "job_schedule"}
    # dagster_name matches the factory's registration (dagster-activity §0), '-' → '_'.
    assert by_type["asset_schedule"]["dagster_name"] == "autocond_both_kind"
    assert by_type["job_schedule"]["dagster_name"] == "sched_both_kind"
    assert by_type["asset_schedule"]["expr"] == "0 17 * * *"
    assert [c["name"] for c in bk["checks"]] == ["has-output"]


def test_parse_error_row_has_no_kind_or_crons(settings):
    open(os.path.join(settings.AGENTS_DIR, "broken.yaml"), "w").write("name: broken\n: : :\n")
    broken = {r["name"]: r for r in st.list_agents()["agents"]}["broken"]
    assert broken["parse_error"]
    assert broken["is_asset"] is False and broken["is_job"] is False
    assert broken["crons"] == [] and broken["checks"] == []


def test_tab_counts_derivation(settings):
    _write_both_kind(settings)
    rows = st.list_agents()["agents"]
    # Both-kind counts in both Assets and Jobs; on-demand agents are excluded from Scheduled.
    assert sum(1 for r in rows if r["is_asset"]) == 2   # hello-asset-example + both-kind
    assert sum(1 for r in rows if r["is_job"]) == 2     # hello-example + both-kind
    assert sum(1 for r in rows if r["crons"]) == 1      # only both-kind is scheduled
    assert sum(1 for r in rows if r["enabled"] is False) == 0
