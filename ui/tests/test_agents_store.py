"""Tests for agents_store: the YAML emitter, round-trips, and file CRUD."""
import glob
import os

import pytest
import yaml

import agents_store as st
import schema


# The definitions the checked-in golden files were generated from (one per harness).
GOLDEN = {
    "claude-code": {"name": "repo-librarian-agentbox", "enabled": True, "harness": "claude-code",
        "model": "claude-opus-4-8[1m]", "effort": "high", "fallback_model": "claude-opus-4-8[1m]",
        "prompt_file": "repo-librarian2.md", "output_dir": "/data/outputs/repo-librarian/agentbox",
        "workspace": "/data/workspaces/repo-librarian/agentbox", "wipe_workspace": True,
        "max_turns": 50, "permission_mode": "default", "allowed_tools": ["Read", "Write", "Bash"],
        "timeout_seconds": 1800, "schedule": "30 2 * * *", "network": "bridge", "memory": "1g", "cpus": 1.5,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "leeclemmer", "GITHUB_REPONAME": "agentbox"}},
    "pi": {"name": "repo-librarian-pi-kimi", "enabled": True, "harness": "pi", "model": "kimi", "effort": "max",
        "prompt_file": "repo-librarian.md", "output_dir": "/data/outputs/repo-librarian/pi-kimi",
        "workspace": "/data/workspaces/repo-librarian/pi-kimi", "wipe_workspace": True,
        "timeout_seconds": 1800, "allowed_tools": ["read", "write", "bash"], "schedule": "",
        "network": "agentnet", "memory": "1g", "cpus": 1.5,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "leeclemmer"}},
    "api": {"name": "nightly-digest", "enabled": True, "harness": "api", "model": "cheap", "max_tokens": 1024,
        "prompt_file": "repo-librarian.md", "output_dir": "/data/outputs/nightly-digest",
        "timeout_seconds": 600, "schedule": "0 7 * * *", "network": "agentnet-isolated", "memory": "1g", "cpus": 1.5,
        "env_file": "/data/credentials/agent-secrets.env", "env": {"GITHUB_USER": "leeclemmer"}},
    "codex": {"name": "repo-librarian-codex", "enabled": True, "harness": "codex", "model": "gpt-6-astra", "effort": "high",
        "prompt_file": "repo-librarian2.md", "output_dir": "/data/outputs/repo-librarian-codex",
        "workspace": "/data/workspaces/repo-librarian-codex", "wipe_workspace": True,
        "timeout_seconds": 1800, "schedule": "", "network": "bridge", "memory": "1g", "cpus": 1.5,
        "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_USER": "leeclemmer", "GITHUB_REPONAME": "agentbox"}},
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
    """Every real agents/*.yaml (templates included) survives emit + reload."""
    paths = sorted(glob.glob(os.path.join(settings.AGENTS_DIR, "*.yaml")))
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
    assert "repo-librarian-agentbox.yaml" in files
    assert all(not f.startswith("_") for f in files)
    assert any(f.startswith("_") for f in template_files)


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
    open(path, "w").write("name: needs-migration\nharness: pi\nprompt_file: repo-librarian.md\n")
    before = open(path).read()

    def boom(data, from_version):
        raise RuntimeError("bad migration")

    monkeypatch.setattr(schema, "apply_migrations", boom)
    info = st.read_agent("needs-migration")
    assert info["agent"] is None
    assert "schema migration failed" in info["parse_error"]
    assert info["raw"] is not None
    assert open(path).read() == before          # read never rewrote the file
