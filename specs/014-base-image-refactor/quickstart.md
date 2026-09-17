# Quickstart: verifying the shared agent base image

This guide proves the feature end to end: the base builds, the shell-based harnesses build on it, the
common tools resolve, no agent YAML changed, behavior is unchanged (image tests pass), one-place tool
addition works, and the deduplicated footprint shrinks. Run it on the arm64 Pi host (or any Docker
host); build steps are the live-verification posture used by prior specs. See
[contracts/agent-base-image.md](contracts/agent-base-image.md) and [data-model.md](data-model.md) for
the guarantees each step checks; do not duplicate their detail here.

**Prerequisites**: Docker; the repo checked out; run all `docker build` commands with the `images/`
directory as context so the shared `images/lib/` is available (research.md R4).

## 1. Record the "before" footprint (for SC-005)

Before rebuilding, capture the deduplicated on-disk size of the shell-based harness images as they
exist today (each on its own `node:20-slim` copy):

```bash
docker system df -v | grep -E 'agent-claude|agent-pi|agent-codex'   # note the sizes
```

## 2. Build the base first, then the harnesses (FR-012)

```bash
cd images
docker build -f agent-base/Dockerfile   -t agentbox/agent-base   .   # MUST be first
docker build -f agent-claude/Dockerfile -t agentbox/agent-claude .
docker build -f agent-pi/Dockerfile     -t agentbox/agent-pi     .
docker build -f agent-codex/Dockerfile  -t agentbox/agent-codex  .
docker build -f agent-python/Dockerfile -t agentbox/agent-python .   # standalone; order-independent
```

**Expected**: all builds succeed; the three shell-based harnesses resolve `FROM agentbox/agent-base`
(so the base must exist first).

## 3. Common tools resolve in every shell-based harness (FR-007 / SC-004)

```bash
for img in agent-claude agent-pi agent-codex; do
  echo "== $img =="
  docker run --rm --entrypoint sh agentbox/$img -c \
    'for t in git curl rg jq gh unzip cc python3; do command -v $t || echo "MISSING: $t"; done; \
     python3 -c "import dagster_pipes; print(\"dagster-pipes OK\")"'
done
```

**Expected**: every tool resolves to a path, `dagster-pipes OK` prints, and no `MISSING:` line
appears. (`cc` proves `build-essential`.)

## 4. The harness images carry no shared install (SC-003 / US1-2 / US2-3)

```bash
for f in images/agent-claude/Dockerfile images/agent-pi/Dockerfile images/agent-codex/Dockerfile; do
  echo "== $f =="
  grep -Eq 'apt-get|useradd|adduser|^WORKDIR|python3-pip|dagster-pipes' "$f" \
    && echo "FAIL: harness still declares shared setup" || echo "OK: thin harness"
  grep -q 'FROM agentbox/agent-base' "$f" && echo "OK: on shared base" || echo "FAIL: not on base"
  grep -qi 'agent-base' "$f" && echo "OK: has one-line base pointer (FR-006)" || echo "FAIL: no pointer"
done
```

**Expected**: each file is `OK: thin harness`, `OK: on shared base`, `OK: has one-line base pointer`.

## 5. Single source of truth — add one tool, rebuild, it appears everywhere (SC-001 / US2)

Temporarily add `yq` to the one tool line in `images/agent-base/Dockerfile`, rebuild the base and one
harness **without editing that harness's Dockerfile**, and confirm `yq` is present:

```bash
# (edit images/agent-base/Dockerfile: append `yq` to the apt install list — one line, one place)
cd images
docker build -f agent-base/Dockerfile   -t agentbox/agent-base   .
docker build -f agent-claude/Dockerfile -t agentbox/agent-claude .
docker run --rm --entrypoint sh agentbox/agent-claude -c 'command -v yq'
git diff --stat images/agent-claude/Dockerfile   # expect: no changes to the harness file
# revert the temporary yq edit afterwards
```

**Expected**: `yq` resolves in `agent-claude`; the harness Dockerfile shows no diff — the tool was
gained by editing exactly one place.

## 6. Behavioral parity — image tests pass unchanged (FR-008 / SC-002)

```bash
.venv/bin/python -m pytest -q images/tests
```

**Expected**: the suite passes unchanged (it is hermetic — it parses fixtures, not live runs). This
is the parity evidence: same wrapper/runner and report code, so report format and output semantics
are unchanged.

## 7. No agent YAML changed (FR-009 / SC-006)

```bash
git diff --name-only | grep -E '/agents/.*\.ya?ml$' && echo "FAIL: an agent YAML changed" \
  || echo "OK: no agent YAML changed"
```

**Expected**: `OK: no agent YAML changed`.

## 8. Standalone harness kept its base with a reason (FR-010 / US4)

```bash
grep -q 'FROM python:3.12-slim' images/agent-python/Dockerfile && echo "OK: still on python base"
grep -qiE 'node|shell tool|shared base|agent-base' images/agent-python/Dockerfile \
  && echo "OK: reason documented" || echo "FAIL: no documented reason"
```

**Expected**: both `OK` lines.

## 9. Smaller combined footprint, deduplicated (FR-011 / SC-005)

```bash
docker system df -v | grep -E 'agent-base|agent-claude|agent-pi|agent-codex'
```

**Expected**: the deduplicated on-disk usage of the three shell-based harnesses **plus** the single
shared `agent-base` layer is smaller than the "before" total from step 1 — the common OS+tool+runtime
layer is stored once instead of three times. Compare deduplicated store usage, **not** the sum of the
per-image `docker images` SIZE column (which counts the shared base three times — research.md R5).
