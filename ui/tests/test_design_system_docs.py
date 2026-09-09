"""Constitution VI (Docs Track Reality): ARCHON-DESIGN-SYSTEM.md must describe the
reference files it documents. These checks read the guide and the reference canvas
and assert the guide's component and grid claims are present and not contradicted."""
import os
import re

import pytest


UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_DIR = os.path.join(UI_DIR, "design-system")
GUIDE = os.path.join(DESIGN_DIR, "ARCHON-DESIGN-SYSTEM.md")
REFERENCE = os.path.join(DESIGN_DIR, "Archon Design System.dc.html")

GRID_PATTERNS = [
    "ax-grid-stats",
    "ax-grid-cards",
    "ax-grid-cards-lg",
    "ax-grid-detail",
    "ax-grid-split",
    "ax-grid-form",
]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _squash(s):
    return re.sub(r"\s+", "", s)


def _section(text, heading):
    """Body of a `### heading` section up to the next heading of any level."""
    m = re.search(r"^### " + re.escape(heading) + r"\s*$(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S)
    assert m, f"guide has no '### {heading}' section"
    return m.group(1)


def _grid_row(text, pattern):
    """(columns, gap) from the named-grid table row for `pattern`."""
    m = re.search(r"^\|\s*`" + re.escape(pattern) + r"`\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|", text, re.M)
    assert m, f"guide's grid table has no row for {pattern}"
    return m.group(1), m.group(2)


@pytest.mark.parametrize("pattern", GRID_PATTERNS)
def test_guide_lists_each_named_grid_pattern(pattern):
    columns, gap = _grid_row(_read(GUIDE), pattern)
    assert columns and gap


@pytest.mark.parametrize("pattern", [p for p in GRID_PATTERNS if p != "ax-grid-cards-lg"])
def test_guide_grid_rules_match_reference_specimens(pattern):
    # The reference canvas renders each pattern with inline styles; the guide's
    # column rule and gap must appear there verbatim (whitespace-insensitive).
    columns, gap = _grid_row(_read(GUIDE), pattern)
    reference = _squash(_read(REFERENCE))
    assert f"grid-template-columns:{_squash(columns)};gap:{_squash(gap)}" in reference, (
        f"{pattern}: guide says {columns!r} / {gap!r} but the reference has no such specimen"
    )


def test_guide_large_card_grid_matches_reference_note():
    columns, _gap = _grid_row(_read(GUIDE), "ax-grid-cards-lg")
    assert "minmax(360px" in _squash(columns)
    assert "minmax(360px,1fr)" in _squash(_read(REFERENCE))


def test_guide_documents_select_dropdown_component():
    body = _section(_read(GUIDE), "Select / Dropdown")
    # Native styled select: appearance-none with a custom chevron on bg-input.
    assert "appearance" in body and "chevron" in body.lower()
    assert "--ax-bg-input" in body
    # Custom dropdown component: elevated panel with accent-highlighted selection.
    assert "--ax-bg-card" in body
    assert "--ax-border-strong" in body
    assert "--ax-shadow-lg" in body
    assert "--ax-cyan-bg" in body
    assert "--ax-radius-sm" in body


def test_guide_dropdown_tokens_match_reference():
    reference = _read(REFERENCE)
    assert "Custom Dropdown (open)" in reference
    for token in ("--ax-bg-card", "--ax-border-strong", "--ax-shadow-lg", "--ax-cyan-bg", "--ax-radius-sm"):
        assert token in reference


def test_guide_toggle_matches_reference():
    body = _section(_read(GUIDE), "Toggle")
    reference = _squash(_read(REFERENCE))
    assert "36px" in body and "20px" in body and "16px" in body
    assert "width:36px;height:20px" in reference
    assert "width:16px;height:16px" in reference
    assert "cyan" in body and "background:var(--ax-cyan)" in reference
