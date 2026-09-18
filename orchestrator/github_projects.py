"""GitHub Projects v2 board observation + launch admission (spec 016, FR-022).

The module seam a board-driven trigger builds on. Observation (all network I/O) and
admission (pure, clock-injected) are separated by a hard boundary so a later feature can
re-home the observer:

  * ``GitHubProjectsClient.fetch_board`` — the outbound GraphQL read of the WHOLE board
    (all statuses/content-types), following pagination. The only network in this module.
  * ``filter_items`` — pure: keep only issues in the configured status passing the optional
    ``label``/``repo`` filters. Applied per sensor after the shared fetch.
  * ``plan_tick`` — pure: decide launches, held issues, and the next cursor over the
    already-filtered items. No network, no clock read (``now`` is injected).
  * ``feature_key`` / ``sanitize_title`` — pure identity helpers.

Every behaviour is unit-testable with a faked client and no network call (SC-010). See
contracts/orchestrator-model.md and contracts/github-projects-query.md.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# The env var names the run handoff sets on the container, and the run tags the sensor sets
# on the RunRequest (contracts/orchestrator-model.md §1). Stated once here so the factory and
# tests share one source. Title/body are NEVER tags (FR-015).
ISSUE_ENV_NAMES = ("AGENTBOX_ISSUE_NUMBER", "AGENTBOX_ISSUE_REPO", "AGENTBOX_ISSUE_URL",
                   "AGENTBOX_ISSUE_TITLE", "AGENTBOX_FEATURE_KEY", "AGENTBOX_ISSUE_BODY_FILE")
ISSUE_TAG_NAMES = ("agentbox/issue_number", "agentbox/issue_repo", "agentbox/issue_url",
                   "agentbox/project_item_id", "agentbox/feature_key")

# The GraphQL endpoint (Projects v2 is GraphQL-only; the REST API does not expose it — FR-003).
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
# Bounded outbound timeout; a timeout is a transient error (skip-with-reason, FR-019).
REQUEST_TIMEOUT = 20.0


# --- Types ------------------------------------------------------------------

@dataclass
class BoardItem:
    """One item on the board, derived from a GraphQL node (contracts/github-projects-query.md §4).

    ``fetch_board`` derives one for EVERY node (all statuses/content-types) so the result is
    shareable across sensors. Issue-only fields (number/title/body/url/repo/labels) are present
    only for issues; a PR/draft carries just ``item_id``/``content_type``/``status``.
    """
    item_id: str
    content_type: str            # "Issue" | "PullRequest" | "DraftIssue"
    status: str | None           # the Status single-select option name, or None
    number: int | None = None
    repo: str | None = None      # repository.nameWithOwner (owner/repo)
    url: str | None = None
    title: str | None = None
    body: str | None = None
    labels: list[str] = field(default_factory=list)


@dataclass
class Launch:
    """A launch the sensor turns into a RunRequest (contracts/orchestrator-model.md §2)."""
    run_key: str
    tags: dict
    run_config: dict
    item: BoardItem


@dataclass
class Held:
    """An eligible issue that could not launch because the slot is held (FR-009)."""
    item: BoardItem
    holder_number: int | None


@dataclass
class TickPlan:
    """The result of ``plan_tick`` (contracts/orchestrator-model.md §1)."""
    launches: list[Launch] = field(default_factory=list)
    held: list[Held] = field(default_factory=list)
    next_cursor: dict = field(default_factory=dict)
    skip_reason: str | None = None


class BoardError(Exception):
    """A transient GitHub error (5xx / connection / timeout) — skip, cursor untouched (FR-019)."""


class RateLimited(BoardError):
    """GitHub rate-limit (403/429 or a GraphQL RATE_LIMITED) — skip, cursor untouched (FR-019).

    A subclass of ``BoardError`` so a broad ``except BoardError`` still catches it; the sensor
    catches both and reports the rate-limit reason.
    """


class Unresolvable(Exception):
    """The board, Status field, or status option could not be resolved (FR-020).

    ``what`` names the offending thing (e.g. ``board owner/1`` / ``Status field`` /
    ``status option 'In progress'``) so the sensor's SkipReason can name it.
    """

    def __init__(self, what: str):
        self.what = what
        super().__init__(what)


# --- Config shape -----------------------------------------------------------
# `ProjectStatusCfg` is just the `on_project_status` mapping (owner/project/status/label/repo/
# interval_seconds). Passed around as a plain dict; documented here as the shape helpers read.
ProjectStatusCfg = dict


# --- Pure helpers (feature key + title, contracts/orchestrator-model.md §5) ---

def feature_key(number: int, title: str) -> str:
    """The stable feature key for a launch: ``NNN`` + a slug of the title (FR-011).

    ``NNN`` is the issue number zero-padded to three digits. The slug is the lowercased title
    with only ``a-z0-9`` kept (non-ASCII letters and emoji are DROPPED, not transliterated),
    every other run collapsed to a single ``-``, no leading/trailing hyphen. The whole key is
    capped at 48 chars, then any trailing hyphen is stripped; an empty slug yields ``NNN`` alone.
    Grammar ``^[0-9]{3}(-[a-z0-9]+)*$``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower())
    slug = slug.strip("-")
    key = f"{int(number):03d}" + (f"-{slug}" if slug else "")
    return key[:48].rstrip("-")


def sanitize_title(title: str) -> str:
    """The title with control characters dropped and capped at 256 chars (FR-015)."""
    stripped = "".join(c for c in (title or "") if unicodedata.category(c)[0] != "C")
    return stripped[:256]


# --- Filtering (PURE, no I/O) -----------------------------------------------

def filter_items(items: list[BoardItem], cfg: ProjectStatusCfg) -> list[BoardItem]:
    """Keep only launch candidates from the whole board (contracts/github-projects-query.md §4).

    Applied per sensor AFTER the shared fetch, so two agents on the same board with different
    statuses never cross-contaminate. Keeps only ``Issue`` items (PRs/drafts dropped, FR-004)
    whose Status option name equals ``cfg['status']`` case-insensitively (a null Status never
    matches), that pass the optional ``repo`` (full ``owner/repo``, case-insensitive) and
    ``label`` (exact membership of the label-name list, case-insensitive — NOT a substring
    match) filters. An issue whose ``repo`` is absent/blank is skipped defensively rather than
    launched with a blank repo (CHK005). Raises ``Unresolvable("status option '<status>'")``
    when the configured status matches no option present anywhere on the board (FR-020).
    """
    want_status = str(cfg["status"]).strip().lower()
    want_repo = cfg.get("repo")
    want_repo = str(want_repo).strip().lower() if want_repo else None
    want_label = cfg.get("label")
    want_label = str(want_label).strip().lower() if want_label else None

    # FR-020: the configured status must match SOME option present anywhere on the board,
    # else it is unresolvable (an operator typo, not "no items today").
    present_options = {(it.status or "").strip().lower() for it in items if it.status}
    if want_status not in present_options:
        raise Unresolvable(f"status option '{cfg['status']}'")

    kept: list[BoardItem] = []
    for it in items:
        if it.content_type != "Issue":
            continue
        if (it.status or "").strip().lower() != want_status:
            continue
        # Defensive: never launch an issue with a blank repo (CHK005).
        if not (it.repo and str(it.repo).strip()):
            continue
        if want_repo is not None and str(it.repo).strip().lower() != want_repo:
            continue
        if want_label is not None:
            names = {str(n).strip().lower() for n in (it.labels or [])}
            if want_label not in names:
                continue
        kept.append(it)
    return kept


# --- Admission (PURE, no I/O, clock injected) -------------------------------

def _launch_for(item: BoardItem, entered_at: str) -> Launch:
    """Build the ``Launch`` for an admitted item: run key, the five identity tags, and the
    ``run_config`` payload (contracts/orchestrator-model.md §2/§5). Title/body live only in
    ``run_config`` — never a tag (FR-015)."""
    key = feature_key(item.number, item.title or "")
    tags = {
        "agentbox/issue_number": str(item.number),
        "agentbox/issue_repo": item.repo,
        "agentbox/issue_url": item.url,
        "agentbox/project_item_id": item.item_id,
        "agentbox/feature_key": key,
    }
    run_config = {
        "number": item.number,
        "repo": item.repo,
        "url": item.url,
        "title": item.title or "",
        "feature_key": key,
        "body": item.body or "",
    }
    return Launch(run_key=f"{item.item_id}:{entered_at}", tags=tags, run_config=run_config, item=item)


def plan_tick(cursor_state: dict, items: list[BoardItem], cfg: ProjectStatusCfg,
              now: str) -> TickPlan:
    """Decide launches, held issues, and the next cursor over the already-filtered items.

    A pure function of ``(cursor_state, items, cfg, now)`` — no network, no clock read — so the
    whole state machine is unit-tested with a faked client (SC-010). See
    contracts/orchestrator-model.md §2 and data-model.md.

    * **First tick** (``cursor_state == {}`` — no persisted cursor): seed every in-status item
      ``{entered_at: now, launched: False, eligible: False}`` and launch nothing (FR-007). The
      discriminator is the ABSENCE of the cursor, never ``seen`` being empty — an empty-board
      first tick still persists ``{"version": 1, "seen": {}}`` so the next tick reads a present
      cursor and treats a genuine arrival as eligible.
    * **Normal tick**: drop left ids, carry both-present ids with their stored state, add new ids
      ``eligible: True``. The slot is occupied iff a carried id has ``launched: True``; candidates
      are ``launched: False`` AND ``eligible: True`` ordered by ``(entered_at, number)``. If the
      slot is free launch the oldest; the rest are held. Seeded ``eligible: False`` ids are never
      candidates (FR-007).
    """
    seen = cursor_state.get("seen", {})
    version = cursor_state.get("version", 1)
    S = {it.item_id: it for it in items}

    # First tick: no persisted cursor at all (cursor_state == {}). Seed pre-existing items as
    # ineligible and launch nothing (FR-007). An empty board still yields a non-empty cursor.
    if cursor_state == {}:
        next_seen = {
            iid: {"entered_at": now, "launched": False, "eligible": False} for iid in S
        }
        reason = (
            f"first tick: recorded {len(next_seen)} item(s) already in status, launched none"
        )
        return TickPlan(launches=[], held=[],
                        next_cursor={"version": 1, "seen": next_seen}, skip_reason=reason)

    # Normal tick — reconcile `seen` against the current in-status set S.
    next_seen: dict = {}
    for iid, item in S.items():
        if iid in seen:
            # Carried: keep the stored state (a seeded id stays eligible:false; a held id true).
            prev = seen[iid]
            next_seen[iid] = {
                "entered_at": prev.get("entered_at", now),
                "launched": bool(prev.get("launched", False)),
                "eligible": bool(prev.get("eligible", False)),
            }
        else:
            # New arrival — edge-triggered against the previous tick (FR-005).
            next_seen[iid] = {"entered_at": now, "launched": False, "eligible": True}
    # Left ids (in `seen` not in S) are simply not carried into next_seen (forgotten, FR-005).

    # Slot: occupied iff any carried id is still launched-and-in-status (FR-008).
    holder_iid = next((iid for iid, st in next_seen.items() if st["launched"]), None)
    holder_number = S[holder_iid].number if holder_iid is not None else None

    # Candidates: genuine arrivals still awaiting the slot, oldest first (FR-010).
    candidates = [
        iid for iid, st in next_seen.items() if not st["launched"] and st["eligible"]
    ]
    candidates.sort(key=lambda iid: (next_seen[iid]["entered_at"], S[iid].number or 0))

    launches: list[Launch] = []
    held: list[Held] = []
    if holder_iid is None and candidates:
        winner = candidates[0]
        next_seen[winner]["launched"] = True
        launches.append(_launch_for(S[winner], next_seen[winner]["entered_at"]))
        rest = candidates[1:]
        holder_number = S[winner].number
    else:
        rest = candidates

    for iid in rest:
        held.append(Held(item=S[iid], holder_number=holder_number))

    skip_reason = None
    if held and not launches:
        nums = ", ".join(f"#{S[iid].number}" for iid in rest)
        holder_txt = f"#{holder_number}" if holder_number is not None else "the active run"
        skip_reason = f"holding {nums} — {holder_txt} is in flight"

    return TickPlan(launches=launches, held=held,
                    next_cursor={"version": version, "seen": next_seen},
                    skip_reason=skip_reason)


# --- Observation (all I/O) --------------------------------------------------
# The GraphQL query reading the WHOLE board (contracts/github-projects-query.md §2). Owner is
# resolved as an organization first, then retried as a user (best-effort user-owned board).
_BOARD_QUERY = """
query($owner: String!, $project: Int!, $after: String) {
  %(root)s(login: $owner) {
    projectV2(number: $project) {
      title
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
          content {
            __typename
            ... on Issue {
              number title body url
              repository { nameWithOwner }
              labels(first: 50) { nodes { name } }
            }
          }
        }
      }
    }
  }
}
"""


def _status_of(node: dict) -> str | None:
    """The item's current Status single-select option name, or None.

    The Status field is the single-select whose field name equals ``Status`` case-insensitively
    (contracts/github-projects-query.md §2). Returns the option ``name`` for that field.
    """
    for fv in ((node.get("fieldValues") or {}).get("nodes") or []):
        if not isinstance(fv, dict) or not fv.get("name"):
            continue
        fld = fv.get("field") or {}
        if str(fld.get("name", "")).strip().lower() == "status":
            return fv["name"]
    return None


def _board_item(node: dict) -> BoardItem:
    """Derive a ``BoardItem`` from one GraphQL node (contracts/github-projects-query.md §4)."""
    content = node.get("content") or {}
    ctype = content.get("__typename") or ""
    item = BoardItem(item_id=node.get("id"), content_type=ctype, status=_status_of(node))
    if ctype == "Issue":
        item.number = content.get("number")
        item.title = content.get("title")
        item.body = content.get("body")
        item.url = content.get("url")
        repo = content.get("repository") or {}
        item.repo = repo.get("nameWithOwner")
        item.labels = [n.get("name") for n in ((content.get("labels") or {}).get("nodes") or [])
                       if isinstance(n, dict) and n.get("name")]
    return item


class GitHubProjectsClient:
    """The outbound GraphQL reader for a Projects v2 board (all I/O lives here).

    The token comes from ``GITHUB_PROJECT_TOKEN`` only (the sensor reads it; §6) — never a
    fallback to ``GITHUB_TOKEN``. It is used solely to sign the request and never leaves this
    process (FR-016/FR-017).
    """

    def __init__(self, token: str):
        self._token = token

    def _post(self, client, root: str, owner: str, project: int, after):
        """One GraphQL POST for a given owner-root (``organization`` or ``user``).

        Returns the parsed ``projectV2`` mapping, or ``None`` when the owner-root itself is null
        (so the caller can retry the other root). Raises the transient/rate-limit errors here so
        one page's failure is mapped uniformly (contracts/github-projects-query.md §5).
        """
        try:
            resp = client.post(
                GRAPHQL_ENDPOINT,
                headers={"Authorization": f"Bearer {self._token}",
                         "Content-Type": "application/json"},
                json={"query": _BOARD_QUERY % {"root": root},
                      "variables": {"owner": owner, "project": int(project), "after": after}},
            )
        except Exception as e:  # httpx transport/timeout → transient (FR-019)
            raise BoardError(f"request failed: {e}") from e
        if resp.status_code in (403, 429):
            raise RateLimited("rate limited")
        if resp.status_code >= 500:
            raise BoardError(f"HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except Exception as e:
            raise BoardError(f"malformed response: {e}") from e
        for err in (payload.get("errors") or []):
            if str(err.get("type") or "").upper() == "RATE_LIMITED" or \
               "rate limit" in str(err.get("message", "")).lower():
                raise RateLimited("rate limited")
        data = payload.get("data") or {}
        owner_node = data.get(root)
        if owner_node is None:
            return None
        return owner_node.get("projectV2")

    def fetch_board(self, owner: str, project: int) -> list[BoardItem]:
        """Read the WHOLE board's items + Status, following pagination (FR-021).

        Issues the GraphQL POST(s) via httpx with a bounded timeout, returning a ``BoardItem``
        for every node across all pages (unfiltered, so the result is shareable across sensors
        watching the same board on different statuses). Retries with ``user(login:)`` when
        ``organization(login:)`` resolves null (best-effort user-owned board). Raises
        ``RateLimited``/``BoardError`` (transient) or ``Unresolvable("board …")`` /
        ``Unresolvable("Status field")`` (contracts/github-projects-query.md §3/§5).
        """
        import httpx  # imported lazily so the module loads even where httpx is absent

        items: list[BoardItem] = []
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            root = "organization"
            after = None
            project_node = self._post(client, root, owner, project, after)
            if project_node is None:
                # org resolved null (or org itself null) — retry the user-owned board.
                root = "user"
                project_node = self._post(client, root, owner, project, after)
            if project_node is None:
                raise Unresolvable(f"board {owner}/{project}")

            saw_status_field = False
            while True:
                nodes = ((project_node.get("items") or {}).get("nodes")) or []
                for node in nodes:
                    if _status_field_present(node):
                        saw_status_field = True
                    items.append(_board_item(node))
                page = (project_node.get("items") or {}).get("pageInfo") or {}
                if not page.get("hasNextPage"):
                    break
                after = page.get("endCursor")
                project_node = self._post(client, root, owner, project, after)
                if project_node is None:
                    raise Unresolvable(f"board {owner}/{project}")

        # No single-select field named "Status" anywhere on the board is unresolvable (FR-020).
        if items and not saw_status_field:
            raise Unresolvable("Status field")
        return items


def _status_field_present(node: dict) -> bool:
    """Whether this node carries a single-select field named ``Status`` (case-insensitive).

    Used to detect a board with no Status field at all — an ``Unresolvable("Status field")``
    (FR-020) — distinct from an item that merely has no Status value set.
    """
    for fv in ((node.get("fieldValues") or {}).get("nodes") or []):
        if not isinstance(fv, dict):
            continue
        fld = fv.get("field") or {}
        if str(fld.get("name", "")).strip().lower() == "status":
            return True
    return False
