# Contract: Orchestrator model — the polling sensor, admission, cursor, and issue handoff

How the orchestrator turns `on_project_status` into a polling sensor, decides launches, and hands the
issue to a run. Authority: new `orchestrator/github_projects.py`, `orchestrator/factory.py`,
`orchestrator/definitions.py`. The GraphQL read is in
[github-projects-query.md](github-projects-query.md).

## §1 Module boundary (`orchestrator/github_projects.py`) — FR-022

Observation and admission are separated by a hard seam so a later feature can re-home the observer:

```python
# --- Observation (all I/O) ---
class GitHubProjectsClient:
    def __init__(self, token: str): ...            # token from GITHUB_PROJECT_TOKEN only (§6)
    def fetch_board(self, owner: str, project: int) -> list[BoardItem]:
        """Outbound GraphQL read of the WHOLE board's items + Status, following pagination (FR-021).
        Returns every item (all statuses/content-types) so the result is shareable across sensors
        watching the same board on different statuses (FR-021). Raises RateLimited / BoardError
        (transient) or Unresolvable(what) (board/Status-field). Status-option resolution and the
        status/label/repo filtering are NOT done here — see filter_items."""

# --- Filtering (PURE, no I/O) ---
def filter_items(items: list[BoardItem], cfg: ProjectStatusCfg) -> list[BoardItem]:
    """Keep only issues (drop PRs/drafts) whose Status equals cfg.status case-insensitively and
    that pass the optional label + owner/repo filters (FR-004). The `label` filter is exact
    membership of the issue's label-name list, matched case-insensitively (like `status`/`repo`); it
    is NOT a substring match. An issue whose `repository.nameWithOwner` is absent/blank is skipped
    defensively rather than launched with a blank repo (CHK005). Applied per sensor AFTER the shared
    fetch, so two agents on the same board with different statuses never cross-contaminate. Raises
    Unresolvable("status option '<status>'") when the configured status matches no option present
    anywhere on the board (FR-020)."""

# --- Admission (PURE, no I/O, clock injected) ---
def plan_tick(cursor_state: dict, items: list[BoardItem], cfg: ProjectStatusCfg, now: str) -> TickPlan:
    """Decide launches, held issues, and the next cursor over the already-filtered items.
    No network, no clock read."""

# --- Pure helpers ---
def feature_key(number: int, title: str) -> str: ...     # §5
def sanitize_title(title: str) -> str: ...               # §5
ISSUE_ENV_NAMES = ("AGENTBOX_ISSUE_NUMBER", "AGENTBOX_ISSUE_REPO", "AGENTBOX_ISSUE_URL",
                   "AGENTBOX_ISSUE_TITLE", "AGENTBOX_FEATURE_KEY", "AGENTBOX_ISSUE_BODY_FILE")
ISSUE_TAG_NAMES = ("agentbox/issue_number", "agentbox/issue_repo", "agentbox/issue_url",
                   "agentbox/project_item_id", "agentbox/feature_key")
```

`TickPlan = {launches: list[Launch], held: list[Held], next_cursor: dict, skip_reason: str | None}`
where `Launch` carries `{run_key, tags, run_config, item}` ready for the sensor to turn into a
`RunRequest`, and `Held = {item, holder_number}`.

## §2 Admission — `plan_tick` (FR-004..FR-010)

Given `items` already filtered by the client to **issues in the configured status passing the `label`
and `repo` filters** (PRs/drafts/other-status dropped, FR-004), let `S = {item.item_id}` and
`seen = cursor_state["seen"]`:

1. **First tick** (`cursor_state` empty / no `seen`): `next_cursor.seen = {id: {entered_at: now,
   launched: false, eligible: false} for id in S}`; `launches = []`; `skip_reason = "first tick:
   recorded N items already in status, launched none"` (FR-007). The seeded ids are `eligible: false`,
   so they are **never** admission candidates on any later tick — a pre-existing item cannot launch by
   being carried forward (fixes the two-field ambiguity: "seeded" ≠ "held").
2. **Normal tick**:
   - **Left**: ids in `seen` not in `S` are dropped (forgotten, FR-005).
   - **Carried**: ids in both keep their stored `{entered_at, launched, eligible}` (a seeded id stays
     `eligible: false`; a held id stays `eligible: true`).
   - **New**: ids in `S` not in `seen` are added `{entered_at: now, launched: false, eligible: true}` —
     a genuine arrival, edge-triggered against the previous tick (FR-005).
   - **Slot**: occupied iff any carried id has `launched: true` (the active issue is still in status,
     FR-008). `holder` = that id's issue number.
   - **Admit**: candidates = ids with `launched: false` **and** `eligible: true` (genuine arrivals
     still awaiting the slot — new plus carried-held; first-tick-seeded `eligible: false` ids are
     **never** candidates), ordered by `entered_at` then number. If the slot is free, take the
     **oldest** candidate, mark its `launched: true`, and emit one `Launch`; the remaining candidates
     become `held`. If the slot is occupied, emit no launch and all candidates are `held`
     (FR-009/FR-010).
   - `skip_reason` = a held report naming the holder when there are held issues and no launch, else
     `None`.
3. **Run key**: `f"{item_id}:{entered_at}"` (FR-006) — stable across ticks/restarts, new on re-entry.
4. **Tags / run_config** for a `Launch` — the five identity tags (`ISSUE_TAG_NAMES`) and the payload
   `{number, repo, url, title, feature_key, body}` (§4). `title`/`body` are **never** in tags (FR-015).

`plan_tick` is a pure function of `(cursor_state, items, cfg, now)`, so the whole state machine
(enter/stay/leave/re-enter/first-tick/held/release-order) is unit-tested with a faked client and no
network (SC-010).

## §3 The sensor — `factory.build_project_status_sensor(cfg)` (FR-002/FR-003)

```python
def build_project_status_sensor(cfg: dict) -> SensorDefinition:
    ps = cfg["triggers"]["on_project_status"]
    name = f"project_status_{cfg['name'].replace('-', '_')}"

    @sensor(name=name, minimum_interval_seconds=int(ps.get("interval_seconds", 60)),
            default_status=DefaultSensorStatus.STOPPED,
            **_target(cfg))                       # job=agent_<name> or asset target, per kind
    def _sensor(context: SensorEvaluationContext):
        token = os.environ.get("GITHUB_PROJECT_TOKEN")
        if not token:
            yield SkipReason("GITHUB_PROJECT_TOKEN is not set (no fallback to GITHUB_TOKEN)")  # FR-016
            return
        try:
            board = board_cache_get(ps["owner"], ps["project"]) or \
                    GitHubProjectsClient(token).fetch_board(ps["owner"], ps["project"])   # WHOLE board, shareable
            items = filter_items(board, ps)              # per-sensor status/label/repo filter (FR-004)
        except Unresolvable as e:
            yield SkipReason(f"could not resolve {e.what}")                                    # FR-020
            return
        except (RateLimited, BoardError) as e:
            yield SkipReason(f"GitHub unavailable: {e}")                                       # FR-019
            return                                                                            # cursor untouched
        state = json.loads(context.cursor) if context.cursor else {}
        plan = plan_tick(state, items, ps, now=_utcnow_iso())
        for lk in plan.launches:
            yield RunRequest(run_key=lk.run_key, tags=lk.tags, run_config=lk.run_config,
                             **_run_target(cfg))          # asset_selection= or job_name=
        if plan.skip_reason and not plan.launches:
            yield SkipReason(plan.skip_reason)             # held report / first tick (FR-009)
        context.update_cursor(json.dumps(plan.next_cursor))
    return _sensor
```

- **Paused by default** (`STOPPED`) and **named `project_status_<name>`** — the operator toggle model
  is the same as `autocond_<name>` (FR-025).
- **Per-kind launch** (FR-002): `_run_target` yields `asset_selection=[AssetKey(...)]` for an
  asset-kind agent (records a materialization, as the UI does) and `job_name=f"agent_{name}"` for a
  job-kind agent — the same launch distinction the UI makes.
- **Cursor untouched on error** (FR-019/FR-020): the two `except` arms `return` before
  `update_cursor`, so a transient/unresolvable tick loses nothing and re-fires nothing.
- **Shared query** (FR-021): `board_cache_get` is a short-TTL process-local memo keyed by
  `(owner, project)` that stores the **whole board** (all statuses/content-types); a cache miss
  fetches and stores. Each sensor then applies its own `filter_items`, so two agents on the same
  board with different statuses share the one query without cross-contamination (spec Edge Case
  "Same board, different statuses"). Best-effort; correctness never depends on the cache.

## §4 Issue handoff into the run — `factory._prepare_issue_handoff` (FR-012/FR-013/FR-014/FR-015)

The twin of spec-013's `_prepare_upstream_handoff`, called in the op before `_build_agent_cmd`:

```python
def _prepare_issue_handoff(cfg: dict, context) -> tuple[str | None, dict]:
    issue = (context.op_config or {}).get("issue") or _issue_from_run_config(context)
    if not issue:
        return None, {}                                   # not a sensor-launched run — unchanged path
    os.makedirs(paths.STAGING_ROOT, exist_ok=True)
    handoff_dir = tempfile.mkdtemp(prefix="issue-", dir=paths.STAGING_ROOT)
    os.chmod(handoff_dir, 0o777)
    body_path = os.path.join(handoff_dir, "body.md")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(issue.get("body") or "")
    os.chmod(body_path, 0o644)                            # non-root container reads it
    env = {
        "AGENTBOX_ISSUE_NUMBER":   str(issue["number"]),
        "AGENTBOX_ISSUE_REPO":     issue["repo"],         # full owner/repo (FR-013)
        "AGENTBOX_ISSUE_URL":      issue["url"],
        "AGENTBOX_ISSUE_TITLE":    sanitize_title(issue.get("title") or ""),  # control-stripped, <=256
        "AGENTBOX_FEATURE_KEY":    issue["feature_key"],
        "AGENTBOX_ISSUE_BODY_FILE": "/issue/body.md",     # path only — body never on cmdline/env (FR-014)
    }
    return handoff_dir, env
```

Wiring in `make_run_op` (mirrors the upstream handoff exactly):
- `issue_dir, issue_env = _prepare_issue_handoff(cfg, context)`
- `launch_env = {**runtime_env, **upstream_env, **issue_env}`
- `_launch_mounts` adds `{source: issue_dir, target: "/issue", mode: "ro"}` when `issue_dir` is set;
  `_build_agent_cmd` gets `-v <issue_dir>:/issue:ro` (read-only, FR-013).
- The dir is `--rm`-cleaned in the op's `finally`, like pipes/staging/upstream.

The op gains an optional `issue` config field so the sensor's `RunRequest.run_config` reaches it. The
five identity **tags** are set on the `RunRequest` (§2), so the run carries them from creation (FR-012)
and the run page links the issue (FR-026). Title/body live only in `run_config` (never a tag, FR-015).

## §5 Feature key and title (FR-011/FR-015)

```python
def feature_key(number: int, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())      # non-ASCII/emoji already gone (only a-z0-9 kept)
    slug = slug.strip("-")
    key = f"{number:03d}" + (f"-{slug}" if slug else "")  # empty slug -> NNN alone (no trailing hyphen)
    return key[:48].rstrip("-")                            # cap whole key at 48, strip any trailing hyphen

def sanitize_title(title: str) -> str:
    stripped = "".join(c for c in title if unicodedata.category(c)[0] != "C")  # drop control chars
    return stripped[:256]                                  # cap at 256 (FR-015)
```

- Non-ASCII letters and emoji are **dropped** (they are not in `a-z0-9`), not transliterated (spec
  clarification). `038-ui-update-runs-overview-page`; an all-punctuation title ⇒ `038`.
- The key cap (48) and the title cap (256) are independent. Pinned by test vectors (SC-007).

## §6 Token isolation (FR-016/FR-017)

- `GitHubProjectsClient` reads the token **only** from `GITHUB_PROJECT_TOKEN`; the sensor skips naming
  it when unset, with **no** fallback to `GITHUB_TOKEN` (FR-016).
- The token is used only to sign the outbound request. It is **never** placed in a `RunRequest` tag,
  `run_config`, env value, log line, or file (FR-017). It rides through `orchestrator/redact.py` (the
  `github_pat_`/`ghp_`/`gho_` prefixes and the `*TOKEN*` name rule already mask it) as defence in depth.

## §7 Governors & lineage (FR-018)

No new code: the `RunRequest` from a sensor carries `dagster/sensor_name` (Dagster-set), so
`is_automated_run(context)` is true, `governor_gate` applies (the run counts toward `max_runs_per_hour`
and is refused past `max_chain_depth`), and `derive_chain_depth` returns 1 (no automated upstream ⇒ a
root chain at depth 1). The existing gate, tags, and metadata recording are reused unchanged.

## §8 Load-time wiring (`orchestrator/definitions.py`) — FR-023

`discover()` calls `_project_status(cfg)`: on a malformed block, `RejectAgent(file, field-message)`
(the agent is skipped, others load); on a valid block,
`sensors.append(build_project_status_sensor(cfg))`, for both asset- and job-kind agents. The block
composes with the agent's existing triggers (the asset automation sensor and any schedule are built as
before).

## §9 What is unchanged

`make_run_op` / the container launch, Pipes transport, redaction, run-directory capture, the upstream
handoff, the governor gate, and the asset/job routing (spec 006/013) are untouched apart from: the new
`project_status_<name>` sensor, the `:ro /issue` mount + `AGENTBOX_ISSUE_*` env values, the op's
optional `issue` config field, and the five `agentbox/issue_*` tags on the sensor's `RunRequest`. No
per-harness code path is added.
