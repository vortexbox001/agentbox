"""Run viewer route/render tests (spec 012). US1 Conversation tab here; US2/US3 extend this file."""
import json

import pytest


def write_run(runs_dir, agent, date, run_id, *, report=None, context=None, events=None,
              transcript=None):
    d = runs_dir / agent / date / run_id
    d.mkdir(parents=True)
    if report is not None:
        (d / "report.json").write_text(json.dumps(report))
    if context is not None:
        (d / "context.json").write_text(json.dumps(context))
    if events is not None:
        (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    if transcript is not None:
        (d / "transcript.jsonl").write_text(transcript)
    return d


def _events_with_tools():
    return [
        {"kind": "system", "ts": "t", "turn": 0, "text": "Session started."},
        {"kind": "user", "ts": "t", "turn": 0, "text": "Do the upgrade."},
        {"kind": "assistant", "ts": "t", "turn": 1, "text": "Checking outdated deps.",
         "tokens_in": 1200, "tokens_out": 300},
        {"kind": "tool_call", "ts": "t", "turn": 1, "tool": "Bash", "args": {"command": "npm outdated"}},
        {"kind": "tool_result", "ts": "t", "turn": 1, "result": "date-fns 2.29 -> 2.30"},
        {"kind": "tool_call", "ts": "t", "turn": 2, "tool": "Edit", "args": {"file_path": "package.json"}},
        {"kind": "tool_result", "ts": "t", "turn": 2, "result": "",
         "diff": "--- a/package.json\n+++ b/package.json\n-  \"date-fns\": \"2.29.3\",\n+  \"date-fns\": \"2.30.0\","},
        {"kind": "tool_call", "ts": "t", "turn": 3, "tool": "Bash", "args": {"command": "npm test"}},
        {"kind": "tool_result", "ts": "t", "turn": 3, "missing": True},
        {"kind": "final", "ts": "t", "turn": 3, "text": "Done.", "tokens_in": 8000, "tokens_out": 1500},
    ]


@pytest.mark.parametrize("harness", ["api", "claude-code", "codex", "pi"])
def test_conversation_renders_same_components_each_harness(settings, tmp_runs, client, harness):
    write_run(tmp_runs, harness, "2026-09-15", f"run-{harness}",
              report={"status": "ok", "tokens_in": 8000, "tokens_out": 1500, "turns": 3,
                      "cost_usd": None, "transcript_path": "x"},
              context={"harness": {"harness": harness}, "model": {"model": "m"}},
              events=_events_with_tools())
    html = client.get(f"/runs/run-{harness}").text
    # the same threaded shape for every harness, now with IN/OUT tool cards (spec 017 US2)
    assert "ax-timeline" in html
    assert "ax-entry" in html
    assert "ax-toolcard" in html
    assert "ax-toolcard-name" in html
    # a file edit renders as a diff in the OUT row (FR-026)
    assert "ax-diff-add" in html and "ax-diff-del" in html
    # a missing tool result is marked (failed marker + warning-colour OUT), not hidden (FR-027)
    assert "recorded as missing" in html
    assert "ax-io-body--missing" in html


def test_conversation_pruned_note(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "pruned",
              report={"status": "ok"}, context={"harness": {"harness": "api"}})  # no events.jsonl
    html = client.get("/runs/pruned").text
    assert "Conversation pruned" in html
    assert "ax-timeline" not in html


def test_events_api_returns_normalized_events(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "with-events",
              report={"status": "ok"}, context={}, events=_events_with_tools())
    r = client.get("/api/runs/with-events/events")
    assert r.status_code == 200
    events = r.json()["events"]
    assert [e["kind"] for e in events][:2] == ["system", "user"]


def test_events_api_404_for_unknown(settings, tmp_runs, client):
    assert client.get("/api/runs/nope/events").status_code == 404


# --- US2: Context tab -------------------------------------------------------

def _claude_context():
    return {
        "prompt": {"prompt_text": "Upgrade the deps.", "append_system_prompt": "Write to /output"},
        "model": {"model": "sonnet", "effort": "high", "fallback_model": None},
        "harness": {"harness": "claude-code", "image_ref": "agentbox/agent-claude:latest",
                    "image_digest": "sha256:abc"},
        "tools": {"allowed_tools": ["Read", "Write"], "permission_mode": "acceptEdits",
                  "mcp_servers": [{"name": "github", "tools": ["create_issue", "list_prs"]}]},
        "instruction_files": [{"path": "/workspace/CLAUDE.md", "contents": "PROJECT RULES: be careful"}],
        "runtime": {"env_names": ["TZ", "OPENAI_API_KEY"], "mounts": [
            {"source": "/data/ws", "target": "/workspace", "mode": "rw"}],
            "network": "agentnet", "working_dir": "/workspace"},
        "file_trees": {"workspace": [{"path": "a.py", "size": 12}], "output": []},
        "completeness": {"complete": False, "undisclosed": ["vendor base system prompt"],
                         "statement": "The claude-code vendor base system prompt is not disclosed."},
    }


def test_context_tab_renders_instruction_files_and_completeness(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "ctx",
              report={"status": "ok"}, context=_claude_context())
    html = client.get("/runs/ctx").text
    # full instruction-file contents shown (SC-008)
    assert "PROJECT RULES: be careful" in html
    assert "/workspace/CLAUDE.md" in html
    # completeness statement naming the vendor base prompt undisclosed
    assert "vendor base system prompt is not disclosed" in html
    # MCP servers + exposed tools
    assert "github" in html and "create_issue" in html


def test_context_tab_shows_env_names_only_and_flags_secret(settings, tmp_runs, client):
    write_run(tmp_runs, "hello", "2026-09-15", "ctx2",
              report={"status": "ok"}, context=_claude_context())
    html = client.get("/runs/ctx2").text
    assert "ax-env-pill" in html
    assert "OPENAI_API_KEY" in html and "TZ" in html
    # the secret-looking name is flagged, but no value is present anywhere (FR-015)
    assert "data-secret" in html


# --- US3: Runs list (disk-only, filters) ------------------------------------

@pytest.fixture
def three_runs(tmp_runs):
    write_run(tmp_runs, "hello", "2026-09-14", "r1",
              report={"status": "ok", "cost_usd": 0.01, "model": "cheap"},
              context={"model": {"model": "cheap"}, "harness": {"harness": "api"}})
    write_run(tmp_runs, "hello", "2026-09-15", "r2",
              report={"status": "failed", "error": "boom"},
              context={"model": {"model": "smart"}, "harness": {"harness": "claude-code"}})
    write_run(tmp_runs, "other", "2026-09-15", "r3",
              report={"status": "ok"}, context={"model": {"model": "smart"}})
    return tmp_runs


def test_runs_list_renders_from_disk(settings, three_runs, client):
    # No Dagster stub is installed — the page must render purely from disk (SC-007).
    html = client.get("/runs").text
    assert "ax-runs-table" in html or "ax-table" in html
    for rid in ("r1", "r2", "r3"):
        assert f"/runs/{rid}" in html


def test_runs_list_has_the_ten_columns_in_order(settings, three_runs, client):
    # FR-012: exactly ten columns, in order; FR-013: no Date/Time/Attempts.
    html = client.get("/runs").text
    order = ["Run", "Agent", "Model", "Target", "Launched by", "Checks", "Status",
             "Created", "Duration", "Cost"]
    positions = [html.index(f">{c}</th>") for c in order]
    assert positions == sorted(positions), "columns are not in the FR-012 order"
    for gone in ("Date", "Time", "Attempts"):
        assert f">{gone}</th>" not in html


def test_runs_list_filters_by_agent(settings, three_runs, client):
    html = client.get("/runs?agent=other").text
    assert "/runs/r3" in html
    assert "/runs/r1" not in html and "/runs/r2" not in html


def test_runs_list_ignores_removed_status_param_and_filters_by_date(settings, three_runs, client):
    # FR-007: the old Status dropdown query param is ignored (tabs replace it).
    html = client.get("/runs?status=failed").text
    for rid in ("r1", "r2", "r3"):
        assert f"/runs/{rid}" in html          # status= no longer filters anything out
    # The date range still filters (FR-010).
    html2 = client.get("/runs?date_from=2026-09-15&date_to=2026-09-15").text
    assert "/runs/r2" in html2 and "/runs/r3" in html2 and "/runs/r1" not in html2


def test_runs_list_has_no_status_dropdown(settings, three_runs, client):
    # FR-007: the Status <select> is gone; tabs partition instead.
    html = client.get("/runs").text
    assert 'name="status"' not in html
    assert "ax-tabs" in html and "ax-tab-count" in html


def test_api_runs_json(settings, three_runs, client):
    rows = client.get("/api/runs?agent=hello").json()["runs"]
    assert {r["run_id"] for r in rows} == {"r1", "r2"}


def test_context_tab_complete_for_pi(settings, tmp_runs, client):
    ctx = _claude_context()
    ctx["harness"]["harness"] = "pi"
    ctx["completeness"] = {"complete": True, "undisclosed": [], "statement": "Complete — pi adds no vendor prompt."}
    write_run(tmp_runs, "hello", "2026-09-15", "ctx-pi", report={"status": "ok"}, context=ctx)
    html = client.get("/runs/ctx-pi").text
    assert "Complete — pi adds no vendor prompt." in html


# ── spec 015: Runs overview enrichment + tabs + columns + pagination ────────────────────────

@pytest.fixture
def stub_run_status(monkeypatch):
    """Stub dagster.run_status so tests drive true status/target/launched-by/checks. Set
    ``box["payload"]`` to the enrichment shape before the request."""
    import dagster
    box = {"payload": {"reachable": True, "runs": {}}}

    async def fake(run_ids):
        return box["payload"]

    monkeypatch.setattr(dagster, "run_status", fake)
    return box


def _enrich(**runs):
    return {"reachable": True, "runs": runs}


# --- US1: truthful status + last-known fallback -----------------------------

def test_us1_dagster_failure_shows_failed_not_ok(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-15", "r1", report={"status": "ok"}, context={})
    stub_run_status["payload"] = _enrich(r1={"status": "FAILURE", "start_time": None,
        "end_time": None, "target": None, "launched_by": {"kind": "manual", "name": None},
        "checks": None})
    html = client.get("/runs").text
    assert 'data-status="failure"' in html and ">failed<" in html
    assert ">ok<" not in html                      # the everything-maps-to-ok bug is dead


def test_us1_states_map_to_tabs(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "run-x", "2026-09-15", "x", report={"status": "running"}, context={})
    write_run(tmp_runs, "run-q", "2026-09-15", "q", report={"status": "unknown"}, context={})
    stub_run_status["payload"] = _enrich(
        x={"status": "STARTED", "start_time": 1.0, "end_time": None, "target": None,
           "launched_by": {"kind": "manual", "name": None}, "checks": None},
        q={"status": "QUEUED", "start_time": None, "end_time": None, "target": None,
           "launched_by": {"kind": "manual", "name": None}, "checks": None})
    html = client.get("/runs").text
    assert ">in progress<" in html and ">queued<" in html


def test_us1_page_loads_last_known_when_dagster_down(settings, three_runs, client, stub_run_status):
    stub_run_status["payload"] = {"reachable": False, "runs": {}}
    resp = client.get("/runs")
    assert resp.status_code == 200
    # Every row is marked last-known and still shows its local status.
    assert "last-known" in resp.text
    for rid in ("r1", "r2", "r3"):
        assert f"/runs/{rid}" in resp.text


def test_us1_dagster_wins_over_report(settings, tmp_runs, client, stub_run_status):
    # report says ok, Dagster says FAILURE while reachable → failed (FR-003).
    write_run(tmp_runs, "hello", "2026-09-15", "r1", report={"status": "ok"}, context={})
    stub_run_status["payload"] = _enrich(r1={"status": "FAILURE", "start_time": None,
        "end_time": None, "target": None, "launched_by": {"kind": "manual", "name": None},
        "checks": None})
    html = client.get("/runs").text
    assert ">failed<" in html
    assert "last-known" not in html                # reachable + has record → not last-known


# --- US2: tabs + filter + URL round-trip ------------------------------------

@pytest.fixture
def mixed_runs(tmp_runs):
    write_run(tmp_runs, "alpha", "2026-09-14", "ok1", report={"status": "ok"}, context={})
    write_run(tmp_runs, "beta", "2026-09-15", "fail1", report={"status": "failed"}, context={})
    write_run(tmp_runs, "beta", "2026-09-16", "run1", report={"status": "running"}, context={})
    return tmp_runs


def test_us2_failed_tab_shows_only_failed(settings, mixed_runs, client, stub_run_status):
    stub_run_status["payload"] = _enrich(
        ok1={"status": "SUCCESS", "start_time": 1.0, "end_time": 2.0, "target": None,
             "launched_by": {"kind": "manual", "name": None}, "checks": None},
        fail1={"status": "FAILURE", "start_time": 1.0, "end_time": 2.0, "target": None,
               "launched_by": {"kind": "manual", "name": None}, "checks": None},
        run1={"status": "STARTED", "start_time": 1.0, "end_time": None, "target": None,
              "launched_by": {"kind": "manual", "name": None}, "checks": None})
    html = client.get("/runs?tab=failed").text
    assert "/runs/fail1" in html
    assert "/runs/ok1" not in html and "/runs/run1" not in html


def test_us2_counts_cover_whole_filtered_set(settings, mixed_runs, client, stub_run_status):
    stub_run_status["payload"] = _enrich(
        ok1={"status": "SUCCESS", "start_time": 1.0, "end_time": 2.0, "target": None,
             "launched_by": {"kind": "manual", "name": None}, "checks": None},
        fail1={"status": "FAILURE", "start_time": 1.0, "end_time": 2.0, "target": None,
               "launched_by": {"kind": "manual", "name": None}, "checks": None},
        run1={"status": "STARTED", "start_time": 1.0, "end_time": None, "target": None,
              "launched_by": {"kind": "manual", "name": None}, "checks": None})
    data = client.get("/api/runs?tab=failed").json()
    assert data["counts"] == {"all": 3, "in_progress": 1, "succeeded": 1, "failed": 1}


def test_us2_text_filter_narrows_by_agent_model_runid(settings, three_runs, client, stub_run_status):
    # q matches agent/model/run id (target absent here). "other" is the r3 agent name.
    html = client.get("/runs?q=other").text
    assert "/runs/r3" in html and "/runs/r1" not in html


def test_us2_url_state_round_trips(settings, three_runs, client, stub_run_status):
    url = "/runs?tab=succeeded&q=hello&agent=hello&date_from=2026-09-14&date_to=2026-09-15&page=1"
    assert client.get(url).status_code == 200


# --- US3: columns + formatting ----------------------------------------------

def test_us3_created_label_and_cost_and_agent_link(settings, tmp_runs, client, stub_run_status):
    import os
    from datetime import datetime
    d = write_run(tmp_runs, "hello", "2026-09-17", "r1",
                  report={"status": "ok", "cost_usd": 0.0, "model": "cheap"},
                  context={"model": {"model": "cheap"}})
    # Pin the dir mtime to 13:15 local on 2026-09-17 so Created reads the R7 label.
    epoch = datetime(2026, 9, 17, 13, 15, 0).timestamp()
    os.utime(d, (epoch, epoch))
    stub_run_status["payload"] = _enrich(r1={"status": "SUCCESS", "start_time": epoch,
        "end_time": epoch + 63, "target": "refined/daily",
        "launched_by": {"kind": "schedule", "name": "sched_hello"}, "checks": None})
    html = client.get("/runs").text
    assert datetime.fromtimestamp(epoch).strftime("%b %-d, %-I:%M %p") in html  # e.g. Sep 17, 1:15 PM
    assert "$0.0000" in html                        # a real 0 shows a value, not em-dash (FR-019)
    assert '<a class="ax-mono" href="/agents/hello">' in html   # agent links to /agents/<agent>
    assert "refined/daily" in html                  # Target from enrichment
    assert "sched_hello" in html                    # Launched by from enrichment


def test_us3_unknown_cost_and_missing_enrichment_are_em_dashes(settings, tmp_runs, client,
                                                                stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-15", "r1",
              report={"status": "ok"}, context={})   # no cost_usd, no model
    stub_run_status["payload"] = _enrich(r1={"status": "SUCCESS", "start_time": None,
        "end_time": None, "target": None, "launched_by": {"kind": "manual", "name": None},
        "checks": None})
    row = client.get("/api/runs").json()["runs"][0]
    assert row["cost_usd"] is None                  # unknown cost → em-dash in the cell (FR-019)
    assert row["target"] == "—" and row["model"] is None
    assert "—" in client.get("/runs").text          # rendered as the em-dash placeholder


def test_us3_in_progress_duration_shows_elapsed(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-15", "r1", report={"status": "running"}, context={})
    stub_run_status["payload"] = _enrich(r1={"status": "STARTED", "start_time": 1000.0,
        "end_time": None, "target": None, "launched_by": {"kind": "manual", "name": None},
        "checks": None})
    data = client.get("/api/runs").json()
    row = data["runs"][0]
    assert row["status"] == "in_progress"
    assert row["duration"] is not None              # elapsed-so-far (now − start)


# --- US4: Dagster deep link -------------------------------------------------

def test_us4_dagster_link_present_when_configured(settings, three_runs, client, stub_run_status):
    html = client.get("/runs").text
    assert 'class="ax-run-dagster-link"' in html
    assert 'target="_blank"' in html
    assert "/runs/r1" in html                       # the id links to the AgentBox run page
    assert 'href="http://testserver:3000/runs/r1"' in html   # icon → {dagster_url}/runs/{id}


def test_us4_no_dagster_link_when_not_configured(settings, three_runs, client, stub_run_status,
                                                 monkeypatch):
    import main
    monkeypatch.setattr(main, "public_dagster_url", lambda request: "")
    html = client.get("/runs").text
    assert "ax-run-dagster-link" not in html
    assert "/runs/r1" in html                       # the run id still links to the AgentBox page


# --- US5: pagination --------------------------------------------------------

@pytest.fixture
def many_runs(tmp_runs):
    for i in range(31):
        write_run(tmp_runs, "hello", "2026-09-15", f"r{i:02d}",
                  report={"status": "ok"}, context={})
    return tmp_runs


def test_us5_page_one_has_thirty_and_pagination(settings, many_runs, client, stub_run_status):
    data = client.get("/api/runs").json()
    assert len(data["runs"]) == 30 and data["pages"] == 2 and data["page"] == 1
    html = client.get("/runs").text
    assert "ax-pagination" in html


def test_us5_page_two_has_remainder(settings, many_runs, client, stub_run_status):
    data = client.get("/api/runs?page=2").json()
    assert len(data["runs"]) == 1 and data["page"] == 2


def test_us5_page_past_end_clamps(settings, many_runs, client, stub_run_status):
    data = client.get("/api/runs?page=99").json()
    assert data["page"] == data["pages"] == 2


def test_us5_badges_reflect_whole_filtered_set(settings, many_runs, client, stub_run_status):
    data = client.get("/api/runs?page=2").json()
    assert data["counts"]["all"] == 31             # independent of the current page


# --- FR-035: enrichment cap note (T045) -------------------------------------

def test_fr035_cap_note_and_older_rows_last_known(settings, tmp_runs, client, stub_run_status,
                                                  monkeypatch):
    import dagster
    monkeypatch.setattr(dagster, "RUNS_STATUS_CAP", 3)   # small cap so the test stays fast
    for i in range(5):
        write_run(tmp_runs, "hello", "2026-09-15", f"r{i:02d}",
                  report={"status": "ok"}, context={})
    # Enrichment only covers the newest 3 (the caller caps the id list); the payload here
    # returns those, and older rows must stay present + last-known, never dropped.
    stub_run_status["payload"] = _enrich(**{f"r0{i}": {"status": "SUCCESS", "start_time": 1.0,
        "end_time": 2.0, "target": None, "launched_by": {"kind": "manual", "name": None},
        "checks": None} for i in (2, 3, 4)})
    html = client.get("/runs?tab=all").text
    assert "most recent 3 runs" in html            # the cap note renders (FR-035)
    for i in range(5):
        assert f"/runs/r0{i}" in html              # older rows present, not truncated
    assert "last-known" in html                    # rows beyond the cap are last-known


# ── spec 016: a board-launched run links the issue on the run page (FR-026) ──

def test_run_page_links_issue_number_to_url(settings, tmp_runs, client):
    write_run(tmp_runs, "board-agent", "2026-09-17", "board-run",
              report={"status": "ok"},
              context={"issue": {"number": 42, "repo": "vortexbox001/agentbox",
                                 "url": "https://github.com/vortexbox001/agentbox/issues/42",
                                 "title": "Do the thing", "feature_key": "042-do-the-thing"}})
    html = client.get("/runs/board-run").text
    assert 'href="https://github.com/vortexbox001/agentbox/issues/42"' in html
    assert "#42" in html
    assert "042-do-the-thing" in html


# ══ spec 017: run-detail five-section layout ═══════════════════════════════════

def _rich_events():
    return [
        {"kind": "system", "text": "Session started."},
        {"kind": "user", "text": "Do the upgrade."},
        {"kind": "assistant", "text": "Working.", "turn": 1},
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "npm test"}},
        {"kind": "tool_result", "result": "l1\nl2\nl3\nl4\nl5\nl6"},
        {"kind": "tool_call", "tool": "Edit", "args": {"file_path": "package.json"}},
        {"kind": "tool_result", "result": "", "diff": "+new\n-old"},
        {"kind": "final", "text": "All done.", "turn": 2},
    ]


_FULL_NOTES = ("## Summary\n\nThe upgrade **passed** the `gate`.\n\n- one\n- two\n\n"
               "See https://example.com/x")


def _seed_full_run(tmp_runs, notes=_FULL_NOTES):
    return write_run(tmp_runs, "hello", "2026-09-18", "full",
                     report={"status": "ok", "turns": 2, "files_written": 0, "notes": notes},
                     context=_claude_context(), events=_rich_events())


# --- US1: sections, order, defaults, notes -----------------------------------

def test_017_five_sections_in_order_with_defaults(settings, tmp_runs, client, stub_run_status):
    import re
    _seed_full_run(tmp_runs)
    html = client.get("/runs/full").text
    order = ["summary", "output", "checks", "context", "transcript"]
    positions = [html.index(f'data-section-id="{s}"') for s in order]
    assert positions == sorted(positions), "sections not in the FR-001 order"
    assert html.count('class="ax-section"') == 5     # exactly five sections
    for sid, collapsed in [("summary", False), ("output", False), ("checks", False),
                           ("context", True), ("transcript", False)]:
        m = re.search(rf'data-section-id="{sid}"([^>]*)>', html)
        assert ("data-collapsed" in m.group(1)) is collapsed, f"{sid} default open/closed wrong"
    # keyboard-operable disclosure + note wiring present
    assert "data-section-toggle" in html and "ax-section-note" in html
    # header + six-stat strip unchanged
    assert "ax-run-crumb" in html and "ax-run-stats" in html


def test_017_section_storage_key_is_shared_not_per_run():
    # FR-004: the persistence key is a single shared key, not keyed per run id.
    import os
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "static", "run-detail.js"), encoding="utf-8").read()
    assert '"agentbox.runDetail.sections"' in js
    assert ".sections." not in js.replace('"agentbox.runDetail.sections"', "")  # no per-run suffix


# --- US3: Summary ------------------------------------------------------------

def test_017_summary_renders_markdown_no_raw_markup(settings, tmp_runs, client, stub_run_status):
    _seed_full_run(tmp_runs)
    html = client.get("/runs/full").text
    assert "ax-summary-h" in html                    # ## Summary → uppercase label
    assert "<strong>passed</strong>" in html
    assert "<code>gate</code>" in html
    assert "ax-summary-list" in html
    assert "## Summary" not in html and "**passed**" not in html   # no raw markup (SC-003)
    assert "ax-report-notes" not in html             # rail no longer carries the notes (US3-AC4)


def test_017_summary_final_event_fallback(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-18", "noNotes",
              report={"status": "ok", "turns": 1}, context={}, events=_rich_events())
    html = client.get("/runs/noNotes").text
    assert "All done." in html                        # final event text is the Summary source
    assert "final message from the agent" in html


def test_017_summary_foot_fallback_when_no_message(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-18", "legacyish",
              report={"status": "failed", "turns": 0, "files_written": 0}, context={})
    html = client.get("/runs/legacyish").text
    assert "No final message was captured." in html
    assert "failed · 0 turns · 0 files written" in html


def test_017_summary_escapes_raw_html(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-18", "xss",
              report={"status": "ok", "notes": "<script>alert(1)</script>\n\n| a | b |"},
              context={})
    html = client.get("/runs/xss").text
    assert "<script>alert(1)</script>" not in html    # escaped, never live (SC-003)
    assert "&lt;script&gt;" in html


# --- US4: Output + produced elsewhere ---------------------------------------

def test_017_output_produced_elsewhere_when_no_files(settings, tmp_runs, client, stub_run_status):
    events = [
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "gh pr create"}},
        {"kind": "tool_result", "result": "Created https://github.com/octo/repo/pull/7"},
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "git push"}},
        {"kind": "tool_result", "result": "[main 1a2b3c4] done"},
    ]
    write_run(tmp_runs, "hello", "2026-09-18", "prrun",
              report={"status": "ok"}, context=_claude_context(), events=events)
    html = client.get("/runs/prrun").text
    assert "No output artifacts" in html
    assert "ax-produced-row" in html
    assert "Pull request" in html and "Commit" in html and "1a2b3c4" in html
    assert "0 files · 1 pull request" in html         # the note (FR-014)


# --- US5: Checks -------------------------------------------------------------

def test_017_checks_render_with_outcome_note(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-18", "chk", report={"status": "ok"},
              context=_claude_context())
    stub_run_status["payload"] = {"reachable": True, "runs": {"chk": {"checks": [
        {"name": "freshness", "status": "pass", "detail": "ok", "recorded": "Sep 18, 1:15 PM"},
        {"name": "blocking", "status": "fail-blocking", "detail": "missing", "recorded": "—"},
        {"name": "warned", "status": "warn", "detail": "—", "recorded": "—"},
        {"name": "skipped", "status": "not-run", "detail": "—", "recorded": "—"},
    ]}}}
    html = client.get("/runs/chk").text
    assert "ax-checkrow" in html
    assert "freshness" in html and "ax-result--pass" in html and "ax-result--fail" in html
    assert "1 passed · 1 warning · 1 failed · 1 not run" in html


def test_017_checks_empty_when_dagster_unreachable(settings, tmp_runs, client, stub_run_status):
    write_run(tmp_runs, "hello", "2026-09-18", "nochk", report={"status": "ok"},
              context=_claude_context())
    stub_run_status["payload"] = {"reachable": False, "runs": {}}
    html = client.get("/runs/nochk").text
    assert "No checks were configured for this agent." in html


# --- US6: Context ------------------------------------------------------------

def test_017_context_section_collapsed_with_note_and_rail_order(settings, tmp_runs, client,
                                                                stub_run_status):
    import re
    write_run(tmp_runs, "hello", "2026-09-18", "ctxs", report={"status": "ok"},
              context=_claude_context())
    html = client.get("/runs/ctxs").text
    m = re.search(r'data-section-id="context"([^>]*)>', html)
    assert "data-collapsed" in m.group(1)             # collapsed by default (FR-002/FR-019)
    assert "PROJECT RULES: be careful" in html        # context card content nested verbatim
    assert "prompt · appended · 1 instruction file" in html   # note (FR-020)
    order = [">Configuration", ">Container", ">Inputs", ">Completeness", ">Usage"]
    positions = [html.index(o) for o in order]
    assert positions == sorted(positions)             # rail order preserved (US6-AC3)


# --- US7: Transcript search + relocation + dedup + foot ----------------------

def test_017_transcript_controls_and_foot(settings, tmp_runs, client, stub_run_status):
    _seed_full_run(tmp_runs)
    html = client.get("/runs/full").text
    ti = html.index('data-section-id="transcript"')
    assert html.index("ax-conv-count", ti) > ti       # match count in the transcript header
    assert html.index("data-segmented", ti) > ti      # relocated Readable/Raw-log toggle
    assert html.index('id="ax-conv-search"', ti) > ti # relocated search box
    assert "npm test" in html                         # IN/OUT text present → searchable
    assert "ok · 2 turns · 0 files written · 2 tool calls" in html   # four-field foot (FR-033)


def test_017_transcript_dedups_final_result(settings, tmp_runs, client, stub_run_status):
    events = [
        {"kind": "user", "text": "go"},
        {"kind": "assistant", "text": "The answer is 42."},
        {"kind": "final", "text": "The answer is 42."},
    ]
    # report notes distinct from the final so the Summary section is not itself a second copy.
    write_run(tmp_runs, "hello", "2026-09-18", "dedup",
              report={"status": "ok", "notes": "A short recap."}, context={}, events=events)
    html = client.get("/runs/dedup").text
    assert html.count("The answer is 42.") == 1       # transcript renders it once (FR-032)
    assert ">Result<" in html


# --- FR-035: presentation and read-path only (scope guard, T059) -------------

def test_017_read_path_only_no_writes_no_schema_bump(settings, tmp_runs, client, stub_run_status):
    import os
    import schema
    assert schema.SCHEMA_VERSION == 8            # unchanged by this presentation feature (FR-035)
    d = _seed_full_run(tmp_runs)
    before = {p: os.path.getmtime(d / p) for p in os.listdir(d)}
    assert client.get("/runs/full").status_code == 200
    after = {p: os.path.getmtime(d / p) for p in os.listdir(d)}
    assert before == after                       # rendering wrote nothing to the run record
    assert set(os.listdir(d)) == {"report.json", "context.json", "events.jsonl"}  # no new files
    reqs = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "requirements.txt"), encoding="utf-8").read()
    assert "markdown" not in reqs.lower()        # the FR-007 renderer added no dependency
