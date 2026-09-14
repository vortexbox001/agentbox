"""Styling-hygiene conformance checks (spec 009 FR-022) — the acceptance gate for
SC-005. A static-grep pytest module mirroring ``secret_scan.py`` / ``test_secrets.py``:
served app styling must express every colour, pixel value, and typeface through a
design-system ``var(--…)`` token, never a literal and never a retired ``--ax-*`` token.

Scanned trees (conformance-checks.md): ``ui/templates/``, ``ui/static/``, and the
served bundle CSS at ``ui/design-system/*.css``. Exempt (literals allowed): the token
files ``ui/design-system/tokens/*.css`` and any self-hosted font file — everything
else is app styling held to the token rule.

The external-font/CDN/asset-URL half of FR-022 is added to this same module by US4
(T025); this module already fails on an inserted literal colour, literal pixel value,
or ``--ax-*`` token and passes clean on the migrated tree.
"""
import os
import re

import pytest

_UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES = os.path.join(_UI_DIR, "templates")
_STATIC = os.path.join(_UI_DIR, "static")
_DESIGN = os.path.join(_UI_DIR, "design-system")
_TOKENS = os.path.join(_DESIGN, "tokens")


def _is_exempt(path: str) -> bool:
    """Token files and self-hosted font files may carry literals; nothing else."""
    if os.path.abspath(path).startswith(os.path.abspath(_TOKENS) + os.sep):
        return True
    lower = path.lower()
    if os.sep + "fonts" + os.sep in lower:
        return True
    return lower.endswith((".woff", ".woff2", ".ttf", ".otf")) or "font-face" in lower


def _kind(path: str) -> str:
    if path.endswith(".css"):
        return "css"
    if path.endswith(".js"):
        return "js"
    return "html"


def _strip_comments(text: str, kind: str) -> str:
    """Remove comments so literals mentioned in prose never trip a check."""
    if kind in ("css", "js"):
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    if kind == "html":
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    return text


def _scanned_files():
    """(path, kind, comment-stripped text) for every non-exempt scanned file."""
    roots = []
    for base, exts in ((_TEMPLATES, (".html",)), (_STATIC, (".css", ".js"))):
        for dirpath, _, names in os.walk(base):
            for n in names:
                if n.endswith(exts):
                    roots.append(os.path.join(dirpath, n))
    # Bundle CSS lives at the design-system root (styles.css); tokens/ is exempt.
    for n in sorted(os.listdir(_DESIGN)):
        if n.endswith(".css"):
            roots.append(os.path.join(_DESIGN, n))
    for path in sorted(roots):
        if _is_exempt(path):
            continue
        kind = _kind(path)
        text = open(path, encoding="utf-8").read()
        yield path, kind, _strip_comments(text, kind)


# ── Patterns ────────────────────────────────────────────
_AX_TOKEN = re.compile(r"--ax-[\w-]*")                       # def or var() ref
_PX = re.compile(r"\b\d+px\b")                               # literal pixel value
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")                    # #rgb / #rrggbb / #rrggbbaa
_COLOR_FN = re.compile(r"\b(?:rgba?|hsla?)\s*\(")            # rgb()/rgba()/hsl()/hsla()
_FONT_FAMILY = re.compile(r"font-family", re.IGNORECASE)
_VAR_CALL = re.compile(r"var\([^)]*\)")
# Named CSS colours (common subset), matched as standalone value tokens only —
# keywords like transparent/currentColor/inherit/none are intentionally excluded.
_NAMED = re.compile(
    r"(?<![\w-])(?:red|orange|yellow|green|blue|navy|teal|cyan|magenta|purple|violet|"
    r"pink|lime|white|black|gray|grey|silver|gold|brown|maroon|olive|aqua|fuchsia|"
    r"indigo|coral|salmon|khaki|crimson|turquoise)(?![\w-])",
    re.IGNORECASE,
)


def _rel(path: str) -> str:
    return os.path.relpath(path, _UI_DIR)


def test_no_ax_tokens():
    """No retired --ax-* custom property is defined or referenced in app styling."""
    bad = [_rel(p) for p, _, t in _scanned_files() if _AX_TOKEN.search(t)]
    assert not bad, f"--ax-* token(s) survive in: {bad}"


def test_no_literal_pixel_values():
    """Every size is a token: no literal Npx outside the exempt token/font files."""
    bad = [f"{_rel(p)}: {_PX.findall(t)[:5]}" for p, _, t in _scanned_files() if _PX.search(t)]
    assert not bad, f"literal px value(s) in: {bad}"


def test_no_literal_hex_or_functional_colours():
    """No #hex / rgb() / hsl() literal colour in app CSS, templates, or JS."""
    bad = []
    for p, _, t in _scanned_files():
        hits = _HEX.findall(t) + _COLOR_FN.findall(t)
        if hits:
            bad.append(f"{_rel(p)}: {hits[:5]}")
    assert not bad, f"literal colour(s) in: {bad}"


def test_no_named_colours_in_css():
    """No bare named colour in served CSS (token references are stripped first)."""
    bad = []
    for p, kind, t in _scanned_files():
        if kind != "css":
            continue
        stripped = _VAR_CALL.sub(" ", t)          # drop var(--color-…-red) etc.
        hits = _NAMED.findall(stripped)
        if hits:
            bad.append(f"{_rel(p)}: {sorted(set(hits))[:5]}")
    assert not bad, f"named colour literal(s) in: {bad}"


def test_no_stray_font_family():
    """font-family is declared only in the exempt font/token files."""
    bad = [_rel(p) for p, _, t in _scanned_files() if _FONT_FAMILY.search(t)]
    assert not bad, f"stray font-family declared in: {bad}"


# ── SC-005 negative-gate coverage (self-test of the checks) ──
def test_checks_catch_inserted_literals():
    """The patterns must fire on a deliberately non-conforming sample (Edge Case)."""
    sample = ".x { color: #ff0088; width: 12px; background: var(--ax-magenta); font-family: Comic Sans; }"
    stripped = _strip_comments(sample, "css")
    assert _HEX.search(stripped)
    assert _PX.search(stripped)
    assert _AX_TOKEN.search(stripped)
    assert _FONT_FAMILY.search(stripped)
    assert _NAMED.search(_VAR_CALL.sub(" ", ".y { border-color: navy; }"))
