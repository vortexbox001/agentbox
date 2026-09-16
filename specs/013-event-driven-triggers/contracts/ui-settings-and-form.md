# Contract: UI — Depends-on card, trigger toggles, and the Settings governors card

The UI surfaces this feature adds: authoring `depends_on` + the two triggers on the agent form
(FR-019/FR-020), and editing the two governors on the Settings page (FR-018). All controls are
composed from the shared Jinja macros and design-system tokens (Constitution VII / agentbox-design
skill) — no literal colours/px, no inline styles, no raw `<select>`.

## §1 Agent form — Depends-on & trigger toggles (FR-019/FR-020)

`ui/static/agent-form.js` + `ui/templates/agents/form.html`.

- **Depends-on** (FR-019): the `depends_on` field renders as a **list control** inside the asset
  card region (a "Depends-on" card/subsection), letting the operator add/remove upstream asset
  keys. It is gated by the asset toggle — when the agent is not an asset, `depends_on` is hidden and
  omitted from `collect()`.
- **on_upstream / on_missing** (FR-020): each renders as a **toggle** in the asset card's grid
  (they are asset-kind), beside `asset_schedule`. When the asset toggle is off, both are hidden and
  omitted from `collect()`.
- `CARD_SECTIONS` and the asset-card grid gain `depends_on`, `on_upstream`, `on_missing`; the
  removal-on-toggle-off list (`agent-form.js`) gains all three, mirroring how `asset`/`partition`/
  `asset_schedule`/`checks` are dropped when the asset card is off.
- Client-side hints only; `schema.validate` on the server is the authority.

## §2 Agents list — trigger pills (FR-020)

`ui/templates/agents/list.html` + `ui/static/agents-list.js`: the schedules/sensors column shows a
pill for `on_upstream` and `on_missing` (icon via the `schedule_pill` macro) alongside
`asset_schedule`, driven by the lifted flags; the "scheduled" tab narrowing recognizes them as
asset-kind triggers.

## §3 Settings — governors card (FR-018)

`ui/templates/settings/page.html` + `ui/static/settings.js`.

- A new card (id e.g. `#ax-governors-card`) beside the retention card, built from the shared `card`
  + `text_input` (type number) + `button` macros:
  - `max_runs_per_hour` — number input, min 1, help *"Cap on automated runs per rolling 60-minute
    window. Manual runs bypass. Default 12."*
  - `max_chain_depth` — number input, min 1, help *"Cap on how deep an automated chain of triggers
    may go. Manual runs bypass. Default 5."*
- `settings.js` `initGovernors()` (mirrors `initRetention`): read current values from the page
  context, save via `POST /api/settings/governors`, reflect the response, and show the shared
  status/notice.

## §4 HTTP API

Extends `ui/main.py`. Mirrors the retention endpoint shape.

### GET (page context)
`GET /settings` renders `settings/page.html` with `governors = settings_store.read_governors()`
alongside the existing `retention`.

### POST `/api/settings/governors`
- **Request**: `{"max_runs_per_hour": int, "max_chain_depth": int}`.
- **Success 200**: `{"governors": {"max_runs_per_hour": int, "max_chain_depth": int}}`.
- **Error 400**: `{"error": "validation", "message": str}` when a value is not a positive integer
  (or exceeds the sane upper bound).
- **Flow**: `settings_store.write_governors(...)` validates + persists to `config.SETTINGS_FILE`
  (preserving `retention` and any unknown keys), logs `event=governors_updated
  max_runs_per_hour=… max_chain_depth=…`. No Dagster reload is triggered (the orchestrator reads the
  file at op time / on its next reload).

## §5 settings_store additions

`ui/settings_store.py`:

```python
DEFAULT_GOVERNORS = {"max_runs_per_hour": 12, "max_chain_depth": 5}

class GovernorError(ValueError): ...

def read_governors() -> dict:
    """The governors block, normalized to {max_runs_per_hour, max_chain_depth} with defaults for
    absent/invalid keys."""

def validate_governors(max_runs_per_hour, max_chain_depth) -> dict:
    """Validate + normalize; raise GovernorError. Each must be an int >= 1 (and <= a sane cap, e.g.
    max_runs_per_hour <= 10000, max_chain_depth <= 1000)."""

def write_governors(max_runs_per_hour, max_chain_depth) -> dict:
    """Persist the governors block, preserving every other key in the file (same pattern as
    write_retention)."""
```

`DEFAULT_GOVERNORS` is the twin of `orchestrator/governors.DEFAULT_GOVERNORS`, pinned by a
parity test; the live value is the `settings.yaml` file.

## §6 Tests (`ui/tests/`)

- `test_settings.py`: `read_governors` default when absent; `validate_governors` rejects
  non-positive / non-int / over-cap; `write_governors` preserves the `retention` block and unknown
  keys; `POST /api/settings/governors` persists + returns; 400 on bad payload; the Settings page
  renders the governors card.
- `test_schema.py`: `depends_on` + `on_upstream`/`on_missing` present; `migrate_6_to_7` identity;
  validation (asset-key entries, trigger-applies-only-to-asset, depends_on-needs-asset).
- `test_agents_store.py`: emit/lift the three fields; round-trip; unknown keys preserved.
- `test_api.py`: `/api/schema` includes the three fields; the form renders the Depends-on card and
  the two toggles; the governors API round-trip.
