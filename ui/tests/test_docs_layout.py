"""Docs-track-reality checks for the three-root file layout (spec 010, FR-027/028/029).

Constitution VI asks for automated verification that the docs match the shipped layout.
These assert the three root variables are documented and that the README describes the
three-kinds model with a file-tree listing that matches the real subpaths — so a future
path rename can't silently drift from the prose.
"""
import os
import re

import pytest


UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(UI_DIR)

README = os.path.join(REPO_DIR, "README.md")
AGENTS_MD = os.path.join(REPO_DIR, "AGENTS.md")
ENV_EXAMPLE = os.path.join(REPO_DIR, ".env.example")

# The three roots the whole feature turns on (data-model §Roots).
ROOT_VARS = ["AGENTBOX_CONFIG", "AGENTBOX_DATA", "DAGSTER_HOME"]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _fenced_block_after(text, heading):
    """Return the first ``` fenced code block that follows a heading line."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == heading:
            rest = "\n".join(lines[i + 1 :])
            m = re.search(r"```[^\n]*\n(.*?)\n```", rest, re.DOTALL)
            return m.group(1) if m else None
    return None


# ── FR-029: .env.example documents all three roots ──────────
@pytest.mark.parametrize("var", ROOT_VARS)
def test_env_example_documents_each_root(var):
    text = _read(ENV_EXAMPLE)
    assert var in text, f".env.example does not document {var} (FR-029)"


# ── FR-027: README gains a Layout section naming the roots ──
def test_readme_has_layout_section():
    assert "## Layout" in _read(README), "README.md is missing the '## Layout' section (FR-027)"


@pytest.mark.parametrize("var", ROOT_VARS)
def test_readme_documents_each_root(var):
    assert var in _read(README), f"README.md does not document {var} (FR-027)"


# ── FR-027: the file-tree listing matches the real subpaths ─
def test_readme_layout_tree_lists_real_product_subpaths():
    block = _fenced_block_after(_read(README), "## Repository layout")
    assert block, "README.md has no fenced file-tree under '## Repository layout'"
    # Real top-level product-tree directories (they exist on disk).
    for entry in ["images/", "orchestrator/", "ui/", "litellm/", "examples/", "scripts/"]:
        assert entry in block, f"repository-layout tree omits real product subpath {entry!r}"
        assert os.path.isdir(os.path.join(REPO_DIR, entry.rstrip("/"))), (
            f"{entry!r} is listed but does not exist — the tree must match reality"
        )


def test_readme_layout_tree_drops_moved_config_dirs():
    # agents/ and prompts/ are instance config now (under the config root), not product
    # subpaths. The listing must not present them as top-level product-tree entries.
    block = _fenced_block_after(_read(README), "## Repository layout")
    for moved in ("agents/", "prompts/"):
        offenders = [ln for ln in block.splitlines() if ln.startswith(moved)]
        assert not offenders, (
            f"repository-layout tree still lists {moved!r} as a product-tree entry; "
            f"it belongs under the config root now (FR-027)"
        )


def test_readme_layout_section_lists_instance_subpaths():
    text = _read(README)
    # The config-root and data-root trees the Layout section documents (data-model §§ trees).
    for subpath in ["agents/", "prompts/", "litellm.overlay.yaml", "litellm.rendered.yaml",
                    "runs/", "outputs/", "workspaces/"]:
        assert subpath in text, f"README Layout section does not mention instance subpath {subpath!r}"


# ── FR-028: AGENTS.md states where each kind of file goes ───
def test_agents_md_states_where_each_kind_goes():
    text = _read(AGENTS_MD)
    for phrase in ["product tree", "config root", "data root", "examples/"]:
        assert phrase in text, f"AGENTS.md does not state where files go: missing {phrase!r} (FR-028)"
    # The two instance roots a contributor actually targets (Dagster storage is not a
    # kind of file anyone hand-places; the README Layout section covers it).
    for var in ["AGENTBOX_CONFIG", "AGENTBOX_DATA"]:
        assert var in text, f"AGENTS.md does not name {var} (FR-028)"
