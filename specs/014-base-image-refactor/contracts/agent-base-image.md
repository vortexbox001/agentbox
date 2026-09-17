# Contract: `agentbox/agent-base` → harness images

The shared base is an internal build interface: the "consumers" are the three shell-based harness
Dockerfiles that build `FROM agentbox/agent-base`. This contract states what the base **guarantees**
to those images and what they may rely on, so a change to the base is a change to a versioned surface
rather than an accident. There is no external/network contract — the base exposes no ports, no API.

## What the base guarantees to any image built `FROM agentbox/agent-base`

| Guarantee | Detail | Requirement |
|-----------|--------|-------------|
| **OS + arch** | Debian bookworm-slim, arm64 (via `node:20-slim`) | FR-001, R1 |
| **Node runtime** | Node 20 + `npm` on `PATH` (so harnesses can `npm install -g …`) | R1 |
| **Non-root user** | a uid-1000 `node` user exists (inherited from `node:20-slim`) | FR-001 |
| **Working directory** | `WORKDIR /workspace` is set | FR-001 |
| **Common CLI tools** | `git`, `curl`, `ca-certificates`, `ripgrep` (`rg`), `jq`, `gh`, `unzip`, and `build-essential` are installed and on `PATH` | FR-002/FR-007 |
| **Python runtime** | `python3` and `pip3` on `PATH` | FR-013 |
| **Report library** | `dagster-pipes==1.13.21` importable by `python3` | FR-013 |

A harness image therefore must NOT re-install the OS packages, re-create the user, re-set `WORKDIR`,
or re-install `python3`/`dagster-pipes` — those come from the base (FR-004). Doing so would violate
the single-source-of-truth requirement (FR-003/SC-003).

## What a harness image adds on top (its side of the contract)

1. `FROM agentbox/agent-base`.
2. A **one-line comment** stating that the common tooling comes from `agent-base` (FR-006).
3. Its harness install only (`npm install -g …`).
4. `COPY lib/ /app/lib/` and its wrapper (`COPY agent-*/wrapper.py`), plus `agent-pi`'s
   `entrypoint.sh` (+ `chmod`).
5. Any harness-specific env (`ENV CODEX_HOME=/creds` for `agent-codex`).
6. Its `ENTRYPOINT` (unchanged from today).

Nothing else. The absence of `apt-get`, user creation, and `WORKDIR` in these files is itself part of
the contract (SC-003) and is checked in the quickstart.

## Single-source-of-truth guarantee (SC-001)

Adding or removing a tool shared by all shell-based agents is a **one-line edit to
`images/agent-base/Dockerfile`** followed by a rebuild of the base and the harnesses — with **zero
edits** to any harness Dockerfile. This is the headline contract (US2): after `yq` (for example) is
added to the base's tool line and the images are rebuilt, `yq` resolves in every shell-based harness
and no harness Dockerfile changed.

## Build-order contract (FR-012)

- `agentbox/agent-base` MUST be built before any harness that is `FROM` it. Docker enforces this at
  build time; the human/scripted build paths (README build steps, `scripts/bootstrap.sh`) MUST list
  the base first.
- All images build from the `images/` directory as context so `COPY lib/` resolves (see research.md
  R4 — this also corrects the pre-existing README build-context bug).

## Standalone exception (FR-010)

`agent-python` is explicitly **not** a consumer of this contract: it stays `FROM python:3.12-slim`
and keeps its own `dagster-pipes` pin, with a one-line comment recording why (needs Python, not the
Node base; no shell tools). The null-action safeguard: a harness that cannot use the base is left on
its own base rather than bloating the shared base for the rest.

## Parity guarantee (FR-008/SC-002)

The base carries the *same* Python interpreter family and the *same* pinned `dagster-pipes==1.13.21`
the harnesses use today, and the harnesses keep their existing wrapper/entrypoint and `COPY lib/`.
Therefore the report format and agent-output semantics are unchanged and `images/tests` passes
unchanged — functional/format equivalence, not a byte-identical live rerun.
