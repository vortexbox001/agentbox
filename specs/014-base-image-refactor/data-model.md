# Phase 1 Data Model: Shared Agent Base Image

This feature has no application data model — no schema, no `settings.yaml` key, no run/output shape
change. The "entities" here are the **images** and the build relationships between them; the fields
are Dockerfile stages/instructions. This document pins what each image must and must not contain so
the contract (`contracts/agent-base-image.md`) and the tasks phase have one authoritative reference.

## Entity: Shared base image — `agentbox/agent-base`

The single image carrying everything common to the shell-based harnesses. It is the sole place the
common tool list and the shared Python/`dagster-pipes` runtime are defined.

| Field | Value | Source requirement |
|-------|-------|--------------------|
| Tag | `agentbox/agent-base` | FR-001, spec Key Entities |
| Base | `node:20-slim` (Debian bookworm-slim, arm64) | R1 |
| Non-root user | uid-1000 `node` (inherited from `node:20-slim`; not re-created) | FR-001, R1 |
| Working directory | `WORKDIR /workspace` | FR-001 |
| Final user | left as the image default (**root**) — the base does not `USER node`, so downstream harnesses can `npm install -g`; the uid-1000 `node` user is inherited and available for each harness to switch to | FR-001, R1, parity |
| Common tools | `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, `unzip`, `build-essential`, plus `gh` from the official GitHub CLI apt repo | FR-002, R2 |
| Python runtime | `python3` + `python3-pip` (apt) | FR-013, R3 |
| Report runtime | `dagster-pipes==1.13.21` (pip3, `--break-system-packages`) | FR-013, R3 |
| Not present | any harness install, any entrypoint, any harness-specific env | FR-001/FR-004 (base is harness-agnostic) |

**Validation / invariants**
- The common tool set and the Python/`dagster-pipes` runtime appear **here and nowhere else** among
  the shell-based images (FR-003/FR-013, SC-003).
- `git`, `rg`, `jq`, `gh`, `python3` resolve to executables (FR-007, verified in quickstart).
- No secret, token, or credential in any layer or build arg (Constitution III).

## Entity: Thin harness image — `agent-claude`, `agent-pi`, `agent-codex`

A harness image that builds on the shared base and adds only its own harness.

| Field | Value | Source requirement |
|-------|-------|--------------------|
| Base | `FROM agentbox/agent-base` | FR-004 |
| Common-tool pointer | one-line comment naming `agent-base` as the source of common tooling | FR-006 |
| Harness install | the image's own line(s): `npm install -g @anthropic-ai/claude-code` / `npm install -g --ignore-scripts @earendil-works/pi-coding-agent` / `npm install -g @openai/codex` | FR-005 |
| Shared library | `COPY lib/ /app/lib/` (from the `images/` context) | unchanged |
| Wrapper / entrypoint | `COPY agent-*/wrapper.py`, plus `agent-pi/entrypoint.sh` (+ `chmod 755`); `ENTRYPOINT` unchanged per image | FR-005 |
| Harness-specific env | `ENV CODEX_HOME=/creds` (agent-codex only) | FR-005 |
| Final user switch | keeps its own `USER node` as the last step before `ENTRYPOINT` (a user *switch*, not user *creation* — the base leaves the image as root so `npm install -g` works; this line preserves today's non-root run) | FR-005, parity |
| Must NOT contain | OS-package `apt-get` install, user *creation* (`useradd`/`adduser`), `WORKDIR`, or the Python/`dagster-pipes` install | FR-004, SC-003 |

**Per-image specifics (what survives the thinning)**

- **agent-claude**: `npm install -g @anthropic-ai/claude-code`; `COPY lib/` + `wrapper.py`;
  `ENTRYPOINT ["python3", "/app/wrapper.py"]`.
- **agent-pi**: `npm install -g --ignore-scripts @earendil-works/pi-coding-agent`; `COPY lib/` +
  `wrapper.py` + `entrypoint.sh` (+ `chmod 755`); `ENTRYPOINT ["/app/entrypoint.sh"]`.
- **agent-codex**: `npm install -g @openai/codex`; `ENV CODEX_HOME=/creds`; `COPY lib/` +
  `wrapper.py`; `ENTRYPOINT ["python3", "/app/wrapper.py"]`.

**Validation / invariants**
- Inspecting the image definition shows no OS-package install, no user creation, no `WORKDIR` line
  (SC-003, US1 scenario 2, US2 scenario 3).
- The common tools are present and runnable (inherited from the base) — FR-007/SC-004.
- Behavior is functionally/format-identical to the pre-refactor image: same wrapper/entrypoint, same
  `COPY lib/`, same `dagster-pipes` version → `images/tests` passes unchanged (FR-008/SC-002).

## Entity: Standalone harness image — `agent-python`

The harness that stays on its own base because it cannot benefit from the shared base.

| Field | Value | Source requirement |
|-------|-------|--------------------|
| Base | `FROM python:3.12-slim` (unchanged) | FR-010 |
| Documented reason | one-line comment: needs the Python runtime, not the Node-bearing base, and no shell tools | FR-010, US4 |
| Own runtime pin | keeps its own `dagster-pipes==1.13.21` install | FR-010, Complexity Tracking |
| Must NOT gain | the common shell tool set it does not need | FR-010, US4 scenario 2 |

**Validation / invariants**
- Stays on `python:3.12-slim`; the reason is recorded in the image (US4 scenario 1).
- Not forced onto the shared base and not bloated with unneeded tools (US4 scenario 2).

## Relationships (build graph)

```text
node:20-slim ──▶ agentbox/agent-base ──▶ agent-claude
                                     ├──▶ agent-pi
                                     └──▶ agent-codex

python:3.12-slim ──▶ agent-python        (standalone; not on the shared base — FR-010)
```

- **Build order**: `agent-base` before the three thin harnesses (enforced by `FROM` at build time;
  stated explicitly in README build steps and `scripts/bootstrap.sh` — FR-012). `agent-python` has no
  ordering dependency on `agent-base`.
- **Footprint**: the three thin harnesses share the single `agent-base` layer set, so the
  deduplicated on-disk total (counting the base once) is smaller than three independent copies of the
  same OS+tools+runtime (FR-011/SC-005).

## State transitions

None. Images are built artifacts; there is no runtime state machine. The only "transition" is the
refactor itself: three harness images move `FROM node:20-slim` (+ duplicated install) → `FROM
agentbox/agent-base` (+ harness-only lines), and `agent-python` stays put with an added comment.
