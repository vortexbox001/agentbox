# Bug Assessment: Model field bypasses the custom dropdown; dropdown should size to its widest option

- **Slug**: model-dropdown-consistency
- **Created**: 2026-09-11
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim)

> on the agent create/edit page the model dropdown isn't using the custom dropdown we're using everywhere else; in fact the "custom dropdown" from the design system should become the only dropdown, and its default behavior should be to be as wide as the largest value

Two asks in one report:

1. **Bug**: the model field on the agent create/edit page shows a native browser dropdown instead of the Archon custom dropdown (`dropdown.js` / `.ax-dropdown`).
2. **Behavior change**: the custom dropdown should become the *only* dropdown in the UI, and its default width should be the width of its widest option (like a native `<select>`), instead of always filling its container.

## Symptom

When the harness is **codex**, the model field renders as a free-text `<input class="ax-input">` with a native `<datalist>` of suggestions (`gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.3-codex-spark`). The browser draws its own native suggestion dropdown for the datalist, which looks nothing like the Archon custom dropdown used by every other select on the form. Expected: the model picker uses the shared custom dropdown like every other choice control.

Separately, every enhanced dropdown is styled `width: 100%` of its grid cell (`.ax-dropdown-trigger { width: 100% }`, panel `left: 0; right: 0`), so it stretches to the container rather than sizing to its content. Expected (per the report): the default is intrinsic width — as wide as the largest option — so the control doesn't stretch and doesn't jump when the selection changes.

## Reproduction

Verified headlessly on 2026-09-11 (scratch uvicorn on :8089 + `chromium --headless=new` over the DevTools protocol, branch `006-explicit-asset-job` working tree):

1. Open `http://10.0.0.100:8080/agents/new` (or any codex agent's edit page, e.g. `/agents/repo-librarian-codex`).
2. Set Harness to **Codex** (on the codex edit page it already is).
3. Observe the Model field: it is `input#f-model.ax-input` with `list="f-model-list"` (native datalist), not wrapped in `.ax-dropdown`. For claude-code / pi / api the model field *is* a properly enhanced `select#f-model.ax-select.ax-dropdown-native` inside `.ax-dropdown`.
4. For the width half: open any enhanced dropdown (e.g. Effort) — the trigger spans the full grid-cell width regardless of option lengths.

DOM audit result: all 8 `<select>`s on the create page are enhanced; the codex model input (and the tools-list suggestion inputs) are the only native-dropdown surfaces left.

## Suspected Code Paths

- `ui/static/agent-form.js:434-441` — `renderModel()`: `rule.custom === "any"` (codex) routes to `renderModelText`, everything else to enhanced selects.
- `ui/static/agent-form.js:444-463` — `renderModelText()`: builds the plain input + `<datalist>` for codex. This is the reported native dropdown.
- `ui/schema.py:343-346` — codex `model_rule: {"choices": [], "custom": "any", "blank_ok": True}` plus `model_suggestions`; the empty `choices` is why the select path isn't taken.
- `ui/static/app.css:436-444` — `.ax-dropdown-trigger { width: 100%; }` — the always-full-width default the report wants changed.
- `ui/static/app.css:467-482` — `.ax-dropdown-panel { left: 0; right: 0; }` — panel width is tied to the trigger, so it follows whatever the trigger's width becomes.
- `ui/static/dropdown.js:135-163` — `sync()`: the place to (re)compute the widest-option width when options change.
- `ui/static/agent-form.js:452-459, 654-663` — the two `<datalist>` builders (codex model, tools-list suggestions) — the only remaining native-dropdown UI if "custom dropdown becomes the only dropdown" is taken literally.
- `ui/tests/test_ui_consistency.py:27-45` — the guard that forces every `<select>` through `enhanceSelect`; it has no rule about `<datalist>`, which is how the codex model field slipped through.

## Root Cause Hypothesis

Confidence: **high** (reproduced, single code path). Spec 002 ("design system compliance") routed every `<select>` through `enhanceSelect` and added a static test enforcing it — but the codex model control was deliberately built as a free-text input with a `<datalist>` (comment at `agent-form.js:433`: "codex → free text with a `<datalist>` of suggestions", research R4), and datalists are outside both the enhancement path and the consistency test. The full-width trigger is not a bug but the styling contract as written (spec 002 `contracts/components.md` §1 + §3: fields fill their `ax-grid-form` cells); the report is asking to change that default to intrinsic, widest-option sizing.

## Proposed Remediation

**Preferred**:

1. **Codex model → the shared custom dropdown.** In `renderModel()`, stop special-casing `custom === "any"` into free text. Render it with `renderModelSelectWithCustom(id, f, rule)` using `model_suggestions` as the choices and a trailing "Custom model id…" option that reveals the free-text input (validation: accept anything non-empty, since codex allows any id — unlike the claude-id/provider-model regexes). This reuses the existing select-with-custom machinery (claude-code and pi already work exactly this way), deletes `renderModelText` and its datalist, and preserves the "any model id" contract via the custom entry. A saved codex model that isn't in the suggestions list already maps onto the custom option by the existing `isCustom` logic at `agent-form.js:499-501`.
2. **Intrinsic dropdown width by default.** In `dropdown.js`, add a hidden sizer inside the wrapper (e.g. `div.ax-dropdown-sizer` refreshed in `sync()` with one line per option text, `visibility: hidden; height: 0; overflow: hidden`) so the trigger's intrinsic width equals its widest option plus chevron/padding. In `app.css`, change the default to size on content: `.ax-dropdown { display: inline-block; max-width: 100%; }`, drop `width: 100%` from the trigger (keep `width: 100%` *of the wrapper*, which now sizes to the sizer). The panel keeps `left: 0; right: 0`, so it automatically matches the new trigger width. Update the spec-002 components contract text to match, and check `test_design_system_docs.py` for any guide prose that asserts full-width.
3. **Guard the invariant.** Extend `test_ui_consistency.py` with a rule that no JS module or template creates a `<datalist>`-backed single-choice control for enum-like fields — pragmatically: assert `agent-form.js` contains no `datalist` in the model-rendering path (or no `datalist` at all if the tools lists are also converted, see below).

**Alternatives**:

- *Width via JS measurement instead of a sizer element* (measure each option with a canvas/offscreen span in `sync()` and set `min-width`): fewer DOM nodes but reflows on font load and duplicates text metrics logic; the CSS sizer is simpler and robust.
- *Scope-limit to the model field only* (leave `width: 100%` as the default, add an opt-in modifier): smaller blast radius, but contradicts the report's explicit "default behavior" ask.

**Files likely to change**:

- `ui/static/agent-form.js` (renderModel path; delete renderModelText or reduce to the custom-entry input)
- `ui/static/dropdown.js` (sizer in `sync()`)
- `ui/static/app.css` (dropdown width defaults, sizer class)
- `ui/schema.py` (optionally promote `model_suggestions` into `model_rule.choices` for codex so the UI needs no special case; keep `custom: "any"` semantics for validation)
- `ui/tests/test_ui_consistency.py` (datalist guard)
- `specs/002-design-system-compliance/contracts/components.md` (width contract text, if specs are treated as living)

**Tests to add or update**:

- `test_ui_consistency.py`: assert the model control path contains no `<datalist>` / that every choice control routes through `enhanceSelect`.
- `test_schema.py` / golden YAMLs: unchanged behavior — codex still accepts any model id and blank; a suggestion picked from the dropdown round-trips identically (existing `hello-codex.yaml` / `repo-librarian-codex.yaml` with `model: gpt-6-astra` are good fixtures).
- Manual/headless browser check (chromium DevTools harness): codex model field is wrapped in `.ax-dropdown`; picking "Custom model id…" reveals the text input; a dropdown's rendered width equals its widest option and does not change when the selection changes; long option lists still scroll and flip-up placement still works.

## Risks & Considerations

- **Global visual change**: intrinsic width alters every dropdown on every page (agent form, automation rows, template picker). Form columns will show ragged right edges where they used to be flush; confirm that's acceptable on the automation table rows, and re-check the flip-up/max-height placement math in `place()` still holds (it reads the trigger rect, so it should).
- **Very long option text** (e.g. a long custom model id shown as the current value, or prompt-file entries like `repo-librarian2.md — 6.1 KB · 2026-09-11`) would make the intrinsic width huge; keep `max-width: 100%` on the wrapper and the existing ellipsis on `.ax-dropdown-value` as the cap.
- **Codex validation loosening**: the select-with-custom path currently validates claude-id or provider/model formats; the codex branch must accept any non-empty string, so the `validateCustom` logic needs a third mode rather than reusing an existing regex.
- **Tools-list datalists** (`allowed_tools`/`disallowed_tools` suggestions) are also native dropdown UI. They are autocomplete on a free-text token input, not a choice control, so converting them means building a combobox variant of the custom dropdown — meaningfully more work than the model fix.
- Spec 002's components contract §1/§3 documents the current full-width behavior; the width change should update the contract (or be recorded as superseding it) so the docs tests and future audits don't flag the new default as a violation.

## Open Questions

- [NEEDS CLARIFICATION: Does "only dropdown" include the free-text autocomplete datalists on `allowed_tools`/`disallowed_tools` (a combobox build), or just single-choice controls like the model field? Assessment assumes the model field is the required scope and the tools lists are a follow-up.]
- [NEEDS CLARIFICATION: With intrinsic width as the default, should the agent-form fields opt back into full-width for visual alignment within `ax-grid-form`, or is ragged intrinsic width wanted there too? Assessment assumes intrinsic everywhere, capped at container width.]
