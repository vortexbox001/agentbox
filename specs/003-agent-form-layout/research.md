# Research: Agent Form Layout

Phase 0 output. Each entry records a decision, why, and what else was considered. There were no `NEEDS CLARIFICATION` markers in the spec; the entries below resolve the choices the spec deferred to planning (FR-011 thresholds, the Job column ratio) and the implementation questions the codebase raises.

## R1. Where the grouping lives

**Decision**: In `ui/schema.py`, as data. Add a `GROUPS` list (`runs`, `job`, `box`), replace `SECTIONS` with the nine new cards each carrying a `group` (the `identity` section carries `group: None` and renders in the lead strip), and change each field's `section` to its new card. `FIELDS` is reordered so fields are contiguous by section in `SECTIONS` order, because both the emitter and `applicable_fields` take their within-section order from `FIELDS`.

**Rationale**: The emitter (`agents_store.emit_yaml`) and the form (`renderForm`) both already iterate `SECTIONS` and filter `FIELDS` by `section`. Changing the data changes both consumers at once, which is exactly what spec FR-015 asks for (file order equals screen order) and what Constitution II (configuration over code) prefers. No emitter code changes.

**Alternatives considered**:
- A separate UI-only grouping map in `agent-form.js`, leaving the YAML order alone. Rejected: two orders to maintain, and the spec explicitly wants the file to read like the screen.
- Keeping the old section ids and adding a `card` attribute per field. Rejected: the old ids would no longer describe anything, and the emitter's headers come from section labels.

## R2. How the three arrangements are selected

**Decision**: Container queries on the content pane. `.ax-content` gets `container-type: inline-size; container-name: ax-content`. The sections mount becomes `.ax-grid-agent`, a named-area grid:

| Content pane inline size | Columns | Areas |
|---|---|---|
| below 720px | 1 | `"runs" "job" "box"` |
| 720px to 1319px | 2 | `"runs job" "box job"` (Job spans both rows) |
| 1320px and up | 3 | `"runs job box"` with columns `1fr 1.4fr 1fr` |

Gap is `var(--ax-space-9)` (20px), the design system's detail-layout gap. `align-items: start` so a short group never stretches. Each group is a flex column of cards with the same gap, so cards keep natural height (spec FR-012).

**Why these numbers**: The design system's minimum form-field width is 280px and card padding is 24px a side, so the narrowest useful card is 328px. Two columns need 2×328 + 20 = 676px; 720px adds slack for the pane's scrollbar. Three columns with Job at 1.4× need 328 + 460 + 328 + 40 = 1156px at the bare minimum; 1320px is chosen so Runs and Box get about 437px at the smallest three-column width rather than a cramped 328px. Checked against the spec's reference widths (sidebar 220px, pane padding 28px a side):

| Viewport | Pane inline size | Arrangement |
|---|---|---|
| 1800px | 1524px | 3 columns (Job ≈ 611px, Runs/Box ≈ 437px) |
| 1440px | 1164px | 2 columns (≈ 572px each) |
| 900px | 624px | 1 column |

**Why a container query rather than a media query**: The sidebar is a fixed 220px today, so a media query would give the same result, but a container query keys the layout to the space the form actually has and keeps working if the sidebar ever collapses or the form is embedded elsewhere. Browsers without container-query support (pre-2023) get the single-column arrangement, which is correct, just less dense.

**Why explicit thresholds at all**: The design system says "no fixed breakpoints, use auto-fill + minmax()". Auto-fill cannot express "fold the third column under the first and let the second span". This is a documented exception (spec Assumptions; guide update in R7).

**Alternatives considered**:
- `repeat(auto-fill, minmax(…))` over the eight cards directly. Rejected: cards would land in whatever column comes next, breaking the Runs/Job/Box grouping and the Runs-first rule.
- Three independent flex columns with JavaScript moving Box under Runs on resize. Rejected: JavaScript for what CSS grid areas do declaratively.
- CSS multi-column (`columns: 3`) with `break-inside: avoid`. Rejected: fill order is top-to-bottom then next column, which cannot pin Job to the middle, and absolutely positioned dropdown panels behave unpredictably inside multicol fragments.

## R3. Job column width

**Decision**: `minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 1fr)` at three columns; equal `minmax(0, 1fr)` twice at two columns.

**Rationale**: Job holds every wide control (prompt picker, chip editors, env rows). 1.4 gives it about 40% of the width at 1800px, enough that env rows keep key, value, and remove button on one line. `minmax(0, …)` stops a long unbreakable value (a path or a model id) from widening its column. Ratios are not tokens in the design system (its own `ax-grid-detail` uses `1fr minmax(0, 340px)`), so a literal ratio is consistent with existing patterns.

**Alternatives considered**: equal thirds (env rows wrap at 1800px), or a fixed Job width (does not scale to ultra-wide screens).

## R4. Lead strip

**Decision**: A non-card container `#ax-form-lead` rendered by the template, laid out with the existing `.ax-grid-form` so its cells sit side by side and wrap at narrow widths. In create mode it holds the existing "Start from template" picker (moved out of its card) and a mount `#ax-form-lead-fields`; in edit mode only the mount. `renderForm` places the fields of any section whose `group` is `None` (today: only `name`) into that mount instead of a card. `lockName` searches the lead mount rather than the sections mount.

**Rationale**: The spec removes the Identity card and wants name and template picker on one strip. Rendering `name` through the same `makeField` path keeps its validation-error mapping, read-only handling, and name-mismatch warning untouched.

**Alternatives considered**: Rendering the name field in the template. Rejected: it would bypass `makeField`, duplicating the error and read-only logic.

## R5. Group containers and headings

**Decision**: `renderForm` builds one `section.ax-form-group[data-group=<id>]` per entry in `GROUPS`, each starting with an `h2.ax-form-section-heading` showing the group label, followed by that group's cards in `SECTIONS` order. Cards keep their current `ax-card ax-form-section` markup, the uppercase label heading, and the inner `.ax-grid-form`. A group container is always rendered (every harness has at least one field in each group), so the grid areas are always occupied.

**Rationale**: Reuses the existing heading style (`--ax-type-display-sm`, already used for "File contents") rather than adding a type size, and keeps the card markup that spec 002's tests and styles target.

## R6. Reload toggle position

**Decision**: No change. The `.ax-form-actionbar` holding the toggle already sits first inside the form, right-aligned, directly under the Save button. A page test pins that order so it cannot drift back to the bottom.

## R7. Design guide and doc-accuracy test

**Decision**: Add an "Agent form layout" subsection under the guide's Layout section describing `ax-grid-agent`: the three areas, the two thresholds, the Job ratio, and a sentence stating this is the one place the "no fixed breakpoints" rule is deliberately broken and why. Extend `test_design_system_docs.py` to read both `min-width` thresholds from the `.ax-grid-agent` container queries in `app.css` and assert the guide states the same numbers. The named-grid table is left alone because its rows are checked against specimens in the reference canvas, and this layout has no canvas specimen.

**Rationale**: Constitution VI prefers automated verification; matching numbers between guide and stylesheet is the claim most likely to rot.

## R8. Golden files and contract amendments

**Decision**: Regenerate the four `ui/tests/golden/*.yaml` from the definitions in `test_agents_store.py` (the quickstart gives the one-liner) and review the diff to confirm only headers and order moved. Add a test that the `# --- <label> ---` headers in an emitted file appear in `SECTIONS` order. Amend `specs/001-agent-management-ui/contracts/agent-yaml.md` §2 to point at this feature's `contracts/schema-and-yaml.md` for the section list instead of restating it, and relabel the applicability matrix rows in 001's `data-model.md` to the new card names.

**Rationale**: The golden files are the executable form of the YAML contract; regenerating them is how the contract change is proven. Pointing 001's contract at the new list keeps one statement of the order (solo-dev rule: state a fact once).

## R9. Things confirmed not to change

- Field-to-harness applicability (`harnesses` on each `SchemaField`) is untouched, so `applicable_fields` returns the same set per harness, only reordered.
- `collect()`, validation, error mapping (`[data-field]` lookups), the dirty snapshot, the YAML preview, the secret heuristic, the harness switch memory, and the network warning all key on field ids, not on sections, so they need no edits beyond `lockName` (R4).
- The `harness` field keeps its meta line (description and image) inside the Harness & model card.
- The uneditable-file page (parse error from a newer schema) renders no form and is unaffected.
