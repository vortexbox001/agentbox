# Bug Fix: Dagster link base URL missing port (and malformed DAGSTER_PUBLIC_URL)

- **Slug**: dagster-link-base-url
- **Fixed**: 2026-09-14
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

`public_dagster_url` now composes the browser-facing Dagster base as
`{DAGSTER_PUBLIC_URL}:{DAGSTER_HOST_PORT}` — appending the host-published port when the
configured URL has none, normalizing a missing/doubled scheme — and the derive fallback
uses `DAGSTER_HOST_PORT` instead of the internal container port. A new `DAGSTER_HOST_PORT`
UI config var was added and threaded through compose, and the malformed host `.env` value
(`http://http://10.0.0.100`) was corrected.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `ui/config.py` | modified | Added `DAGSTER_HOST_PORT` (default `3000`); reworded `DAGSTER_PUBLIC_URL` doc |
| `ui/main.py` | modified | `public_dagster_url` uses `DAGSTER_HOST_PORT`; new `_compose_public_base` helper normalizes/ports the configured URL; added `re`/`urlunparse` imports |
| `docker-compose.yml` | modified | Pass `DAGSTER_HOST_PORT: ${DAGSTER_HOST_PORT:-3000}` into the `ui` service env |
| `.env.example` | modified | Documented that `DAGSTER_HOST_PORT` is appended to a port-less `DAGSTER_PUBLIC_URL` |
| `.env` | modified | Fixed `http://http://10.0.0.100` → `http://10.0.0.100` (host config, gitignored) |
| `ui/tests/test_dagster_url.py` | added | 8 unit tests over both branches of `public_dagster_url` |

## Diff Highlights

`ui/main.py` — composition + normalization:

```python
if config.DAGSTER_PUBLIC_URL:
    return _compose_public_base(config.DAGSTER_PUBLIC_URL, config.DAGSTER_HOST_PORT)
host = request.url.hostname or "localhost"
scheme = request.url.scheme or "http"
return f"{scheme}://{host}:{config.DAGSTER_HOST_PORT}"
```

```python
def _compose_public_base(value: str, default_port: str) -> str:
    value = value.strip().rstrip("/")
    while (m := re.match(r"(?i)^(https?://)(?=https?://)", value)):   # http://http://host
        value = value[len(m.group(1)):]
    if not re.match(r"(?i)^https?://", value):
        value = "http://" + value
    parsed = urlparse(value)
    if parsed.port is None and parsed.hostname:
        parsed = parsed._replace(netloc=f"{parsed.hostname}:{default_port}")
        value = urlunparse(parsed).rstrip("/")
    return value
```

## Tests Added or Updated

- `ui/tests/test_dagster_url.py::test_bare_host_gets_host_port_appended` — the core case: `http://10.0.0.100` → `http://10.0.0.100:3000`.
- `::test_explicit_port_in_public_url_is_preserved` — an explicit port (proxy on 9999) wins; `DAGSTER_HOST_PORT` not appended.
- `::test_non_default_host_port_is_honored` — `DAGSTER_HOST_PORT=3001` is used.
- `::test_doubled_scheme_typo_is_normalized` — the exact reported `http://http://10.0.0.100` → `http://10.0.0.100:3000`.
- `::test_missing_scheme_defaults_to_http` / `::test_trailing_slash_is_stripped` — normalization edges.
- `::test_derive_uses_host_port_not_internal_port` — blank `DAGSTER_PUBLIC_URL` derives with `DAGSTER_HOST_PORT`, never the internal 3000.
- `::test_derive_keeps_request_scheme_and_host` — derive preserves request scheme/host.

## Local Verification

- `cd ui && ../.venv/bin/python -m pytest tests/test_dagster_url.py -q` → **8 passed**.
- `cd ui && ../.venv/bin/python -m pytest -q` → **380 passed** (no regressions).

## Deviations from Assessment

None. Implemented the preferred remediation. Resolved the open question in favor of the
assessment's assumption: an explicit port in `DAGSTER_PUBLIC_URL` is preserved and
`DAGSTER_HOST_PORT` is only appended when absent (covered by
`test_explicit_port_in_public_url_is_preserved`).

## Follow-ups

- Recreate the `ui` container so the new `DAGSTER_HOST_PORT` env and corrected `.env` take
  effect: `docker compose up -d ui` (env change only; no image rebuild needed).
- The per-agent "runs" links and edit-header link derive from the same `dagster_url`, so
  they are fixed transitively — worth a quick click-through after redeploy.
