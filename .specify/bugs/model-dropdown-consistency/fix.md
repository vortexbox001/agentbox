# Bug Fix: Model field bypasses the custom dropdown; dropdown should size to its widest option

- **Slug**: model-dropdown-consistency
- **Fixed**: 2026-09-11
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

The codex model field now goes through the shared custom dropdown (`renderModelSelectWithCustom`) with the model suggestions as choices and a "Custom model id…" entry accepting any id; the free-text-plus-`<datalist>` path is deleted. The custom dropdown's default width is now intrinsic — the wrapper sizes to its widest option via an invisible sizer — instead of stretching to the container. Both open questions were answered by the user: the tools-list autocomplete datalists stay out of scope, and intrinsic ("ragged") width applies everywhere with no full-width opt-back.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/static/agent-form.js` | modified | `renderModel` routes `custom: "any"` (codex) to `renderModelSelectWithCustom` with `model_suggestions` as choices; `renderModelText` (input + datalist) deleted; `validateCustom` gains an any-id mode (codex accepts anything non-empty); codex `modelNote` text updated |
| `ui/static/dropdown.js` | modified | `enhanceSelect` builds an `aria-hidden` `.ax-dropdown-sizer` inside the wrapper; `sync()` rebuilds it with one line per option so the wrapper's intrinsic width tracks the widest option |
| `ui/static/app.css` | modified | `.ax-dropdown` is now `width: max-content; max-width: 100%` (trigger keeps `width: 100%` of the wrapper); new `.ax-dropdown-sizer` rules mirror the trigger's horizontal box (border + padding + gap + chevron) plus a `--ax-space-8` allowance for a classic scrollbar |
| `ui/tests/test_ui_consistency.py` | added test | `test_model_control_never_uses_a_native_datalist` |
| `specs/002-design-system-compliance/contracts/components.md` | modified | §1 structure diagram gains the sizer node; styling contract records the intrinsic-width default as superseding the original full-width behavior |

## Diff Highlights

`agent-form.js` — the codex branch now reuses the select-with-custom machinery:

```js
if (custom === "none") return renderEnumSelect(id, f, rule.choices || [], !!rule.blank_ok);
// custom === "any" (codex): the suggestions are the choices; the custom entry takes any id.
if (custom === "any") return renderModelSelectWithCustom(id, f, { ...rule, choices: h.model_suggestions || [] });
return renderModelSelectWithCustom(id, f, rule);
```

```js
if (!v || anyModel) { setFieldError(f.id, null); return; }   // codex: any id is fine
```

`app.css` — intrinsic width default:

```css
.ax-dropdown { position: relative; width: max-content; max-width: 100%; }
```

## Tests Added or Updated

- `ui/tests/test_ui_consistency.py::test_model_control_never_uses_a_native_datalist` — pins that `renderModelText` stays deleted and that the only `createElement("datalist")` in `agent-form.js` lives inside `renderList` (the out-of-scope tools autocomplete), so the model field can never regress to a native dropdown.

## Local Verification

- Commands run: `cd ui && ../.venv/bin/python -m pytest -q` → **298 passed** (was 297; the new consistency test is included).
- Headless browser verification (scratch uvicorn :8089 + `chromium --headless=new` DevTools driver, fresh profile), 11/11 checks pass:
  - Create page, codex harness: `#f-model` is a `<select class="ax-select">` wrapped in `.ax-dropdown`, zero datalists; options = "— (harness default)" + the three suggestions + "Custom model id…".
  - Choosing "Custom model id…" reveals the text input; an arbitrary id produces no field error; claude-code custom ids are still regex-validated (negative case still errors).
  - Effort trigger is far narrower than its grid cell, its width equals the sizer's, and it does not change when the selection changes.
  - An open panel exactly matches the trigger width and every option renders on one line — including when `place()` caps the panel height and a 15px classic scrollbar appears (the case that initially caused "medium" to wrap; fixed by the space-8 allowance).
  - Edit page for a codex agent with an off-list `model:` maps onto the custom entry with the id pre-filled in the revealed input.
  - The prompt-file dropdown (long option labels) is capped at its container width.
  - Screenshots of `/agents/new` and `/automation` eyeballed: dropdowns hug their widest option ("Blank agent", "cron", "on demand", "Select a prompt…"), text inputs unchanged, nothing overlaps or clips.

## Deviations from Assessment

- The sizer needed one addition the assessment didn't anticipate: a `--ax-space-8` (16px) right-padding allowance so panel options stay on one line when the panel scrolls and a classic (non-overlay) scrollbar consumes ~15px of its inner width. Found during browser verification ("medium" wrapped in the effort dropdown when the panel height was capped).
- `ui/schema.py` was left untouched (the assessment listed it as optional): mapping `model_suggestions` into choices happens in `renderModel` in JS, keeping the server-side `custom: "any"` validation semantics exactly as they were.

## Addendum (2026-09-11, follow-up report)

A control revealed by a dropdown choice (the "Custom model id…" input) sat flush against the trigger. Added to `ui/static/app.css`: `.ax-dropdown + .ax-input, .ax-dropdown + .ax-textarea { margin-top: var(--ax-space-4); }` — the same 8px gap the new-prompt panel already had. Browser-verified: model reveal gap 8px, prompt panel gap 8px, automation rows (select + cron input side by side, input inside a wrapper div) unaffected. Tests still 298 passed.

## Follow-ups

- The `allowed_tools`/`disallowed_tools` free-text autocomplete datalists remain native by explicit decision; if a combobox variant of the custom dropdown is ever built, the new consistency test's renderList carve-out should be removed.
- The design-system guide page (`/design-system`) documents the dropdown component; its prose doesn't mention width so nothing was stale, but if a width note is ever added it should describe the intrinsic default.
