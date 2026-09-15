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


def test_theme_control_is_accessible_icon_buttons(client):
    # FR-003 accessibility "move" (finding I2): US2 removed the foot theme radiogroup and
    # US3 (T028) relocates the theme control to the settings modal dropdown. This asserts
    # both halves of the move.
    base = open(os.path.join(_TEMPLATES, "base.html"), encoding="utf-8").read()
    # US2 half: the sidebar radiogroup is gone.
    assert "ax-theme-control" not in base, "the foot theme radiogroup must be removed (FR-003)"
    assert 'role="radiogroup"' not in base, "no theme radiogroup remains in the shell (FR-003)"
    assert "data-theme-choice" not in base, "the radiogroup theme-choice buttons must be gone"

    # US3 half: the theme control lives in a labelled settings-modal dropdown with iconed
    # options (contract shell-and-modal §D/§E, FR-005/007). The modal markup lives in a
    # <template> in base.html rendered on every page (via the ui.select macro), so this
    # reads the rendered HTML. settings.js clones the template and enhances the native
    # select with the shared dropdown, so at runtime the panel is an accessible
    # role="listbox" of role="option" rows (that mechanism lives in dropdown.js, below).
    html = client.get("/agents").text  # any page renders the shell (base.html) + the modal
    modal = re.search(r'<template id="ax-settings-modal">(.*?)</template>', html, re.DOTALL)
    assert modal, "the settings modal template must render into the shell (#ax-settings-modal)"
    mtext = modal.group(1)
    assert 'role="dialog"' in mtext and 'aria-modal="true"' in mtext, \
        "the settings modal must be a role=dialog / aria-modal panel (FR-005)"
    assert 'aria-labelledby="ax-settings-title"' in mtext and ">User settings<" in mtext, \
        "the settings modal must be labelled 'User settings' (FR-005)"
    # A labelled theme control (the select the shared dropdown enhances).
    assert re.search(r'<label for="ax-theme-select">\s*Theme\s*</label>', mtext), \
        "the Theme row must carry a <label for> tying it to the theme control (FR-007)"
    theme_select = re.search(r'<select\b[^>]*id="ax-theme-select"[^>]*>', mtext)
    assert theme_select and "ax-select" in theme_select.group(0), \
        "the theme control must be an ax-select the shared dropdown enhances (research R5)"
    # Iconed options: Light / Dark / Use system setting, each with a lead icon; no indigo.
    for icon in ("theme-light", "theme-dark", "theme-system"):
        assert f'data-icon="{icon}"' in mtext, f"theme option missing its lead icon {icon} (FR-007)"
    assert "Use system setting" in mtext, "the 'Use system setting' option must be present"
    assert "indigo" not in mtext.lower() and "Dagster Indigo" not in mtext, \
        "the mock's fourth 'Dagster Indigo' theme option must be dropped (contract §C)"

    # The accessible listbox roles come from the shared dropdown (one keyboard model).
    dd = open(os.path.join(_STATIC, "dropdown.js"), encoding="utf-8").read()
    assert '"listbox"' in dd and '"option"' in dd, \
        "dropdown.js must build the role=listbox/role=option accessible control"
    settings = open(os.path.join(_STATIC, "settings.js"), encoding="utf-8").read()
    assert "enhanceSelect" in settings, \
        "settings.js must enhance the theme select with the shared dropdown (FR-007, R5)"


def test_settings_theme_persists_and_stamps_html():
    # SC-003 static coverage (finding G1): settings.js persists the theme preference to
    # localStorage["agentbox.theme"] and applies it by stamping/clearing data-theme on the
    # <html> element (FR-008/009). The full apply-without-reload / survives-reload / OS-flip
    # behaviour is the manual US3 quickstart check (browser-only).
    settings = open(os.path.join(_STATIC, "settings.js"), encoding="utf-8").read()
    assert '"agentbox.theme"' in settings, "settings.js must use the agentbox.theme localStorage key"
    assert "localStorage.setItem" in settings, "settings.js must persist the theme preference"
    assert re.search(r"localStorage\.getItem", settings), "settings.js must read the stored theme"
    assert 'setAttribute("data-theme"' in settings, "settings.js must stamp data-theme on <html>"
    assert 'removeAttribute("data-theme")' in settings, "settings.js must clear data-theme for light"
    assert "documentElement" in settings, "settings.js must apply the theme to <html>"


def test_shell_foot_has_dagster_keyline_and_links():
    # US2 (contract shell-and-modal §B, SC-004): the foot on every page (base.html) shows,
    # top to bottom, the Dagster status block → a keyline → Hide navigation → Settings.
    base = open(os.path.join(_TEMPLATES, "base.html"), encoding="utf-8").read()
    foot = re.search(r'<div class="ax-sidebar-foot">(.*?)</div>\s*</aside>', base, re.DOTALL)
    assert foot, "sidebar foot not found"
    block = foot.group(1)
    # Dagster status block (its own indigo styling comes from .ax-dagster in app.css).
    assert "ax-dagster" in block, "foot missing the Dagster status block"
    # The keyline + the two foot links live in .ax-foot-links (border-top keyline in app.css).
    assert "ax-foot-links" in block, "foot missing the keyline'd foot-links group"
    # Hide navigation (the collapse control) and Settings, each a design-system button.
    hide = re.search(r'<button[^>]*id="ax-collapse-toggle"[^>]*>', block)
    settings = re.search(r'<button[^>]*id="ax-settings-link"[^>]*>', block)
    assert hide and "ax-btn" in hide.group(0), "foot missing Hide-navigation button"
    assert 'aria-label="Hide navigation"' in hide.group(0), "collapse link is not named 'Hide navigation'"
    assert settings and "ax-btn" in settings.group(0), "foot missing Settings button"
    assert 'aria-label="Settings"' in settings.group(0), "settings link is not named 'Settings'"
    # No theme radiogroup remains in the foot.
    assert "ax-theme-control" not in block, "the theme radiogroup must be gone from the foot"


def test_shell_collapse_exposes_show_navigation_name():
    # SC-004: collapsed, the foot collapse link's accessible name reads "Show navigation";
    # shell.js flips the aria-label on collapse (the label span is hidden by CSS).
    shell = open(os.path.join(_STATIC, "shell.js"), encoding="utf-8").read()
    assert "Show navigation" in shell and "Hide navigation" in shell, \
        "shell.js must toggle the collapse link between 'Hide navigation' and 'Show navigation'"
    assert "ax-theme-control" not in shell, "shell.js must not still wire the removed theme radiogroup"


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
