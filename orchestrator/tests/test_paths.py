"""Path-resolution unit tests for orchestrator/paths.py (contract path-resolution §4).

The three root env vars are read once at import, so every test that changes them reloads
the module under the new environment (the ``reload_paths`` helper) and the ``restore_paths``
fixture reloads it back to the ambient environment afterwards.
"""
import importlib
import os

import pytest

import paths

# The three root env vars this module resolves — cleared so "unset" means the documented default.
ROOT_VARS = ("AGENTBOX_CONFIG", "AGENTBOX_DATA", "DAGSTER_HOME")


def reload_paths(monkeypatch, **env):
    """Reload ``paths`` with exactly ``env`` set for the root vars (others cleared)."""
    for v in ROOT_VARS + ("AGENTBOX_HOST_REPO",):
        monkeypatch.delenv(v, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(paths)


@pytest.fixture(autouse=True)
def restore_paths():
    """Reload ``paths`` back to the ambient environment after each test."""
    yield
    importlib.reload(paths)


# --- R-PR-1: unset → defaults ------------------------------------------------

def test_unset_vars_resolve_to_defaults(monkeypatch):
    p = reload_paths(monkeypatch)
    assert p.CONFIG_ROOT == os.path.join(p.PRODUCT_ROOT, "config")
    assert p.DATA_ROOT == "/data/agentbox"
    assert p.DAGSTER_ROOT == "/data/dagster"
    # derived subpaths follow the defaults
    assert p.AGENTS_GLOB == os.path.join(p.PRODUCT_ROOT, "config", "agents", "*.yaml")
    assert p.PROMPTS_DIR == os.path.join(p.PRODUCT_ROOT, "config", "prompts")
    assert p.RUNS_ROOT == "/data/agentbox/runs"
    assert p.PIPES_ROOT == "/data/dagster/pipes"


def test_module_imports_with_no_vars_set(monkeypatch):
    # R-PR-1: both processes must import/start normally with none of §1 set.
    p = reload_paths(monkeypatch)
    assert all(isinstance(v, str) for v in (p.CONFIG_ROOT, p.DATA_ROOT, p.DAGSTER_ROOT))


# --- derived-constant relationships (R-PR-3) ---------------------------------

def test_pipes_under_dagster_runs_under_data(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state", DAGSTER_HOME="/mnt/dag")
    assert p.PIPES_ROOT == os.path.join(p.DAGSTER_ROOT, "pipes")
    assert p.PIPES_ROOT.startswith(p.DAGSTER_ROOT + os.sep)
    assert p.RUNS_ROOT == os.path.join(p.DATA_ROOT, "runs")
    assert p.RUNS_ROOT.startswith(p.DATA_ROOT + os.sep)
    # RUNS is under DATA, never under DAGSTER (agent-logs moved out — FR-010)
    assert not p.RUNS_ROOT.startswith(p.DAGSTER_ROOT + os.sep)


def test_state_subpaths_all_under_data_root(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state")
    for sub in (p.RUNS_ROOT, p.OUTPUTS_ROOT, p.WORKSPACES_ROOT, p.CREDENTIALS_ROOT, p.KEYS_ROOT):
        assert sub.startswith("/mnt/state/"), sub
    assert p.default_output_dir("a") == "/mnt/state/outputs/a"
    assert p.default_workspace("a") == "/mnt/state/workspaces/a"


def test_config_subpaths_all_under_config_root(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_CONFIG="/mnt/cfg")
    assert p.AGENTS_DIR == "/mnt/cfg/agents"
    assert p.AGENTS_GLOB == "/mnt/cfg/agents/*.yaml"
    assert p.PROMPTS_DIR == "/mnt/cfg/prompts"


# --- R-PR-2: non-default roots → no default-path leakage ---------------------

def test_non_default_roots_have_no_default_leakage(monkeypatch):
    p = reload_paths(
        monkeypatch,
        AGENTBOX_CONFIG="/mnt/cfg", AGENTBOX_DATA="/mnt/state", DAGSTER_HOME="/mnt/dag",
    )
    derived = [
        p.CONFIG_ROOT, p.DATA_ROOT, p.DAGSTER_ROOT, p.AGENTS_DIR, p.AGENTS_GLOB, p.PROMPTS_DIR,
        p.RUNS_ROOT, p.OUTPUTS_ROOT, p.WORKSPACES_ROOT, p.CREDENTIALS_ROOT, p.KEYS_ROOT,
        p.PIPES_ROOT, p.default_output_dir("x"), p.default_workspace("x"),
    ]
    for d in derived:
        assert not d.startswith("/data/agentbox"), d
        assert not d.startswith("/data/dagster"), d
        assert os.path.join(p.PRODUCT_ROOT, "config") not in d, d


# --- SC-005: roots relocated to any disk → no default fallback (US3, T024) ---

def test_relocated_roots_land_every_derived_path_under_its_root(monkeypatch):
    # US3 quickstart / SC-005: with both instance roots on a different disk, every derived
    # path is under the configured root and none resolve to a default location.
    p = reload_paths(
        monkeypatch,
        AGENTBOX_CONFIG="/mnt/disk2/cfg", AGENTBOX_DATA="/mnt/disk2/state",
        DAGSTER_HOME="/mnt/disk2/dag",
    )
    under_config = [p.AGENTS_DIR, p.AGENTS_GLOB, p.PROMPTS_DIR]
    under_data = [
        p.RUNS_ROOT, p.OUTPUTS_ROOT, p.WORKSPACES_ROOT, p.CREDENTIALS_ROOT, p.KEYS_ROOT,
        p.default_output_dir("x"), p.default_workspace("x"),
    ]
    under_dagster = [p.PIPES_ROOT]
    for d in under_config:
        assert d.startswith("/mnt/disk2/cfg/"), d
    for d in under_data:
        assert d.startswith("/mnt/disk2/state/"), d
    for d in under_dagster:
        assert d.startswith("/mnt/disk2/dag/"), d
    # SC-005: no derived path resolves to a default location, config included.
    for d in under_config + under_data + under_dagster:
        assert not d.startswith("/data/agentbox"), d
        assert not d.startswith("/data/dagster"), d
        assert os.path.join(p.PRODUCT_ROOT, "config") not in d, d


# --- Run-directory helpers (spec 012, contracts/run-directory.md) ------------

def test_run_dir_is_agent_date_runid_under_runs_root(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state")
    d = p.run_dir("hello", "2026-09-15", "abc-123")
    assert d == "/mnt/state/runs/hello/2026-09-15/abc-123"
    assert d.startswith(p.RUNS_ROOT + os.sep)


def test_run_file_composes_each_of_the_four_files(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state")
    base = p.run_dir("hello", "2026-09-15", "abc-123")
    assert p.RUN_TRANSCRIPT == "transcript.jsonl"
    assert p.RUN_EVENTS == "events.jsonl"
    assert p.RUN_CONTEXT == "context.json"
    assert p.RUN_REPORT == "report.json"
    for fn in (p.RUN_TRANSCRIPT, p.RUN_EVENTS, p.RUN_CONTEXT, p.RUN_REPORT):
        assert p.run_file("hello", "2026-09-15", "abc-123", fn) == os.path.join(base, fn)


def test_legacy_transcript_is_the_flat_form(monkeypatch):
    # Backward compat: the pre-012 flat transcript is a sibling .jsonl, not a directory (R1).
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state")
    legacy = p.legacy_transcript("hello", "2026-09-15", "abc-123")
    assert legacy == "/mnt/state/runs/hello/2026-09-15/abc-123.jsonl"
    assert legacy == p.run_dir("hello", "2026-09-15", "abc-123") + ".jsonl"


# --- host-path bridge (contract §2, R-PR-4 support) --------------------------

def test_host_path_rewrites_product_tree_only(monkeypatch):
    p = reload_paths(monkeypatch, AGENTBOX_DATA="/mnt/state")
    monkeypatch.setenv("AGENTBOX_HOST_REPO", "/host/repo")
    p = importlib.reload(paths)
    # a config path under the product tree is rewritten to the host repo
    assert p.host_path(os.path.join(p.PRODUCT_ROOT, "config", "prompts")) == "/host/repo/config/prompts"
    # a data path (host==container) passes through unchanged
    assert p.host_path("/mnt/state/outputs/a") == "/mnt/state/outputs/a"
