# Bug Assessment: Dagster link base URL missing port (and malformed DAGSTER_PUBLIC_URL)

- **Slug**: dagster-link-base-url
- **Created**: 2026-09-14
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim)

> the links to dagsters are wrong on buttons linking to local dagsters, base url should be http://10.0.0.100:3000/ i.e. {DAGSTER_PUBLIC_URL}:{DAGSTER_HOST_PORT}/

## Symptom

Buttons/links that open Dagster from the UI (sidebar "Dagster" link, per-agent "runs"
link, agent edit header link) point at a wrong base URL. Observed base is
`http://http://10.0.0.100` (double scheme, **no** `:3000` port); expected base is
`http://10.0.0.100:3000/`. Clicking the links lands on a broken/unreachable URL.

The user's stated expectation is that the browser base is composed as
`{DAGSTER_PUBLIC_URL}:{DAGSTER_HOST_PORT}/` — i.e. `DAGSTER_PUBLIC_URL` is a host base
(no port) and the host's published Dagster port (`DAGSTER_HOST_PORT`) is appended.

## Reproduction

1. On the host, `.env` currently has `DAGSTER_PUBLIC_URL=http://http://10.0.0.100`.
2. Load the UI (e.g. `http://10.0.0.100:8000/agents`).
3. Hover/click the sidebar "Dagster" link or a row's "runs" button.
4. Observe the `href` base is `http://http://10.0.0.100` — malformed scheme and no port —
   instead of `http://10.0.0.100:3000`.

## Suspected Code Paths

- `ui/main.py:63-75` (`public_dagster_url`) — when `DAGSTER_PUBLIC_URL` is set it is used
  **verbatim** (`return config.DAGSTER_PUBLIC_URL.rstrip("/")`); the port is never
  appended. The derive-fallback branch (blank `DAGSTER_PUBLIC_URL`) takes its port from
  `urlparse(config.DAGSTER_URL).port` — the **internal** container port (3000), not
  `DAGSTER_HOST_PORT`. Neither branch matches the requested `{PUBLIC_URL}:{HOST_PORT}`
  composition, and neither guards against a malformed `DAGSTER_PUBLIC_URL`.
- `ui/config.py:46-52` — `DAGSTER_URL` (internal) and `DAGSTER_PUBLIC_URL` are defined;
  there is **no** `DAGSTER_HOST_PORT` in the UI config at all (`grep` confirms zero
  references under `ui/`), so the composition the user describes is not implementable
  today without adding it.
- `ui/main.py:78-81` (`_shell_context`) — injects `dagster_url` from `public_dagster_url`
  into every page's shell context; all clickable Dagster links derive from it.
- `ui/templates/base.html:57` — sidebar link `href="{{ dagster_url }}"`.
- `ui/templates/agents/list.html:50` — per-row "runs" button `href = dagster_url ~ a.dagster_path`.
- `ui/templates/agents/form.html:13` — edit header link `href = dagster_url ~ dagster_path`.
- `.env:35` (host, gitignored) — `DAGSTER_PUBLIC_URL=http://http://10.0.0.100`: a
  double-`http://` typo **and** no port. This is the immediate trigger of the observed
  broken links.

## Root Cause Hypothesis

Two overlapping causes, confidence **high**:

1. **Config typo** (immediate): the host `.env` has `DAGSTER_PUBLIC_URL=http://http://10.0.0.100`
   — duplicated scheme and no port — so `public_dagster_url` returns that string verbatim
   and every Dagster link is malformed.
2. **Design gap** (root): `public_dagster_url` treats `DAGSTER_PUBLIC_URL` as a *complete*
   base URL and never appends a port, while the derive fallback uses the *internal* port
   rather than the host-published `DAGSTER_HOST_PORT`. There is no `DAGSTER_HOST_PORT` in
   UI config. So a user who sets `DAGSTER_PUBLIC_URL` to a bare host (the natural mental
   model, matching how `.env` documents it) gets a port-less, unreachable link, and a
   non-default `DAGSTER_HOST_PORT` is never honored by the links.

## Proposed Remediation

**Preferred**: Make `public_dagster_url` compose the port and tolerate a bare-host
`DAGSTER_PUBLIC_URL`, and honor `DAGSTER_HOST_PORT`.

- Add `DAGSTER_HOST_PORT = os.environ.get("DAGSTER_HOST_PORT", "3000")` to `ui/config.py`
  and thread it into the UI service env in `docker-compose.yml` (the var already exists at
  compose top-level; pass it into the `ui`/orchestrator service environment).
- In `public_dagster_url`:
  - If `DAGSTER_PUBLIC_URL` is set, parse it; if it already carries an explicit port, use
    it verbatim; if it has **no** port, append `:{DAGSTER_HOST_PORT}`. Normalize a missing
    scheme to `http://` and collapse an accidental double scheme (defensive against the
    `http://http://…` typo).
  - In the derive fallback, use `DAGSTER_HOST_PORT` for the port instead of
    `urlparse(config.DAGSTER_URL).port`, since the browser reaches the host-published port,
    not the internal one.
- Fix the host `.env` to `DAGSTER_PUBLIC_URL=http://10.0.0.100` (bare host) — with the code
  change this yields `http://10.0.0.100:3000`. (`.env` is gitignored, not a source file —
  note it in the fix, but the code change is what makes the setup correct.)

**Alternatives**:
- *Minimal / no code change*: fix `.env` to a full URL `DAGSTER_PUBLIC_URL=http://10.0.0.100:3000`
  (or blank it to use the derive path). Fixes this host immediately but leaves the design
  gap — a bare-host value or non-default `DAGSTER_HOST_PORT` still produces wrong links,
  and it does not match the `{PUBLIC_URL}:{HOST_PORT}` composition the user asked for.
- *Blank `DAGSTER_PUBLIC_URL`, derive from request*: works when Dagster shares the UI host;
  but the derive branch still uses the internal port (3000), so it silently breaks if
  `DAGSTER_HOST_PORT` is remapped. Fold that same `DAGSTER_HOST_PORT` fix in regardless.

**Files likely to change**:
- `ui/config.py`
- `ui/main.py`
- `docker-compose.yml` (pass `DAGSTER_HOST_PORT` into the UI service env)
- `ui/tests/test_api.py` and/or a focused test around `public_dagster_url`
- `.env` (host config; not committed)

**Tests to add or update**:
- `public_dagster_url` with `DAGSTER_PUBLIC_URL` bare host (`http://10.0.0.100`) →
  `http://10.0.0.100:3000`.
- with `DAGSTER_PUBLIC_URL` already carrying a port (`http://10.0.0.100:9999`) → verbatim.
- with a non-default `DAGSTER_HOST_PORT` (e.g. `3001`) → appended in both the explicit and
  derive branches.
- with a malformed double-scheme value (`http://http://10.0.0.100`) → normalized to a
  single scheme with the port (guards the exact reported typo).
- derive branch (blank `DAGSTER_PUBLIC_URL`) uses `DAGSTER_HOST_PORT`, not the internal
  `DAGSTER_URL` port.

## Risks & Considerations

- **Ambiguity of intent**: users may reasonably set `DAGSTER_PUBLIC_URL` to a *full* URL
  (behind a proxy on 443, no port). The "append port only when absent" rule preserves that
  case; do not append a port when one is already present or when the scheme implies a
  standard port the operator intends. Document the expected form in `.env.example`.
- **`.env.example` doc drift**: line 35 currently says "blank = derive from the request
  host + Dagster port". Update it to describe the new bare-host + `DAGSTER_HOST_PORT`
  composition so operators don't reintroduce the typo.
- **Low blast radius**: change is confined to link construction; no data, API, or migration
  impact. Server-rendered links only (`agent-form.js` does not touch these hrefs).

## Open Questions

- [NEEDS CLARIFICATION: should a `DAGSTER_PUBLIC_URL` that already includes a port be left
  exactly as-is (preferred), or should `DAGSTER_HOST_PORT` always override it?] Assessment
  assumes an explicit port in `DAGSTER_PUBLIC_URL` wins.
