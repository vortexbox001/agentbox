"""Styling-hygiene conformance checks (spec 009 FR-022) — the acceptance gate for
SC-005. A static-grep pytest module mirroring ``secret_scan.py`` / ``test_secrets.py``:
served app styling must express every colour, pixel value, and typeface through a
design-system ``var(--…)`` token, never a literal and never a retired ``--ax-*`` token.

Scanned trees (conformance-checks.md): ``ui/templates/``, ``ui/static/``, and the
served bundle CSS at ``ui/design-system/*.css``. Exempt (literals allowed): the token
files ``ui/design-system/tokens/*.css`` and any self-hosted font file — everything
else is app styling held to the token rule.

The external-font/CDN/asset-URL half of FR-022 is enforced by ``test_no_external_urls``
(US4/T025): no served style/markup/script may reference ``googleapis``/``unpkg``/``cdn``
or any other ``http(s)://`` asset URL, so the UI renders with egress blocked. This module
fails on an inserted literal colour, literal pixel value, ``--ax-*`` token, or external URL,
and passes clean on the migrated tree.
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


def _url_scanned_files():
    """(path, raw text) for every served text file in the egress scope (T025):
    ``ui/templates/`` (html), ``ui/static/`` (css/js/html), and the served bundle CSS
    ``ui/design-system/*.css`` — including ``tokens/`` here (where the retired Google
    Fonts ``@import`` lived and where the local ``@font-face`` ``url()``s now point), which
    the literal-token scan exempts. Font binaries are not text and are skipped. Comments
    are NOT stripped: a commented-out external ``@import`` is a latent egress risk, so it
    still fails."""
    roots = []
    for dirpath, _, names in os.walk(_TEMPLATES):
        roots += [os.path.join(dirpath, n) for n in names if n.endswith(".html")]
    for dirpath, _, names in os.walk(_STATIC):
        roots += [os.path.join(dirpath, n) for n in names if n.endswith((".css", ".js", ".html"))]
    for n in sorted(os.listdir(_DESIGN)):          # bundle root, e.g. styles.css
        if n.endswith(".css"):
            roots.append(os.path.join(_DESIGN, n))
    for n in sorted(os.listdir(_TOKENS)):          # tokens/*.css — included for URLs
        if n.endswith(".css"):
            roots.append(os.path.join(_TOKENS, n))
    for path in sorted(set(roots)):
        yield path, open(path, encoding="utf-8").read()


# ── Patterns ────────────────────────────────────────────
_AX_TOKEN = re.compile(r"--ax-[\w-]*")                       # def or var() ref
_PX = re.compile(r"\b\d+px\b")                               # literal pixel value
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")                    # #rgb / #rrggbb / #rrggbbaa
_COLOR_FN = re.compile(r"\b(?:rgba?|hsla?)\s*\(")            # rgb()/rgba()/hsl()/hsla()
_FONT_FAMILY = re.compile(r"font-family", re.IGNORECASE)
_INLINE_STYLE = re.compile(r"style\s*=\s*[\"']")            # inline style="…" attribute
_STYLE_BLOCK = re.compile(r"<style[\s>]", re.IGNORECASE)    # embedded <style> block
_VAR_CALL = re.compile(r"var\([^)]*\)")
# Any absolute http(s) URL, and the CDN/font hosts the migration must never reference.
_URL = re.compile(r"https?://[^\s\"')]+", re.IGNORECASE)
# XML/SVG/metadata namespace URIs are identifiers, not fetched assets — never egress.
_NS_ALLOW = re.compile(r"^https?://(?:www\.)?(?:w3\.org|c2pa\.org)/", re.IGNORECASE)
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


def test_no_inline_styles_in_app_templates():
    """App CSS lives in dedicated stylesheets (Constitution VII): no template under
    ``ui/templates/`` may carry an inline ``style="…"`` attribute or an embedded
    ``<style>`` block. The self-contained design-system reference pages under
    ``ui/design-system/`` are the sole exception (offline standalone documents) and are
    not scanned here."""
    bad = []
    for dirpath, _, names in os.walk(_TEMPLATES):
        for n in names:
            if not n.endswith(".html"):
                continue
            path = os.path.join(dirpath, n)
            text = _strip_comments(open(path, encoding="utf-8").read(), "html")
            hits = []
            if _INLINE_STYLE.search(text):
                hits.append("inline style=")
            if _STYLE_BLOCK.search(text):
                hits.append("<style> block")
            if hits:
                bad.append(f"{_rel(path)}: {hits}")
    assert not bad, f"embedded CSS in app template(s) — move it to a stylesheet: {bad}"


def test_no_external_urls():
    """No served style/markup/script references an external asset (FR-017/FR-022, US4).

    Fails on any ``http(s)://`` URL — Google Fonts, unpkg, any CDN, any font/icon/asset
    host — outside XML/SVG/metadata namespaces, so the UI renders with egress blocked.
    """
    bad = []
    for p, t in _url_scanned_files():
        offenders = [u for u in _URL.findall(t) if not _NS_ALLOW.match(u)]
        if offenders:
            bad.append(f"{_rel(p)}: {offenders[:5]}")
    assert not bad, f"external asset URL(s) — must be self-hosted — in: {bad}"


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
    # Embedded CSS in a template fires the inline-style / <style>-block gates.
    assert _INLINE_STYLE.search('<p style="margin-top:0">')
    assert _STYLE_BLOCK.search("<style>.x{}</style>")
    # External-URL gate fires on a CDN import but not on an SVG namespace URI.
    imp = "@import url('https://fonts.googleapis.com/css2?family=Inter');"
    assert [u for u in _URL.findall(imp) if not _NS_ALLOW.match(u)]
    assert not [u for u in _URL.findall('xmlns="http://www.w3.org/2000/svg"')
                if not _NS_ALLOW.match(u)]
