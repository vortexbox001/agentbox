# Quickstart: Agent Form Layout

Validation guide for feature 003. Contracts: [schema-and-yaml.md](contracts/schema-and-yaml.md), [layout.md](contracts/layout.md). Data model: [data-model.md](data-model.md).

## Prerequisites

- The `ui` service running (`docker compose up ui`) or the FastAPI app served locally from `ui/` in a venv with `requirements.txt` installed.
- At least one agent of each harness in `agents/` (the checked-in templates suffice for the api, pi, and codex harnesses).

## 1. Automated checks

From `ui/` inside the venv:

```bash
pytest
```

Expected: all tests pass, including the new or updated ones:

- schema: `groups` present and ordered; every section's `group` valid; exactly one lead section; `FIELDS` contiguous by section in `SECTIONS` order; every field's `section` exists.
- emitter: golden files match byte for byte; emitted `# --- … ---` headers appear in `SECTIONS` order.
- pages: create and edit pages carry `#ax-form-lead`, `#ax-form-sections` with class `ax-grid-agent`, and the reload actionbar before the lead strip.
- stylesheet: `.ax-grid-agent` declares the three `grid-template-areas` variants and `.ax-content` is an inline-size container.
- design guide: the "Agent form layout" section states the same two `min-width` thresholds as `app.css`.

## 2. Regenerating the golden files

Only needed once, when the schema order changes. From `ui/`:

```bash
python -c "import agents_store as st, tests.test_agents_store as t; [open(f'tests/golden/{h}.yaml','w').write(st.emit_yaml(d)) for h, d in t.GOLDEN.items()]"
```

Then review `git diff ui/tests/golden/`: every hunk should be a moved block or a renamed `# --- … ---` header. If any value line changes, stop; that is a bug, not a reorder.

## 3. Grouping and lead strip (spec US1)

Open `/agents/<a claude-code agent>` and confirm:

- [x] Reload toggle at the top right under Save; name in a read-only lead strip; no Identity card.
- [x] Runs: Schedule (Enabled, Schedule) then Limits (Timeout, Max turns).
- [x] Job: Prompt, Directories, Environment, Tools & permissions, in that order, with the fields listed in [data-model.md](data-model.md).
- [x] Box: Harness & model (Harness with its meta line, Model, Effort, Fallback model) then Container (Network, Memory, CPUs).
- [x] Group headings Runs, Job, Box are visible.

Open `/agents/new` and confirm the template picker and an editable Name share the lead strip. Pick the api template and confirm Tools & permissions disappears, Limits shows only Timeout, Directories shows only Output directory, and Harness & model shows Max tokens.

## 4. Arrangements (spec US2 to US4)

Use the browser's responsive design mode or resize the window. Check each width on the edit page of a claude-code agent:

| Width | Expect |
|---|---|
| 1800px | Three columns, Runs / Job / Box left to right; Job visibly wider; Runs cards stacked from the top with empty space below them, not stretched. |
| 1440px | Two columns: left holds Runs cards then Box cards; right holds Job for the full height. |
| 900px | One column: Runs, Job, Box. Environment rows with three variables fit without clipping. |

At every width: no horizontal scrollbar on the page; wide controls (prompt picker, tool chips, env rows, append system prompt) span their card.

Drag the width across 720px and 1320px of pane width (about 996px and 1596px of viewport) and confirm the layout snaps between arrangements with no intermediate state.

## 5. Behaviour preserved (spec FR-016)

- [x] Change harness on the create page: cards appear/disappear; the groups and lead strip stay put; model/effort memory and the network warning behave as before.
- [x] Submit with an invalid value (for example memory `abc`): the error shows inline in the Container card and the field is scrolled to and focused.
- [x] Add an env var named `MY_TOKEN` with a literal value: the secret warning and confirmation still appear in the Environment card.
- [x] Preview YAML: blocks follow the new order (Identity, Schedule, Limits, Prompt, Directories, Environment, Tools & permissions, Harness & model, Container).
- [x] Edit then navigate away: the unsaved-changes guard still fires.

## 6. YAML on disk (spec US5)

Save an existing agent without changes, then open its file:

- [x] Section headers and key order match [contracts/schema-and-yaml.md](contracts/schema-and-yaml.md) §2.
- [x] Every value equals its pre-save value (`git diff agents/<name>.yaml` shows only moved lines and renamed headers).
- [x] An unmanaged key added by hand survives in the trailing Unmanaged block.
