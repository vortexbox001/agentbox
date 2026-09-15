# Contract: Revised shell + user settings modal

Covers FR-001–011, US2/US3. Structure and behaviour of the sidebar/foot on every page and the
settings modal. Realizes `ui/design-system/templates/tabbed-list/Sidebar.dc.html`, minus the
mock's stale "Dagster Indigo" theme option.

## A. Sidebar nav (`base.html`, every page) — FR-001

- Primary nav links **only to pages that exist: Agents**, rendered **below** the divider keyline
  (the `.ax-nav-divider` is retained so the group lands where the mock places it). No dead or
  disabled placeholder links (Overview/Runs are added by 012/023 when their pages exist).
- The active nav item is marked (existing `data-nav`/active-state mechanism in `shell.js`).

## B. Foot (`base.html`, every page) — FR-002, FR-003, FR-004

Top to bottom:
1. **Dagster status block** — unchanged behaviour (ok/down/unknown dot polled via
   `GET /api/dagster/status` by `shell.js`; opens Dagster in a new tab). Styled with the
   **indigo** translucent fill + indigo text in **every** theme (a Dagster connection point).
2. a **keyline**.
3. **"Hide navigation"** link with the collapse icon.
4. **"Settings"** link with the gear icon.

The old three-button theme **radiogroup** (`.ax-theme-control`) is **removed** (FR-003); its
accessibility assertion moves to the modal theme dropdown (`design-system-sync.md §D`).

**Collapse (FR-004).** "Hide navigation" collapses to the existing **68px rail** using
`localStorage["agentbox.sidebar"]`. Collapsed: foot links centre their icons and hide labels,
the brand shows only its mark, the Dagster block keeps only its dot, nothing overflows, and the
link's accessible name becomes **"Show navigation"** (expanded: "Hide navigation"). State
survives reload (pre-paint script stamps `data-sidebar`).

## C. Indigo accent ramp (FR-010) — NOT a theme

- Add an **indigo accent colour ramp** as design-system tokens under **both** the Light and Dark
  theme scopes (`ui/design-system/tokens/`), then reference it via classes in `app.css`.
- Apply it to the primary **Dagster connection points**: the foot Dagster block and the
  schedule/sensor toggles' checked track. Other elements keep the theme's own accent — in
  particular the per-agent Latest-run link uses the theme link accent (teal) even though it
  deep-links to Dagster, and the Run-history bars keep their run-status colours.
- **No `indigo` theme value** exists and none is added to `config/settings.yaml`. The mock's
  fourth "Dagster Indigo" dropdown option is dropped.

## D. Settings modal (`base.html` `#ax-modal-root` + `ui/static/settings.js`) — FR-005–008

- A `role="dialog"`, `aria-modal="true"` panel labelled **"User settings"**, opened from the
  Settings foot link, rendered into the existing shared `#ax-modal-root`.
- **Chrome (FR-006):** square corners, default-background surface, full-bleed keylines on the
  header and actions rows, padded body. The **same chrome** restyles the existing
  confirm/dirty-form modal (US3 scenario 7). All styling via tokens/classes — no inline style.
- **Content:** one **Preferences** section, one **Theme** row with a right-aligned dropdown, and
  a single primary **"Done"** action — **no Save**.
- **Theme dropdown (FR-007):** a custom listbox on the `.ax-dropdown` chrome (research R5), not a
  native `<select>`. Options **Light, Dark, Use system setting**, each with a lead icon; the
  trigger shows the current option's icon as its lead glyph.
- **Apply/persist (FR-008, FR-009):** choosing an option applies the theme **immediately**
  (stamp/clear `data-theme` on `<html>`) with no reload and writes
  `localStorage["agentbox.theme"]` ∈ {light, dark, system}; a reload keeps it. `system` follows
  `prefers-color-scheme` live. Done, Escape (no open panel), and backdrop click all just close.

## E. Focus & keyboard (FR-011)

- Opening moves focus into the modal and **traps Tab** while open; closing returns focus to the
  **Settings foot link**.
- **Escape** closes an open dropdown **panel first**; a second Escape (no open panel) closes the
  modal (US3 scenario 5). The dropdown keyboard model reuses `dropdown.js` (spec 002), keeping
  one behaviour across the app.

## F. Pre-paint script (`base.html`) — unchanged (FR-009)

Keep the inline head script that reads `agentbox.theme` (resolving light/dark/system) and
`agentbox.sidebar`, stamping `data-theme`/`data-sidebar` before first paint so there is no
wrong-theme or wrong-width flash.
