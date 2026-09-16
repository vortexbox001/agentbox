# Contract: Redaction

**Requirements**: FR-013, FR-014, FR-015, FR-016, SC-004. **Reuses**: `ui/secret_scan.py`
heuristic (spec Assumptions).

## Function

`redact(text: str) -> str` — replaces every secret-like token in `text` with
`[REDACTED:<kind>]`, leaving all other text unchanged. Idempotent (running it twice is a no-op).

Lives in `orchestrator/redact.py`, built on the same detection primitives as
`ui/secret_scan.py`. The UI keeps `secret_scan.py` (authoring-time flagging) and a thin display
redactor for defense-in-depth. The two copies are pinned by a shared-fixture **parity test**
(same pattern as `paths.py`↔`config.py`, `ASSET_KEY_RE`).

## Kinds

Derived from the matched detector (`<kind>` values): `api_key`, `token`, `password`,
`private_key`, `credential`, `secret`. A name-based match uses the name's kind; a value-prefix
match uses the format's kind (e.g. `sk-ant-` → `api_key`, `ghp_`/`github_pat_` → `token`,
`-----BEGIN` → `private_key`).

**Amendment (dropped `high_entropy` from free-text redaction).** The original design also ran a
blanket high-entropy pass and emitted `[REDACTED:high_entropy]`. In practice, on a code-agent
transcript that was almost entirely false positives — claude-code's own message / request /
tool_use ids and "thinking" signatures are high-entropy but not secrets — so it is **not** applied
to `transcript.jsonl` / `events.jsonl` / `context.json`. The reliable detectors (prefixes,
`NAME=value`, PEM) remain, and env values — the primary secret vector — are never written to disk
at all (FR-015), so real credentials are still covered. The high-entropy rule is retained only for
env-value classification (`redact.secret_kind_for`), pinned to `ui/secret_scan.is_secret_like` so
the UI's authoring-time secret confirmation is unchanged.

## Single pass, orchestrator-owned (FR-013)

All three of `transcript.jsonl`, `events.jsonl`, and `context.json` pass through `redact()`
before they are written into the run directory:

- **transcript**: each streamed line is redacted before it is written to `transcript.jsonl` and
  before it is forwarded to the live Dagster run log.
- **events**: every string field of every event is redacted as the orchestrator moves
  `events.jsonl` from staging into the run directory.
- **context**: every string field (prompt, appended prompt, instruction-file contents, mount
  sources, etc.) is redacted as `context.json` is written.

Redaction applies to tool results and every captured field, not only top-level messages
(FR-014).

## Environment variables (FR-015)

Env variable **values** are never captured. `context.json` records `runtime.env_names` (names
only). No captured file — including staging — ever holds an env value. This is by construction:
the orchestrator authors the env-name list, and no wrapper emits env values.

## Guarantee (FR-016 / SC-004)

After capture, a search of the entire run directory for any secret value present in the run finds
no cleartext occurrence. This is asserted directly in the quickstart: seed a run with a fake key,
then `grep -r` the run directory and expect no hit while the viewer shows `[REDACTED:...]`.
