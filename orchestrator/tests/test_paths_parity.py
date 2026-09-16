"""Shared-fixture parity test for the two mirrored resolution modules (contract §4).

``orchestrator/paths.py`` and ``ui/config.py`` are deliberately duplicated — the orchestrator
and UI run in separate containers with no shared import — so, exactly as the ASSET_KEY_RE /
is_valid_cron twins are pinned, this test asserts every constant duplicated between the two
(root names, default subpaths) agrees across both. If one module's subpath drifts (say
``runs`` vs ``run-logs``), this fails.

``ui/config.py`` imports only os + pathlib, so it loads cleanly here; it is loaded under a
distinct module name (via its file path) so it never clashes with the orchestrator's imports.
"""
import importlib
import importlib.util
import os
from pathlib import Path

import pytest

import paths

# orchestrator/tests/ -> orchestrator/ -> repo root -> ui/config.py
UI_CONFIG_PATH = Path(__file__).resolve().parents[2] / "ui" / "config.py"

# One identical environment for both modules, so any remaining difference is a real drift and
# not just the two modules deriving different product-relative defaults.
SHARED_ENV = {
    "AGENTBOX_CONFIG": "/mnt/cfg",
    "AGENTBOX_DATA": "/mnt/state",
    "DAGSTER_HOME": "/mnt/dag",
    "AGENTBOX_PRODUCT_ROOT": "/prod",   # honoured by ui/config.py; harmless to paths.py
}


def _load_ui_config():
    spec = importlib.util.spec_from_file_location("ui_config_parity", UI_CONFIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def both(monkeypatch):
    for k, v in SHARED_ENV.items():
        monkeypatch.setenv(k, v)
    p = importlib.reload(paths)
    c = _load_ui_config()
    yield p, c
    importlib.reload(paths)


def test_roots_agree_across_both_modules(both):
    p, c = both
    assert p.CONFIG_ROOT == c.CONFIG_ROOT == "/mnt/cfg"
    assert p.DATA_ROOT == c.DATA_ROOT == "/mnt/state"
    assert p.DAGSTER_ROOT == c.DAGSTER_ROOT == "/mnt/dag"


def test_shared_config_subpaths_agree(both):
    p, c = both
    # the config-tree subpath names must be identical in both modules
    assert p.AGENTS_DIR == c.AGENTS_DIR
    assert p.PROMPTS_DIR == c.PROMPTS_DIR
    # the settings file the UI writes and the orchestrator's prune job reads must be the same path
    assert p.SETTINGS_FILE == c.SETTINGS_FILE


def test_runs_root_agrees_across_both_modules(both):
    # The writer (paths.RUNS_ROOT) and reader (config.RUNS_DIR) must name the same tree, or the
    # viewer reads a directory the orchestrator never writes (spec 012).
    p, c = both
    assert p.RUNS_ROOT == c.RUNS_DIR == "/mnt/state/runs"


def test_run_filenames_agree_across_both_modules(both):
    # The four per-run filenames are duplicated (writer in paths, reader in config); pin them
    # so a rename in one (say events.jsonl -> events.log) can never desync the two (spec 012).
    p, c = both
    assert p.RUN_TRANSCRIPT == c.RUN_TRANSCRIPT == "transcript.jsonl"
    assert p.RUN_EVENTS == c.RUN_EVENTS == "events.jsonl"
    assert p.RUN_CONTEXT == c.RUN_CONTEXT == "context.json"
    assert p.RUN_REPORT == c.RUN_REPORT == "report.json"


def test_default_state_and_dagster_roots_agree_when_unset(monkeypatch):
    # The two default literals that do not depend on the product tree must match verbatim.
    for v in ("AGENTBOX_DATA", "DAGSTER_HOME"):
        monkeypatch.delenv(v, raising=False)
    p = importlib.reload(paths)
    c = _load_ui_config()
    try:
        assert p.DATA_ROOT == c.DATA_ROOT == "/data/agentbox"
        assert p.DAGSTER_ROOT == c.DAGSTER_ROOT == "/data/dagster"
    finally:
        importlib.reload(paths)


def _load_ui_settings_store():
    """Load ui/settings_store.py, injecting ui/config.py as ``config`` so its import resolves."""
    import sys
    ui_dir = Path(__file__).resolve().parents[2] / "ui"
    saved = sys.modules.get("config")
    cfg_spec = importlib.util.spec_from_file_location("config", ui_dir / "config.py")
    cfg = importlib.util.module_from_spec(cfg_spec)
    sys.modules["config"] = cfg
    try:
        cfg_spec.loader.exec_module(cfg)
        spec = importlib.util.spec_from_file_location("ui_settings_store_parity",
                                                      ui_dir / "settings_store.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if saved is not None:
            sys.modules["config"] = saved
        else:
            sys.modules.pop("config", None)


def test_governor_defaults_agree_across_packages():
    # The governor defaults (12/5) are stated once per package; pin the two twins in agreement
    # (spec 013 R10). The live value is settings.yaml; only the fallback default is duplicated.
    import governors
    ss = _load_ui_settings_store()
    assert governors.DEFAULT_GOVERNORS == {"max_runs_per_hour": 12, "max_chain_depth": 5}
    assert ss.DEFAULT_GOVERNORS == governors.DEFAULT_GOVERNORS


def test_upstream_env_key_transform_documented_form():
    # The AGENTBOX_UPSTREAM_<KEY> upper-snake transform, pinned to its documented form (R6/R10).
    import factory
    assert factory.upstream_env_key("notes/daily") == "NOTES_DAILY"
    assert factory.upstream_env_key("repo-review/list-commits") == "REPO_REVIEW_LIST_COMMITS"
    assert factory.upstream_env_key("a-b/c-d/e") == "A_B_C_D_E"
    assert factory.upstream_key_slug("notes/daily") == "notes_daily"
