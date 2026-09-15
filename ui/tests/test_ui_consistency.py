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


# ── spec 009 US2 / FR-024: every button and table carries its design-system class ──
# Control styling lives in the shared macros (templates/components/macros.html) + app.css,
# never per page; recomposed pages compose those macros (FR-006).


def test_every_template_button_is_ax_btn():
    # A literal <button> in server markup must carry class="ax-btn" (the design-system button).
    for path in _walk(_TEMPLATES, ".html"):
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r"<button\b[^>]*>", text):
            assert "ax-btn" in m.group(0), f"raw <button> without ax-btn in {os.path.basename(path)}"


def test_every_template_table_is_ax_table():
    # A literal <table> in server markup must carry class="ax-table" (the design-system table).
    for path in _walk(_TEMPLATES, ".html"):
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r"<table\b[^>]*>", text):
            assert "ax-table" in m.group(0), f"raw <table> without ax-table in {os.path.basename(path)}"


def test_modules_that_create_buttons_set_ax_btn():
    # Any module that builds a <button> in JS must set the design-system class on it (T014).
    # dropdown.js is the shared custom-dropdown implementation whose trigger is its own control
    # (frozen behaviour, FR-025) — excluded, exactly as the <select> guard above excludes it.
    for path in _walk(_STATIC, ".js"):
        base = os.path.basename(path)
        if base == "dropdown.js":
            continue
        text = open(path, encoding="utf-8").read()
        if 'createElement("button")' not in text:
            continue
        assert "ax-btn" in text, f"{base} creates a <button> but never sets ax-btn"


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
    # The retired Automation page's #ax-automation-banner / .ax-banner save notice must not
    # reappear anywhere in the served tree.
    for path in list(_walk(_TEMPLATES, ".html")) + list(_walk(_STATIC, ".js")):
        text = open(path, encoding="utf-8").read()
        assert "ax-automation-banner" not in text, f"stale save banner in {os.path.basename(path)}"


def test_theme_control_is_accessible_icon_buttons():
    # Bug theme-control-overflow: the sidebar theme control is a radiogroup of three
    # icon-only buttons (System/Light/Dark) that fits the narrow column, each with an
    # accessible name (aria-label) and a hover tooltip (title); no native <select>.
    base = open(os.path.join(_TEMPLATES, "base.html"), encoding="utf-8").read()
    group = re.search(r'<div class="ax-theme-control"[^>]*>(.*?)</div>', base, re.DOTALL)
    assert group, "theme control radiogroup not found"
    block = group.group(0)
    assert 'role="radiogroup"' in block and 'aria-label="Theme"' in block
    assert "<select" not in block, "theme control must not use a native <select>"
    choices = re.findall(r'data-theme-choice="(system|light|dark)"', block)
    assert set(choices) == {"system", "light", "dark"}, f"expected all three choices, got {choices}"
    # Every option is a button with an accessible name and a hover title.
    for m in re.finditer(r"<button\b[^>]*>", block):
        tag = m.group(0)
        assert 'data-theme-choice="' in tag
        assert "aria-label=" in tag, f"theme option missing aria-label: {tag}"
        assert "title=" in tag, f"theme option missing hover title: {tag}"
        assert "ax-btn" in tag, f"theme option missing design-system button class: {tag}"


# ── US5: checks require an asset — the Checks card lives inside the Asset card ──
# (spec 008, FR-011, contract check-model §4). A job-only agent never renders it, and
# the checks list is dropped on collect when the asset gate is off.

def _fn_body(text, name):
    """Slice a top-level `function <name>(` … up to the next top-level `function `."""
    start = text.index(f"function {name}(")
    nxt = text.find("\nfunction ", start + 1)
    return text[start : nxt if nxt != -1 else len(text)]


def test_checks_card_rendered_only_inside_asset_card():
    text = open(os.path.join(_STATIC, "agent-form.js"), encoding="utf-8").read()
    # The checks editor is built in buildAssetCard (so it is present only for an asset)…
    assert "renderChecks()" in _fn_body(text, "buildAssetCard")
    # …and never in the Job card, so a job-only agent has no Checks control (FR-011).
    assert "renderChecks" not in _fn_body(text, "buildJobCard")


def test_collect_drops_checks_when_asset_gate_off():
    text = open(os.path.join(_STATIC, "agent-form.js"), encoding="utf-8").read()
    body = _fn_body(text, "collect")
    # checks are children of the produces block: when the Asset card is off they are dropped
    # alongside asset/partition/asset_schedule (contract check-model §4).
    assert "delete agent.checks" in body
    # the drop sits in the gate-off branch, after the drops of the other produces children.
    assert body.index("delete agent.checks") > body.index("delete agent.asset")


# ── spec 011 US1 / SC-006: the rebuilt tabbed agents list carries its design-system classes ──
_SCHED_AGENT = (
    "name: sched-agent\nharness: api\nmodel: cheap\nprompt_file: hello-example.md\n"
    "output_dir: /data/outputs/sched-agent\njob: true\ntriggers:\n  job_schedule: \"0 7 * * *\"\n"
)


def test_agents_list_uses_design_system_classes(client, tmp_agents):
    # A scheduled agent so the schedule pill actually renders in the served markup.
    (tmp_agents / "sched-agent.yaml").write_text(_SCHED_AGENT, encoding="utf-8")
    html = client.get("/agents").text

    # Full-bleed list view with no page header (contract §B).
    assert "ax-list-view" in html
    assert "ax-page-header" not in html
    # Tabs with counts, toolbar, show-disabled checkbox, full-bleed table.
    assert "ax-tabs" in html and "ax-tab-count" in html
    assert "ax-list-toolbar" in html and "ax-list-toolbar-group" in html
    assert "ax-checkbox" in html          # show-disabled control
    assert "ax-table--full-bleed" in html
    # Pills for the scheduled agent, kind badge, and the New-agent primary button.
    assert "ax-schedule-pill" in html
    assert "ax-badge--job" in html
    assert "ax-btn--primary" in html


def test_agents_list_after_paint_columns_are_placeholders(client, tmp_agents):
    # Columns 6–8 ship as em-dash placeholders the activity JS fills after first paint.
    (tmp_agents / "sched-agent.yaml").write_text(_SCHED_AGENT, encoding="utf-8")
    html = client.get("/agents").text
    for cls in ("ax-col-latest", "ax-col-checks", "ax-col-history"):
        assert cls in html
    assert "/static/agents-list.js" in html
