"""UI consistency greps (spec 006 US4 / SC-004/SC-005, contract ui-automation-and-shell §4/§6).

Static assertions over ui/templates and ui/static:
  * every <select> is on the shared custom-dropdown path (class ax-select), and every module
    that creates a <select> enhances it via dropdown.enhanceSelect(s);
  * no page uses the bespoke .ax-banner as a save/reload notice — the one shared notice pattern
    (shell.showStatus into #ax-status-region) is used instead.
"""
import os
import re

import pytest

_UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES = os.path.join(_UI_DIR, "templates")
_STATIC = os.path.join(_UI_DIR, "static")


def _walk(root, ext):
    for dirpath, _, names in os.walk(root):
        for n in names:
            if n.endswith(ext):
                yield os.path.join(dirpath, n)


def test_every_template_select_is_ax_select():
    # A literal <select> in server markup must carry class="ax-select" so dropdown.js enhances it.
    for path in _walk(_TEMPLATES, ".html"):
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r"<select\b[^>]*>", text):
            assert "ax-select" in m.group(0), f"raw <select> without ax-select in {os.path.basename(path)}"


def test_modules_that_create_selects_enhance_them():
    # Any module that builds a <select> in JS must route it through the shared dropdown
    # (className ax-select + enhanceSelect/enhanceSelects). dropdown.js is the implementation.
    for path in _walk(_STATIC, ".js"):
        base = os.path.basename(path)
        if base == "dropdown.js":
            continue
        text = open(path, encoding="utf-8").read()
        if 'createElement("select")' not in text:
            continue
        assert "ax-select" in text, f"{base} creates a <select> but never sets ax-select"
        assert re.search(r"enhanceSelects?\s*\(", text), f"{base} creates a <select> but never enhances it"


def test_model_control_never_uses_a_native_datalist():
    # Every single-choice control goes through the shared custom dropdown; a native
    # <datalist> on the model field is the one that slipped through for codex
    # (bug model-dropdown-consistency). The only datalist allowed in agent-form.js
    # is the free-text token autocomplete inside renderList (tools suggestions).
    text = open(os.path.join(_STATIC, "agent-form.js"), encoding="utf-8").read()
    assert "renderModelText" not in text, "codex model must use the shared dropdown, not free text + datalist"
    occurrences = [m.start() for m in re.finditer(r'createElement\("datalist"\)', text)]
    render_list = text.index("function renderList(")
    assert all(pos > render_list for pos in occurrences), (
        "a <datalist> is created outside renderList — choice controls must use dropdown.enhanceSelect"
    )


def test_no_bespoke_save_banner_remains():
    # The Automation page's #ax-automation-banner / .ax-banner save notice is retired.
    for path in list(_walk(_TEMPLATES, ".html")) + list(_walk(_STATIC, ".js")):
        text = open(path, encoding="utf-8").read()
        assert "ax-automation-banner" not in text, f"stale save banner in {os.path.basename(path)}"
    # automation.js uses the shared notice, not a bespoke banner.
    auto = open(os.path.join(_STATIC, "automation.js"), encoding="utf-8").read()
    assert "ax-banner" not in auto
    assert "showStatus" in auto


def test_automation_uses_shared_dropdown_and_notice():
    auto = open(os.path.join(_STATIC, "automation.js"), encoding="utf-8").read()
    assert "enhanceSelects" in auto and "/static/dropdown.js" in auto
    assert "/static/shell.js" in auto
