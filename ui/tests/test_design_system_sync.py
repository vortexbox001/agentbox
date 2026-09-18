"""The served shared assets must not silently drift from their design-system copies.

Each file under ``ui/static/`` that is a shared design-system asset (``app.css``,
``dropdown.js``, ``icons.svg``) is compared byte-for-byte against its
``ui/design-system/static/`` sibling. Exactly ONE substitution is tolerated: the
icon-href form. Served copies resolve icons by document-relative ``#id`` (the sprite is
inlined once in ``base.html``, research R3); a design-system copy may still carry the
absolute ``/static/icons.svg#id`` form. The named normalisation below collapses that one
difference on BOTH copies before the comparison, so any OTHER divergence fails the build
(contract design-system-sync §A, FR-024, SC-006).
"""
import os

import pytest

UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVED_DIR = os.path.join(UI_DIR, "static")
DESIGN_DIR = os.path.join(UI_DIR, "design-system", "static")

# The one documented substitution: strip the absolute sprite prefix so both the served
# (`href="#id"`) and design-system forms compare equal. Nothing else is normalised.
_ICON_HREF_PREFIX = "/static/icons.svg#"

SHARED_ASSETS = ["app.css", "dropdown.js", "icons.svg"]


def _normalise(text: str) -> str:
    return text.replace(_ICON_HREF_PREFIX, "#")


@pytest.mark.parametrize("name", SHARED_ASSETS)
def test_served_asset_matches_design_system(name):
    served = os.path.join(SERVED_DIR, name)
    design = os.path.join(DESIGN_DIR, name)
    with open(served, encoding="utf-8") as f:
        served_text = f.read()
    with open(design, encoding="utf-8") as f:
        design_text = f.read()
    assert _normalise(served_text) == _normalise(design_text), (
        f"ui/static/{name} has drifted from ui/design-system/static/{name} beyond the "
        f"documented icon-href substitution; bring the served copy level (FR-024)."
    )


# ── spec 017: the five new run-detail components are registered manifest ↔ bundle ──
import json  # noqa: E402

_DESIGN = os.path.join(UI_DIR, "design-system")
_NEW_017 = ["Disclosure", "ToolCard", "CheckRow", "ProducedRow", "Summary"]


@pytest.mark.parametrize("name", _NEW_017)
def test_new_component_manifest_bundle_parity(name):
    manifest = json.loads(open(os.path.join(_DESIGN, "_ds_manifest.json"), encoding="utf-8").read())
    entry = next((c for c in manifest["components"] if c["name"] == name), None)
    assert entry, f"{name} missing from _ds_manifest.json components"
    assert any(sp["name"] == name for sp in manifest["startingPoints"]), \
        f"{name} missing a startingPoints specimen"
    bundle = open(os.path.join(_DESIGN, "_ds_bundle.js"), encoding="utf-8").read()
    assert entry["sourcePath"] in bundle, f"{name} source not in the rebuilt bundle"
    assert f"__ds_ns.{name} = __ds_scope.{name};" in bundle, \
        f"{name} not exposed by the bundle namespace"
