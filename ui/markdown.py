"""Dependency-free renderer for the Summary section's safe markdown subset (spec 017 FR-007, R2).

``render_summary(text)`` escapes **all** input first, then emits only the small subset the spec
names — paragraphs, ``##``/``###`` headings (as small uppercase labels), ``**bold**``,
```inline code```, ``-``/``*`` bullet lists, and URLs (bare or ``[label](url)``) as links. Anything
outside the subset (tables, raw HTML, blockquotes, images) renders as its already-escaped plain
text; **no raw HTML is ever passed through**, so the "no raw markup visible" guarantee (SC-003) is
structural rather than a sanitiser bolted on afterwards. No markdown library is added (FR-035).
"""
from __future__ import annotations

import re
from html import escape

from markupsafe import Markup

_HEADING = re.compile(r"^(#{2,3})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"(https?://[^\s<]+)")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text: str) -> str:
    """Inline formatting over already-escaped text: code, bold, and links (bare + labelled)."""
    # Stash labelled links so their inner URL is not double-linkified, then linkify bare URLs.
    stash: list[tuple[str, str]] = []

    def _keep(m: re.Match) -> str:
        stash.append((m.group(1), m.group(2)))
        return f"\x00L{len(stash) - 1}\x00"

    text = _MD_LINK.sub(_keep, text)
    text = _BARE_URL.sub(r'<a href="\1" rel="noopener">\1</a>', text)
    for i, (label, url) in enumerate(stash):
        text = text.replace(f"\x00L{i}\x00", f'<a href="{url}" rel="noopener">{label}</a>')
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    return text


def render_summary(text: str) -> Markup:
    """Render ``text`` as the FR-007 markdown subset → safe HTML (``Markup``).

    All input is HTML-escaped up front, so no ``<script>``/table/raw-HTML markup can ever go live
    (SC-003, edge case). Only the whitelisted constructs are re-emitted as tags.
    """
    if not text:
        return Markup("")
    out: list[str] = []
    bullets: list[str] = []
    para: list[str] = []

    def _flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def _flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{_inline(b)}</li>" for b in bullets)
            out.append(f"<ul class=\"ax-summary-list\">{items}</ul>")
            bullets.clear()

    for raw in escape(text).splitlines():
        line = raw.rstrip()
        if not line.strip():
            _flush_para()
            _flush_bullets()
            continue
        heading = _HEADING.match(line)
        if heading:
            _flush_para()
            _flush_bullets()
            out.append(f'<div class="ax-summary-h">{_inline(heading.group(2).strip())}</div>')
            continue
        bullet = _BULLET.match(line)
        if bullet:
            _flush_para()
            bullets.append(bullet.group(1).strip())
            continue
        _flush_bullets()
        para.append(line.strip())
    _flush_para()
    _flush_bullets()
    return Markup("".join(out))
