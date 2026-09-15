# Quickstart / Validation: File Layout Overhaul — Three Roots

Runnable validation for each user story. Unit-level checks run in the `.venv` (Python 3.12);
the migration and fresh-install stories run on a **copy** of the box (never the live box until
the copy passes). Do not recreate `.venv/` — see CLAUDE.local.md.

## Prerequisites

- Repo checked out on branch `010-file-layout-overhaul`.
- `.venv/` present; suites run with `../.venv/bin/python -m pytest -q`.
- For the box-copy stories: a snapshot/clone of the Pi's `/data` and repo, or a scratch host.

## Unit suites (fast, no box)

```bash
# Orchestrator: path resolution, PIPES-under-DAGSTER_HOME, RUNS-under-DATA
cd orchestrator && ../.venv/bin/python -m pytest -q

# UI: path resolution parity, schema path validation + version 6 migration, template picker source
cd ui && ../.venv/bin/python -m pytest -q

# Image lib (unchanged report contract still green)
cd images && ../.venv/bin/python -m pytest -q tests
```

Expected: all green, including new tests for path-resolution (contracts/path-resolution §4),
migration planner (migration-cli §4), LiteLLM generator (litellm-generator §4), and path
validation (path-validation §4).

## US6 — LiteLLM generation (no box)

```bash
# Happy path: bind alias tiers to the overlay's providers
python3 litellm/generate.py
grep -q "os.environ/ANTHROPIC_API_KEY" config/litellm.rendered.yaml && echo "refs preserved"

# Missing-key path: unset a referenced key, expect a named failure and NO output written
mv config/litellm.rendered.yaml /tmp/prev.yaml
env -u ANTHROPIC_API_KEY python3 litellm/generate.py; echo "exit=$?"   # non-zero, names ANTHROPIC_API_KEY
test ! -f config/litellm.rendered.yaml && echo "no config emitted on missing key"
```

Expected: happy path binds `cheap/smart/opus/kimi/kimi-k3` to the overlay providers and keeps
`os.environ/<KEY>` refs; missing-key path exits non-zero **naming the key** and writes nothing
(SC-008).

## US1 — Migrate the existing box without losing anything (P1)

On a **copy** of the box:

```bash
# 1. Dry-run: full plan, zero changes
python3 scripts/migrate-layout.py | tee /tmp/plan.txt
git status --porcelain    # unchanged; /data unchanged

# 2. Apply
python3 scripts/migrate-layout.py --apply

# 3. Regenerate LiteLLM config + restart
python3 litellm/generate.py
docker compose down && docker compose up -d
```

Then verify:
- UI (`:8080`) lists every agent; Dagster (`:3000`) shows every schedule + past runs; outputs
  present. (SC-001)
- `git status` shows **only** the deletions of `agents/` and `prompts/` and the new `/config/`
  gitignore entry. (SC-002)
- `ls -l /data/dagster/agent-logs` is a symlink to `$AGENTBOX_DATA/runs`; a historical run's
  "transcript" link in the UI resolves. (FR-021)
- Clobber refusal: re-run `--apply` → refuses, naming a now-populated destination. (R-MIG-2)
- `/data/logs` still present, recorded "left untouched" in `/tmp/plan.txt`. (Clarification C)

## US2 — Fresh install from examples (P1)

In a clean directory:

```bash
git clone <repo> agentbox && cd agentbox
cp -r examples/config config
export AGENTBOX_DATA=/tmp/fresh-data DAGSTER_HOME=/tmp/fresh-dagster
scripts/bootstrap.sh
python3 litellm/generate.py
docker compose up -d
```

Verify:
- UI lists the example agents. (US2-1)
- Materialize one → its run dir appears under `$AGENTBOX_DATA/runs/`. (US2-2)
- During the materialization, a filesystem watch (`inotifywait -mr /`) records **zero** writes
  outside `config/` and `$AGENTBOX_DATA`, and `$DAGSTER_HOME` contains **no** agentbox run dirs.
  (SC-004)

## US3 — Relocate the roots to any disk (P2)

```bash
export AGENTBOX_CONFIG=/mnt/cfg AGENTBOX_DATA=/mnt/state DAGSTER_HOME=/mnt/dag
# bootstrap + up, run an agent, then:
# assert all reads/writes hit the /mnt paths and nothing lands in /data/agentbox or <repo>/config
```

Expected: zero writes in the default locations across a full run. (SC-005)

## US4 — Config edits stay out of the product repo (P2)

```bash
git -C config init            # config becomes its own repo
# edit an agent + a prompt through the UI, then:
git -C config status          # shows the edits
git status                    # product repo clean
```

Expected: edits land in `config/`; product repo git status clean. (SC-007)

## US5 — Config paths validated against the roots (P2)

Through the UI (or `ui/schema.validate` directly): submit an agent whose `output_dir` is under
the product tree → rejected with a message naming `output_dir` and stating the data-root rule.
Submit one with `output_dir`/`workspace`/`env_file` under the data root, omitted, or the
documented default → accepted. (SC-006)

## Docs check (Constitution VI)

- README has a "Layout" section describing the three kinds + both instance trees, and the
  file-tree listing matches the real subpaths. (FR-027)
- AGENTS.md states where each new kind of file goes. (FR-028)
- `.env.example` documents `AGENTBOX_CONFIG`, `AGENTBOX_DATA`, `DAGSTER_HOME`. (FR-029)
