"""Docs-track-reality checks for the design system (spec 009 FR-023).

The retired Archon guide and its reference canvases are gone (FR-001); these checks
replace the stale assertions that read them. They verify the in-repo design system is
the source of truth and is described where it should be:

1. Every component in ``ui/design-system/_ds_manifest.json`` has a corresponding shared
   Jinja2 macro in ``ui/templates/components/macros.html`` (``Tab`` is covered by
   ``tabs``).
2. ``README.md`` and ``AGENTS.md`` name ``ui/design-system/readme.md`` as the source of
   truth.
3. No test or served file references a retired Archon artefact.
"""
import json
import os
import re

import pytest


UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(UI_DIR)
DESIGN_DIR = os.path.join(UI_DIR, "design-system")
MANIFEST = os.path.join(DESIGN_DIR, "_ds_manifest.json")
MACROS = os.path.join(UI_DIR, "templates", "components", "macros.html")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── 1. Manifest components ↔ shared macros ──────────────
def _manifest_component_names():
    data = json.loads(_read(MANIFEST))
    return [c["name"] for c in data["components"]]


def _macro_names():
    # `{% macro name(` — the shared component macros.
    return set(re.findall(r"{%-?\s*macro\s+([a-z_][\w]*)\s*\(", _read(MACROS)))


# CamelCase component name → snake_case macro name; `Tab` is rendered by `tabs`.
_MACRO_OVERRIDES = {"Tab": "tabs"}


def _expected_macro(component_name):
    if component_name in _MACRO_OVERRIDES:
        return _MACRO_OVERRIDES[component_name]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", component_name).lower()


def test_manifest_lists_components():
    names = _manifest_component_names()
    assert names, "manifest lists no components"


@pytest.mark.parametrize("component", _manifest_component_names())
def test_each_manifest_component_has_a_macro(component):
    macros = _macro_names()
    expected = _expected_macro(component)
    assert expected in macros, (
        f"manifest component {component!r} has no shared macro {expected!r} in "
        f"templates/components/macros.html (have: {sorted(macros)})"
    )


# ── 2. Docs name the source of truth ────────────────────
@pytest.mark.parametrize("doc", ["README.md", "AGENTS.md"])
def test_docs_reference_design_system_source_of_truth(doc):
    text = _read(os.path.join(REPO_DIR, doc))
    assert "design-system/readme.md" in text, (
        f"{doc} does not name ui/design-system/readme.md as the design-system source of truth"
    )


# ── 3. No retired Archon artefact is referenced ─────────
# The files removed by FR-001; a live reference to any is a broken link or a stale claim.
_RETIRED_ARTEFACTS = [
    "archon-tokens.css",
    "ARCHON-DESIGN-SYSTEM.md",
    "Archon Design System.dc.html",
    "Archon Prototype.dc.html",
    "support.js",
]
_SCAN_EXTS = (".py", ".html", ".css", ".js", ".md", ".json")
_THIS_FILE = os.path.abspath(__file__)


def _served_and_test_files():
    roots = [
        os.path.join(UI_DIR, "templates"),
        os.path.join(UI_DIR, "static"),
        DESIGN_DIR,
        os.path.join(UI_DIR, "tests"),
    ]
    for root in roots:
        for dirpath, _, names in os.walk(root):
            for n in names:
                if not n.endswith(_SCAN_EXTS):
                    continue
                path = os.path.join(dirpath, n)
                if os.path.abspath(path) == _THIS_FILE:
                    continue  # the scanner names the artefacts it forbids
                yield path


def test_no_retired_archon_artefact_referenced():
    needles = [a.lower() for a in _RETIRED_ARTEFACTS]
    offenders = []
    for path in _served_and_test_files():
        text = _read(path).lower()
        hit = [a for a in needles if a in text]
        if hit:
            offenders.append(f"{os.path.relpath(path, REPO_DIR)}: {hit}")
    assert not offenders, f"retired Archon artefact(s) referenced in: {offenders}"


# ── Served specimen gallery renders offline (spec 009 T034–T036) ──
# Every HTML the /design-system gallery serves and iframes (the gallery page, the
# component preview cards, the guideline specimens, and the ui-kit) must load with egress
# blocked: no CDN or external asset URL. (Token/font egress is US4's separate concern and
# is scoped out here — this guards the gallery itself.)
_EXTERNAL_ASSET = re.compile(r"unpkg|cdnjs|jsdelivr|cdn\.|googleapis|https?://\S+\.(?:js|css|woff2?)")


def _served_bundle_html():
    roots = [
        os.path.join(DESIGN_DIR, "components"),
        os.path.join(DESIGN_DIR, "ui_kits"),
        os.path.join(DESIGN_DIR, "guidelines"),
    ]
    files = [os.path.join(DESIGN_DIR, "index.html")]
    for root in roots:
        for dirpath, _, names in os.walk(root):
            for n in names:
                if n.endswith(".html"):
                    files.append(os.path.join(dirpath, n))
    return files


def test_specimen_gallery_has_no_external_assets():
    offenders = []
    for path in _served_bundle_html():
        if _EXTERNAL_ASSET.search(_read(path)):
            offenders.append(os.path.relpath(path, REPO_DIR))
    assert not offenders, f"served specimen file(s) reference an external/CDN asset: {offenders}"


def test_every_manifest_card_preview_exists():
    manifest = json.loads(_read(MANIFEST))
    missing = [c["path"] for c in manifest["cards"] if not os.path.exists(os.path.join(DESIGN_DIR, c["path"]))]
    assert not missing, f"manifest card preview file(s) missing: {missing}"


# ── spec 015 US5 / FR-034: Pagination is a first-class design-system component ──
# Design-system-first gate made executable: the component source, specimen, manifest entry,
# shared macro, and readme entry must all be present (contract pagination-component §A/§D, T037).
def test_pagination_is_registered_end_to_end():
    manifest = json.loads(_read(MANIFEST))
    # Manifest ↔ bundle ↔ macro parity for Pagination.
    assert any(c["name"] == "Pagination" for c in manifest["components"]), \
        "Pagination missing from _ds_manifest.json components"
    assert any(sp["name"] == "Pagination" for sp in manifest["startingPoints"]), \
        "Pagination missing a startingPoints entry"
    assert "pagination" in _macro_names(), "no shared `pagination` macro in macros.html"
    bundle = _read(os.path.join(DESIGN_DIR, "_ds_bundle.js"))
    assert "components/navigation/Pagination.jsx" in bundle, "Pagination not in the rebuilt bundle"
    assert "__ds_ns.Pagination = __ds_scope.Pagination;" in bundle, \
        "Pagination not exposed by the bundle namespace"
    # Component source file set (parallel to Tabs.*) + specimen.
    nav = os.path.join(DESIGN_DIR, "components", "navigation")
    for f in ("Pagination.jsx", "Pagination.d.ts", "Pagination.prompt.md", "pagination.card.html"):
        assert os.path.exists(os.path.join(nav, f)), f"missing Pagination component file: {f}"


def test_pagination_documented_in_readme():
    readme = _read(os.path.join(DESIGN_DIR, "readme.md"))
    assert "Pagination" in readme, "readme.md does not document the Pagination component"


# ── spec 017 / FR-037: the five run-detail components are design-system-first ──
_NEW_017 = [
    ("Disclosure", "disclosure", "components/layout/Disclosure.jsx", "components/layout"),
    ("ToolCard", "tool_card", "components/data/ToolCard.jsx", "components/data"),
    ("CheckRow", "check_row", "components/data/CheckRow.jsx", "components/data"),
    ("ProducedRow", "produced_row", "components/data/ProducedRow.jsx", "components/data"),
    ("Summary", "summary", "components/data/Summary.jsx", "components/data"),
]


@pytest.mark.parametrize("name,macro,src,folder", _NEW_017)
def test_017_component_registered_end_to_end(name, macro, src, folder):
    manifest = json.loads(_read(MANIFEST))
    assert any(c["name"] == name for c in manifest["components"])
    assert any(sp["name"] == name for sp in manifest["startingPoints"])
    assert macro in _macro_names(), f"no shared `{macro}` macro for {name}"
    bundle = _read(os.path.join(DESIGN_DIR, "_ds_bundle.js"))
    assert src in bundle and f"__ds_ns.{name} = __ds_scope.{name};" in bundle
    stem = src.split("/")[-1][:-4]
    for f in (stem + ".jsx", stem + ".d.ts", stem + ".prompt.md"):
        assert os.path.exists(os.path.join(DESIGN_DIR, folder, f)), f"missing {f}"


@pytest.mark.parametrize("name", [n for n, _, _, _ in _NEW_017])
def test_017_component_documented_in_readme(name):
    readme = _read(os.path.join(DESIGN_DIR, "readme.md"))
    assert name in readme, f"readme.md does not document {name}"
