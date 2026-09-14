"""Path-resolution unit tests for ui/config.py (contract path-resolution §4).

Mirrors orchestrator/tests/test_paths.py: the three root env vars are read once at import,
so each test reloads the module under the new environment and the ``restore_config`` fixture
reloads it back afterwards. Includes PRODUCT_ROOT, the anchor FR-025 validation needs.
"""
import importlib
import os

import pytest

import config

ROOT_VARS = ("AGENTBOX_CONFIG", "AGENTBOX_DATA", "DAGSTER_HOME")
# UI-only overrides that would otherwise mask the derived defaults under test.
EXTRA_VARS = ("AGENTBOX_PRODUCT_ROOT", "AGENTS_DIR", "PROMPTS_DIR",
              "EXAMPLES_DIR", "TEMPLATES_DIR", "LITELLM_RENDERED")


def reload_config(monkeypatch, **env):
    for v in ROOT_VARS + EXTRA_VARS:
        monkeypatch.delenv(v, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config():
    yield
    importlib.reload(config)


# --- R-PR-1: unset → defaults ------------------------------------------------

def test_unset_vars_resolve_to_defaults(monkeypatch):
    c = reload_config(monkeypatch)
    assert c.CONFIG_ROOT == os.path.join(c.PRODUCT_ROOT, "config")
    assert c.DATA_ROOT == "/data/agentbox"
    assert c.DAGSTER_ROOT == "/data/dagster"
    assert c.AGENTS_DIR == os.path.join(c.PRODUCT_ROOT, "config", "agents")
    assert c.PROMPTS_DIR == os.path.join(c.PRODUCT_ROOT, "config", "prompts")
    assert c.EXAMPLES_DIR == os.path.join(c.PRODUCT_ROOT, "examples", "config")
    assert c.TEMPLATES_DIR == os.path.join(c.PRODUCT_ROOT, "examples", "config", "agents")


def test_product_root_is_the_checkout_and_read_only_anchor(monkeypatch):
    # FR-025 needs an explicit product-tree anchor. Under an override it follows the override.
    c = reload_config(monkeypatch, AGENTBOX_PRODUCT_ROOT="/prod")
    assert c.PRODUCT_ROOT == "/prod"
    assert c.EXAMPLES_DIR == "/prod/examples/config"


# --- R-PR-3: derived-constant relationships ----------------------------------

def test_config_subpaths_under_config_root(monkeypatch):
    c = reload_config(monkeypatch, AGENTBOX_CONFIG="/mnt/cfg")
    assert c.AGENTS_DIR == "/mnt/cfg/agents"
    assert c.PROMPTS_DIR == "/mnt/cfg/prompts"
    assert c.LITELLM_RENDERED == "/mnt/cfg/litellm.rendered.yaml"


# --- R-PR-2: non-default roots → no default-path leakage ---------------------

def test_non_default_roots_have_no_default_leakage(monkeypatch):
    c = reload_config(
        monkeypatch,
        AGENTBOX_CONFIG="/mnt/cfg", AGENTBOX_DATA="/mnt/state",
        DAGSTER_HOME="/mnt/dag", AGENTBOX_PRODUCT_ROOT="/prod",
    )
    derived = [c.CONFIG_ROOT, c.DATA_ROOT, c.DAGSTER_ROOT, c.AGENTS_DIR, c.PROMPTS_DIR,
               c.LITELLM_RENDERED]
    for d in derived:
        assert not d.startswith("/data/agentbox"), d
        assert not d.startswith("/data/dagster"), d
        assert "/prod/config" not in d, d
    # config paths land under the configured config root, not the product tree
    assert c.AGENTS_DIR.startswith("/mnt/cfg/")
