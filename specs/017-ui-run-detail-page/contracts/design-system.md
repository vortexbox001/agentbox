# Contract: Design-system components for the run detail page

The five new presentation components this feature adds, each **design-system-first** (FR-037,
Principle VII): component source + specimen card under `ui/design-system/components/…`, a
`_ds_manifest.json` entry, a rebuilt `_ds_bundle.js`, a `readme.md` section, and only then a shared
Jinja macro in `ui/templates/components/macros.html` used on `runs/detail.html`. Styling resolves from
tokens only — no literal colours/pixels, no `font-family`, no inline `style`/`<style>` (FR-036,
SC-009). The existing `timeline`/`tool_call`/`diff_block`/`tool_out` macros are **left unchanged** for
the compare page (FR-037).

## Common conformance guarantees (all five)

- Registered in `_ds_manifest.json` (`name` + `sourcePath`, plus a `startingPoints` specimen) so
  `test_design_system_sync.py` sees manifest ↔ macro ↔ bundle parity.
- Documented in `ui/design-system/readme.md` so `test_design_system_docs.py` passes.
- Composed from / alongside existing macros where one exists (e.g. `file_row`, `button`, the
  `ax-result` check mark) rather than hand-rolled (FR-036).
- All colours/spacing/type/radius/shadow/transition via `var(--…)` tokens; the clamp fade colour
  follows the **background token** (FR-036, SC-009).

## 1. Disclosure / section card — `components/layout/Disclosure.jsx`, macro `disclosure`

A bordered card with a full-width, keyboard-operable disclosure header.

| Prop | Meaning |
|------|---------|
| `title` | Section title. |
| `note` | Right-aligned muted closed-state note. |
| `open` | Default open/closed (server default; client may override). |
| `id` | Stable section id for persistence + `aria-controls`. |
| body | Caller content (the section body). |

**Guarantees**: header is focusable, toggled by click/Enter/Space, exposes `aria-expanded` reflecting
state, and shows a chevron indicating state (FR-003). Used for all five sections.

## 2. IN/OUT tool card — `components/data/ToolCard.jsx`, macro `tool_card`

| Prop | Meaning |
|------|---------|
| `name` | Tool name (head). |
| `description` | The call's description, ellipsised on one line. |
| `marker` | `exit N` \| `failed` \| none, right-aligned mono. |
| `in_text` / `out_text` | The `IN` and `OUT` row contents. |
| `in_overflow` / `out_overflow` | Show the fade + "Show all N lines" link when true. |
| `in_lines` / `out_lines` | Line counts for the link label. |
| `is_diff` | OUT row renders as a diff, expanded by default, colouring preserved. |
| `out_intent` | `failed` (failed colour) \| `missing` (warning colour) \| none. |

**Guarantees**: rows clamp to 3 visible lines with a token-background fade only when overflowing
(FR-024); the row/link expand control is keyboard-operable with `aria-expanded` and flips "Show all N
lines" ↔ "Show less" (FR-025); diff colouring survives (FR-026); missing/failed OUT rows read in the
warning/failed colour (FR-027).

## 3. Check row — `components/data/CheckRow.jsx`, macro `check_row`

Reuses the existing `ax-result` mark + `CHECK_META` (pass/warn/fail-blocking/not-run) so the mark and
icon match the Agents overview (FR-015/FR-016).

| Prop | Meaning |
|------|---------|
| `status` | `pass` \| `warn` \| `fail-blocking` \| `not-run` → mark + icon. |
| `name` | Check name. |
| `detail` | One-line detail (`—` when absent). |
| `recorded` | Recorded time, right-aligned (`—` when absent). |

**Guarantees**: same visual language as the Agents overview Checks column; no new check vocabulary.

## 4. Produced-elsewhere row — `components/data/ProducedRow.jsx`, macro `produced_row`

| Prop | Meaning |
|------|---------|
| `kind` | `pull_request` \| `commit` \| `file` → label Pull request / Commit / File. |
| `identifier` | URL / short SHA / path, in mono. |
| `action` | Open (URL) / Preview (file) / none. |

**Guarantees**: rendered only when the miner supplies a row; grouped by kind (PRs → commits → files),
event order within kind (FR-012).

## 5. Rendered summary — `components/data/Summary.jsx`, macro `summary`

The visual treatment for the FR-007 subset produced by `render_summary` (§D of the run-detail
contract): headings as small uppercase labels, `bold`, inline-code chips, bullet lists, and links.

| Prop | Meaning |
|------|---------|
| `html` | The pre-rendered, escaped subset HTML. |
| `fallback` | Optional foot-line fallback content when no message exists. |

**Guarantees**: no raw markdown/HTML markup is visible (SC-003); the treatment resolves from tokens
only, verified in light/dark/Indigo themes (SC-009).

## Test hooks (SC-010)

`test_design_system_sync.py` (manifest ↔ macro ↔ bundle parity for the five new components),
`test_design_system_docs.py` (readme documents each), and `test_conformance.py` (tokens-only,
macro-composed, no inline styles, no literal colours/pixels) MUST all pass with the new markup, and the
golden run fixtures MUST render every section.
