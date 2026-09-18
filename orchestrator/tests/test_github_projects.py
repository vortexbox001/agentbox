"""Tests for the GitHub Projects board observer + launch admission (spec 016).

Everything here runs with GitHub **faked** and **no network call** (SC-010): the pure
``filter_items`` / ``plan_tick`` / ``feature_key`` / ``sanitize_title`` take plain data, and
``fetch_board``'s I/O is exercised through an ``httpx.MockTransport`` that never touches the
network. The shared ``FakeGitHubProjectsClient`` stands in for the real client in the sensor
tests (test_factory.py).
"""
import json

import httpx
import pytest

import github_projects as gp
from github_projects import (
    BoardItem, GitHubProjectsClient, filter_items, plan_tick, feature_key, sanitize_title,
    BoardError, RateLimited, Unresolvable,
)


# --- Fixture builders -------------------------------------------------------

def bi(item_id, status="In progress", content_type="Issue", number=1, title="A title",
       body="body", repo="owner/repo", labels=None):
    """A ``BoardItem`` for the pure filter/admission tests."""
    return BoardItem(item_id=item_id, content_type=content_type, status=status, number=number,
                     repo=repo, url=f"https://github.com/{repo}/issues/{number}", title=title,
                     body=body, labels=list(labels or []))


class FakeGitHubProjectsClient:
    """Stands in for ``GitHubProjectsClient`` in the sensor tests.

    Constructed with a preset whole board (``list[BoardItem]``); ``fetch_board`` returns it and
    records each call so a test can assert the per-tick board cache served one raw fetch across
    two sensors on the same ``(owner, project)`` (FR-021). ``raises`` makes ``fetch_board`` raise
    the given exception (resilience tests).
    """

    def __init__(self, board=None, raises=None):
        self.board = board or []
        self.raises = raises
        self.calls: list[tuple] = []

    def __call__(self, token):
        # the factory does GitHubProjectsClient(token).fetch_board(...); this makes the class
        # itself the fake so a single instance records every construction+fetch.
        self._token = token
        return self

    def fetch_board(self, owner, project):
        self.calls.append((owner, project))
        if self.raises is not None:
            raise self.raises
        return list(self.board)


def _node(item_id, *, status="In progress", typename="Issue", number=1, title="A title",
          body="body", repo="owner/repo", labels=None, with_status_field=True):
    """A GraphQL ``items.nodes[]`` node (for the MockTransport fetch_board tests)."""
    field_values = []
    if with_status_field:
        field_values.append({"name": status,
                             "field": {"name": "Status"}} if status is not None
                            else {"name": None, "field": {"name": "Status"}})
    content = {"__typename": typename}
    if typename == "Issue":
        content.update({
            "number": number, "title": title, "body": body,
            "url": f"https://github.com/{repo}/issues/{number}",
            "repository": {"nameWithOwner": repo},
            "labels": {"nodes": [{"name": n} for n in (labels or [])]},
        })
    return {"id": item_id, "fieldValues": {"nodes": field_values}, "content": content}


def _graphql_page(nodes, *, has_next=False, end_cursor=None, root="organization"):
    """A full GraphQL response payload for one page of a board."""
    return {"data": {root: {"projectV2": {
        "title": "Board",
        "items": {"pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                  "nodes": nodes}}}}}


def mock_httpx(monkeypatch, responder):
    """Route ``httpx.Client`` created inside ``fetch_board`` through a ``MockTransport``.

    ``responder(request_json) -> httpx.Response`` decides each response from the parsed request
    body, so no network call is made (SC-010).
    """
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        return responder(body)

    transport = httpx.MockTransport(handler)
    orig_client = httpx.Client

    def make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", make_client)


CFG = {"owner": "owner", "project": 1, "status": "In progress"}


# --- fetch_board happy path + BoardItem derivation (T005) -------------------

def test_fetch_board_derives_boarditem_for_every_node(monkeypatch):
    nodes = [
        _node("i1", status="In progress", number=10, repo="owner/repo", labels=["brief"]),
        _node("p1", typename="PullRequest", status="In progress"),
        _node("d1", typename="DraftIssue", status="Todo"),
        _node("i2", status="Done", number=11, repo="owner/repo"),
    ]
    mock_httpx(monkeypatch, lambda body: httpx.Response(200, json=_graphql_page(nodes)))
    board = GitHubProjectsClient("tok").fetch_board("owner", 1)
    assert [b.item_id for b in board] == ["i1", "p1", "d1", "i2"]  # whole board, unfiltered
    issue = board[0]
    assert issue.content_type == "Issue" and issue.number == 10
    assert issue.repo == "owner/repo" and issue.labels == ["brief"]
    assert issue.status == "In progress"
    assert board[1].content_type == "PullRequest"


def test_filter_items_keeps_only_matching_issues():
    items = [
        bi("i1", status="In progress", number=1),
        bi("i2", status="Done", number=2),
        bi("p1", status="In progress", content_type="PullRequest", number=3),
        bi("i3", status="in progress", number=4),  # case-insensitive match
    ]
    kept = filter_items(items, CFG)
    assert {i.item_id for i in kept} == {"i1", "i3"}


# --- plan_tick launch (T005) ------------------------------------------------

def test_plan_tick_launches_new_arrival_with_run_key_tags_and_config():
    # A present (non-empty) cursor with no seen items → the arrival is a genuine new arrival.
    state = {"version": 1, "seen": {}}
    item = bi("ITEM1", number=38, title="UI: update runs overview page", repo="o/r")
    plan = plan_tick(state, [item], CFG, now="2026-09-17T21:20:00Z")
    assert len(plan.launches) == 1
    lk = plan.launches[0]
    assert lk.run_key == "ITEM1:2026-09-17T21:20:00Z"
    assert set(lk.tags) == set(gp.ISSUE_TAG_NAMES)
    assert lk.tags["agentbox/issue_number"] == "38"
    assert lk.tags["agentbox/feature_key"] == "038-ui-update-runs-overview-page"
    assert lk.tags["agentbox/project_item_id"] == "ITEM1"
    # title/body live only in run_config, never a tag (FR-015)
    assert "title" not in lk.tags and "body" not in lk.tags
    assert lk.run_config == {
        "number": 38, "repo": "o/r", "url": item.url,
        "title": "UI: update runs overview page",
        "feature_key": "038-ui-update-runs-overview-page", "body": "body",
    }
    assert plan.next_cursor["seen"]["ITEM1"]["launched"] is True


# --- plan_tick cursor state machine (T014) ----------------------------------

def test_first_tick_seeds_everything_ineligible_and_launches_nothing():
    items = [bi("a", number=1), bi("b", number=2)]
    plan = plan_tick({}, items, CFG, now="T0")
    assert plan.launches == []
    assert plan.next_cursor["version"] == 1
    for iid in ("a", "b"):
        st = plan.next_cursor["seen"][iid]
        assert st == {"entered_at": "T0", "launched": False, "eligible": False}
    assert "first tick" in plan.skip_reason


def test_empty_board_first_start_persists_nonempty_cursor_then_launches():
    first = plan_tick({}, [], CFG, now="T0")
    assert first.next_cursor == {"version": 1, "seen": {}}   # non-empty even for empty board
    # the NEXT tick reads a present cursor → a genuine arrival is eligible and launches (US1 path)
    second = plan_tick(first.next_cursor, [bi("a", number=5)], CFG, now="T1")
    assert len(second.launches) == 1
    assert second.launches[0].run_key == "a:T1"


def test_second_tick_after_seeding_launches_none_holds_nothing():
    seeded = plan_tick({}, [bi("a", number=1), bi("b", number=2)], CFG, now="T0")
    # same seeded items still in status, no new arrivals
    plan = plan_tick(seeded.next_cursor, [bi("a", number=1), bi("b", number=2)], CFG, now="T1")
    assert plan.launches == []
    assert plan.held == []   # seeded items are eligible:false → never candidates


def test_stay_does_not_relaunch():
    state = {"version": 1, "seen": {"a": {"entered_at": "T0", "launched": True, "eligible": True}}}
    plan = plan_tick(state, [bi("a", number=1)], CFG, now="T1")
    assert plan.launches == []
    assert plan.next_cursor["seen"]["a"]["launched"] is True


def test_leave_drops_id_from_seen():
    state = {"version": 1, "seen": {"a": {"entered_at": "T0", "launched": True, "eligible": True}}}
    plan = plan_tick(state, [], CFG, now="T1")   # 'a' left the status
    assert "a" not in plan.next_cursor["seen"]


def test_reenter_gets_fresh_entered_at_and_launches_again():
    # 'a' was launched then left; now it re-enters with an empty seen (fresh entry).
    state = {"version": 1, "seen": {}}
    plan = plan_tick(state, [bi("a", number=1)], CFG, now="T5")
    assert len(plan.launches) == 1
    assert plan.launches[0].run_key == "a:T5"   # new entered_at → new run key


def test_restart_same_cursor_produces_same_run_key():
    # A launched item still in status on restart: the cursor reloads, no relaunch, key stable.
    state = {"version": 1, "seen": {"a": {"entered_at": "T0", "launched": True, "eligible": True}}}
    plan = plan_tick(state, [bi("a", number=1)], CFG, now="T9")
    assert plan.launches == []
    # were it to relaunch, the key would still be a:T0 (entered_at preserved) — but it does not.
    assert plan.next_cursor["seen"]["a"]["entered_at"] == "T0"


def test_every_next_cursor_carries_version():
    for state, items in (({}, [bi("a")]), ({"version": 1, "seen": {}}, [bi("a")])):
        plan = plan_tick(state, items, CFG, now="T0")
        assert plan.next_cursor.get("version") == 1


# --- plan_tick slot (T016) --------------------------------------------------

def test_second_eligible_issue_is_held_naming_holder():
    state = {"version": 1, "seen": {"a": {"entered_at": "T0", "launched": True, "eligible": True}}}
    plan = plan_tick(state, [bi("a", number=1), bi("b", number=2)], CFG, now="T1")
    assert plan.launches == []
    assert len(plan.held) == 1 and plan.held[0].item.item_id == "b"
    assert plan.held[0].holder_number == 1
    assert "#1" in plan.skip_reason


def test_when_active_leaves_oldest_held_launches():
    # 'a' (holder) has left; 'b' held from an earlier tick now launches.
    state = {"version": 1, "seen": {
        "b": {"entered_at": "T0", "launched": False, "eligible": True},
    }}
    plan = plan_tick(state, [bi("b", number=2)], CFG, now="T2")
    assert len(plan.launches) == 1 and plan.launches[0].item.item_id == "b"


def test_three_simultaneous_entrants_launch_oldest_first_one_per_slot():
    # All three arrive on a present cursor's first normal tick → same entered_at, ordered by number.
    state = {"version": 1, "seen": {}}
    items = [bi("c", number=3), bi("a", number=1), bi("b", number=2)]
    plan = plan_tick(state, items, CFG, now="T0")
    assert len(plan.launches) == 1
    assert plan.launches[0].item.number == 1     # oldest by (entered_at, number)
    assert {h.item.number for h in plan.held} == {2, 3}


# --- filter_items filters (T018) --------------------------------------------

def test_filter_drops_prs_and_drafts():
    items = [bi("i", number=1), bi("p", content_type="PullRequest", number=2),
             bi("d", content_type="DraftIssue", number=3)]
    kept = filter_items(items, CFG)
    assert [i.item_id for i in kept] == ["i"]


def test_label_filter_is_exact_membership_case_insensitive_not_substring():
    cfg = dict(CFG, label="brief")
    items = [
        bi("has", number=1, labels=["Brief", "x"]),      # exact (case-insensitive)
        bi("substr", number=2, labels=["briefing"]),      # substring must NOT match
        bi("none", number=3, labels=["other"]),
    ]
    kept = filter_items(items, cfg)
    assert [i.item_id for i in kept] == ["has"]


def test_repo_filter_case_insensitive():
    cfg = dict(CFG, repo="Owner/Repo")
    items = [bi("a", number=1, repo="owner/repo"), bi("b", number=2, repo="other/repo")]
    kept = filter_items(items, cfg)
    assert [i.item_id for i in kept] == ["a"]


def test_null_status_never_matches():
    items = [bi("a", number=1, status=None), bi("b", number=2, status="In progress")]
    kept = filter_items(items, CFG)
    assert [i.item_id for i in kept] == ["b"]


def test_blank_repo_issue_skipped_defensively():
    items = [bi("a", number=1, repo=""), bi("b", number=2, repo=None),
             bi("c", number=3, repo="owner/repo")]
    kept = filter_items(items, CFG)
    assert [i.item_id for i in kept] == ["c"]


def test_status_matching_no_option_raises_unresolvable():
    items = [bi("a", number=1, status="Todo"), bi("b", number=2, status="Done")]
    with pytest.raises(Unresolvable) as e:
        filter_items(items, CFG)
    assert "status option 'In progress'" in e.value.what


# --- feature_key / sanitize_title vectors (T020) ----------------------------

GRAMMAR = __import__("re").compile(r"^[0-9]{3}(-[a-z0-9]+)*$")


def test_feature_key_basic_vector():
    assert feature_key(38, "UI: update runs overview page") == "038-ui-update-runs-overview-page"


@pytest.mark.parametrize("title", [
    "!!!@@@###", "🎉🎉🎉", "a/b/c ../.. path", "x" * 200,
    "Café déjà vu", "emoji 🚀 mixed Text",
])
def test_feature_key_always_valid_and_capped(title):
    key = feature_key(38, title)
    assert GRAMMAR.match(key), key
    assert len(key) <= 48


def test_all_punctuation_or_emoji_title_yields_number_alone():
    assert feature_key(38, "!!!") == "038"
    assert feature_key(38, "🎉") == "038"


def test_non_ascii_and_emoji_dropped_not_transliterated():
    # 'Café' → 'caf' (é dropped), not 'cafe'
    assert feature_key(1, "Café") == "001-caf"
    assert feature_key(2, "naïve 🚀 rocket") == "002-na-ve-rocket"


def test_two_same_title_issues_differ_by_number():
    assert feature_key(1, "same title") != feature_key(2, "same title")


def test_sanitize_title_strips_control_chars_and_caps_256():
    assert sanitize_title("a\x00b\x07c") == "abc"
    assert sanitize_title("x" * 300) == "x" * 256


# --- resilience: error mapping + pagination (T024) --------------------------

def test_http_5xx_maps_to_board_error(monkeypatch):
    mock_httpx(monkeypatch, lambda body: httpx.Response(502, text="bad gateway"))
    with pytest.raises(BoardError):
        GitHubProjectsClient("t").fetch_board("owner", 1)


def test_connection_error_maps_to_board_error(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("no route", request=request)
    transport = httpx.MockTransport(boom)
    orig = httpx.Client
    monkeypatch.setattr(httpx, "Client",
                        lambda *a, **k: orig(*a, **{**k, "transport": transport}))
    with pytest.raises(BoardError):
        GitHubProjectsClient("t").fetch_board("owner", 1)


def test_403_and_429_and_graphql_rate_limited_map_to_rate_limited(monkeypatch):
    for status in (403, 429):
        mock_httpx(monkeypatch, lambda body, s=status: httpx.Response(s, json={}))
        with pytest.raises(RateLimited):
            GitHubProjectsClient("t").fetch_board("owner", 1)
    mock_httpx(monkeypatch, lambda body: httpx.Response(
        200, json={"data": {"organization": None}, "errors": [{"type": "RATE_LIMITED"}]}))
    with pytest.raises(RateLimited):
        GitHubProjectsClient("t").fetch_board("owner", 1)


def test_null_org_and_user_maps_to_unresolvable_board(monkeypatch):
    def responder(body):
        # both organization and user resolve null → board unresolvable
        root = "organization" if "organization" in body["query"] else "user"
        return httpx.Response(200, json={"data": {root: None}})
    mock_httpx(monkeypatch, responder)
    with pytest.raises(Unresolvable) as e:
        GitHubProjectsClient("t").fetch_board("owner", 1)
    assert "board owner/1" in e.value.what


def test_user_owned_board_retry_succeeds(monkeypatch):
    def responder(body):
        if "organization" in body["query"]:
            return httpx.Response(200, json={"data": {"organization": None}})
        return httpx.Response(200, json=_graphql_page(
            [_node("u1", number=7)], root="user"))
    mock_httpx(monkeypatch, responder)
    board = GitHubProjectsClient("t").fetch_board("owner", 1)
    assert [b.item_id for b in board] == ["u1"]


def test_missing_status_field_maps_to_unresolvable(monkeypatch):
    nodes = [_node("i1", number=1, with_status_field=False)]
    mock_httpx(monkeypatch, lambda body: httpx.Response(200, json=_graphql_page(nodes)))
    with pytest.raises(Unresolvable) as e:
        GitHubProjectsClient("t").fetch_board("owner", 1)
    assert "Status field" in e.value.what


def test_pagination_is_followed_so_page_two_item_is_considered(monkeypatch):
    page1 = _graphql_page([_node("p1a", number=1)], has_next=True, end_cursor="CUR")
    page2 = _graphql_page([_node("p2a", number=2)], has_next=False)

    def responder(body):
        after = body["variables"]["after"]
        return httpx.Response(200, json=page2 if after == "CUR" else page1)
    mock_httpx(monkeypatch, responder)
    board = GitHubProjectsClient("t").fetch_board("owner", 1)
    assert [b.item_id for b in board] == ["p1a", "p2a"]
