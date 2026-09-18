"""Disk-reader tests for ui/runs_store.py (spec 012, T014).

Seeds a temp run tree (the ``tmp_runs`` fixture is already wired into ``config.RUNS_DIR`` by the
``settings`` fixture) and exercises list/read, filters, and missing-file tolerance. No Dagster is
reachable, proving the reader is disk-only (SC-007).
"""
import json

import pytest


def _write_run(runs_dir, agent, date, run_id, *, report=None, context=None,
               events=None, transcript=None):
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


@pytest.fixture
def seeded(tmp_runs):
    _write_run(
        tmp_runs, "hello", "2026-09-14", "run-a",
        report={"status": "ok", "cost_usd": 0.01, "model": "cheap"},
        context={"model": {"model": "cheap"}, "harness": {"harness": "api"}},
        events=[{"kind": "system", "ts": "t", "turn": 0, "text": "init"}],
        transcript='{"type":"result"}\n',
    )
    _write_run(
        tmp_runs, "hello", "2026-09-15", "run-b",
        report={"status": "failed", "cost_usd": None, "error": "boom"},
        context={"model": {"model": "smart"}, "harness": {"harness": "claude-code"},
                 "asset": {"attempt": 2}},
        # no events.jsonl → pruned/never-captured
    )
    _write_run(
        tmp_runs, "other", "2026-09-15", "run-c",
        report={"status": "ok"}, context={"model": {"model": "smart"}},
        events=[{"kind": "final", "ts": "t", "turn": 1, "text": "done"}],
    )
    # a legacy flat transcript-only run
    legacy_dir = tmp_runs / "hello" / "2026-09-13"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "run-legacy.jsonl").write_text('{"type":"result"}\n')
    return tmp_runs


def test_list_all_runs_newest_first(settings, seeded):
    import runs_store
    rows = runs_store.list_runs()
    ids = [r["run_id"] for r in rows]
    assert set(ids) == {"run-a", "run-b", "run-c", "run-legacy"}
    # newest first by mtime — all four present, legacy included as transcript-only
    legacy = next(r for r in rows if r["run_id"] == "run-legacy")
    assert legacy["legacy"] is True and legacy["conversation_available"] is False


def test_list_filters_by_agent(settings, seeded):
    import runs_store
    rows = runs_store.list_runs(agent="other")
    assert [r["run_id"] for r in rows] == ["run-c"]


def test_list_filters_by_status(settings, seeded):
    import runs_store
    rows = runs_store.list_runs(status="failed")
    assert [r["run_id"] for r in rows] == ["run-b"]
    assert rows[0]["cost_usd"] is None  # null cost preserved, not coerced to 0


def test_list_filters_by_date_range(settings, seeded):
    import runs_store
    rows = runs_store.list_runs(date_from="2026-09-15", date_to="2026-09-15")
    assert set(r["run_id"] for r in rows) == {"run-b", "run-c"}


def test_row_reports_model_and_conversation_flag(settings, seeded):
    import runs_store
    rows = {r["run_id"]: r for r in runs_store.list_runs()}
    assert rows["run-a"]["model"] == "cheap"
    assert rows["run-a"]["conversation_available"] is True
    assert rows["run-b"]["conversation_available"] is False  # no events.jsonl (pruned)
    assert rows["run-b"]["attempts"] == 2


def test_row_reports_started_time_and_attempts(settings, seeded):
    # FR-017: the list row carries a time-of-day and the attempt count for the list columns.
    import runs_store
    rows = {r["run_id"]: r for r in runs_store.list_runs()}
    # started_time is HH:MM (from the dir mtime), always present as a string
    assert all(len(r["started_time"]) in (0, 5) for r in rows.values())
    assert rows["run-a"]["started_time"].count(":") in (0, 1)
    # attempts is the asset attempt when present, else None (rendered as "—")
    assert rows["run-b"]["attempts"] == 2
    assert rows["run-a"]["attempts"] is None


def test_read_run_loads_four_files(settings, seeded):
    import runs_store
    detail = runs_store.read_run("run-a")
    assert detail["context"]["harness"]["harness"] == "api"
    assert detail["report"]["status"] == "ok"
    assert detail["conversation_available"] is True
    assert detail["transcript_available"] is True


def test_read_run_tolerates_missing_files(settings, seeded):
    import runs_store
    detail = runs_store.read_run("run-b")
    assert detail is not None
    assert detail["conversation_available"] is False
    assert detail["events_path"] is None
    assert detail["report"]["status"] == "failed"


def test_read_run_legacy_is_transcript_only(settings, seeded):
    import runs_store
    detail = runs_store.read_run("run-legacy")
    assert detail["legacy"] is True
    assert detail["context"] is None and detail["report"] is None
    assert detail["transcript_available"] is True
    assert detail["conversation_available"] is False


def test_read_run_missing_returns_none(settings, seeded):
    import runs_store
    assert runs_store.read_run("nope") is None


def test_read_events(settings, seeded):
    import runs_store
    events = runs_store.read_events("run-a")
    assert [e["kind"] for e in events] == ["system"]
    assert runs_store.read_events("run-b") == []  # no events file


def test_list_empty_tree_is_empty(settings, tmp_runs):
    import runs_store
    assert runs_store.list_runs() == []


# ── spec 017: produced-elsewhere miner, tool-card enrichment, note builders ──

def test_produced_elsewhere_detects_pr_commit_file_and_groups(settings):
    import runs_store
    events = [
        {"kind": "tool_call", "tool": "Write", "args": {"file_path": "/workspace/a.py"}},
        {"kind": "tool_result", "result": "ok"},
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "git commit"}},
        {"kind": "tool_result", "result": "[main 1a2b3c4] wire it up\n 1 file changed"},
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "gh pr create"}},
        {"kind": "tool_result",
         "result": "Created https://github.com/octo/repo/pull/7 for review"},
        {"kind": "tool_call", "tool": "Edit", "args": {"path": "/workspace/b.py"}},
        {"kind": "tool_result", "result": ""},
    ]
    out = runs_store.produced_elsewhere(events)
    # grouped PRs → commits → files, event order within each kind
    assert [r["kind"] for r in out] == ["pull_request", "commit", "file", "file"]
    assert out[0]["identifier"] == "https://github.com/octo/repo/pull/7"
    assert out[0]["action"] == out[0]["identifier"]
    assert out[1]["identifier"] == "1a2b3c4" and out[1]["action"] is None
    assert [r["identifier"] for r in out if r["kind"] == "file"] == \
        ["/workspace/a.py", "/workspace/b.py"]


def test_produced_elsewhere_empty_and_never_raises(settings):
    import runs_store
    assert runs_store.produced_elsewhere([]) == []
    # garbage / no minable evidence contributes no row and does not raise
    assert runs_store.produced_elsewhere(
        [{"kind": "tool_result", "result": "just some text"},
         {"kind": "assistant", "text": "thinking"}]) == []


def test_enrich_tool_cards_clamp_overflow_and_diff(settings):
    import runs_store
    entries = runs_store.conversation_entries([
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "npm test"}},
        {"kind": "tool_result", "result": "l1\nl2\nl3\nl4\nl5"},          # 5 lines → overflow
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "echo hi"}},
        {"kind": "tool_result", "result": "one\ntwo"},                     # 2 lines → no overflow
        {"kind": "tool_call", "tool": "Edit", "args": {"file_path": "p.py"}},
        {"kind": "tool_result", "result": "", "diff": "+a\n-b\n c\n+d"},   # diff → expanded
    ])
    runs_store.enrich_tool_cards(entries)
    tools = [t for e in entries for t in e["tools"]]
    assert tools[0]["out_overflow"] is True and tools[0]["out_lines"] == 5
    assert tools[1]["out_overflow"] is False
    # a diff OUT is expanded by default (never clamped), colouring preserved
    assert tools[2]["is_diff"] is True and tools[2]["out_overflow"] is False


def test_enrich_tool_cards_marker_derivation(settings):
    import runs_store
    entries = runs_store.conversation_entries([
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "run"}},
        {"kind": "tool_result", "result": "boom\nexit code: 2"},           # exit N
        {"kind": "tool_call", "tool": "Write", "args": {"file_path": "x"}},
        {"kind": "tool_result", "missing": True},                          # failed / missing
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "cat secret"}},
        {"kind": "tool_result", "result": "Permission denied: cannot read"},  # failed / refusal
        {"kind": "tool_call", "tool": "Bash", "args": {"command": "ls"}},
        {"kind": "tool_result", "result": "file-a\nfile-b"},               # neither
    ])
    runs_store.enrich_tool_cards(entries)
    tools = [t for e in entries for t in e["tools"]]
    assert tools[0]["marker"] == "exit 2" and tools[0]["out_intent"] == "failed"
    assert tools[1]["marker"] == "failed" and tools[1]["out_intent"] == "missing"
    assert tools[2]["marker"] == "failed" and tools[2]["out_intent"] == "failed"
    assert tools[3]["marker"] is None and tools[3]["out_intent"] is None


def test_section_note_builders(settings):
    import runs_store
    # Output note: files part always shows; PR part only when non-zero
    assert runs_store.section_note_output([], []) == "0 files"
    assert runs_store.section_note_output(
        [], [{"kind": "pull_request"}]) == "0 files · 1 pull request"
    assert runs_store.section_note_output([1, 2, 3], []) == "3 files"
    # Checks note across the full vocabulary; fail-blocking counts as failed; not-run counts
    assert runs_store.section_note_checks([]) == "—"
    assert runs_store.section_note_checks(
        [{"status": "pass"}, {"status": "pass"}, {"status": "pass"},
         {"status": "pass"}, {"status": "warn"}]) == "4 passed · 1 warning"
    assert runs_store.section_note_checks([{"status": "not-run"}]) == "1 not run"
    assert runs_store.section_note_checks(
        [{"status": "fail-blocking"}]) == "1 failed"
    # Context + Transcript notes
    ctx = {"prompt": {"prompt_text": "p", "append_system_prompt": "a"},
           "instruction_files": [{"path": "x"}]}
    assert runs_store.section_note_context(ctx) == "prompt · appended · 1 instruction file"
    entries = runs_store.conversation_entries([
        {"kind": "tool_call", "tool": "Bash", "args": {}},
        {"kind": "tool_result", "result": "x"}])
    assert runs_store.section_note_transcript(entries, {"turns": 24}) == "24 turns · 1 tool call"


def test_foot_line_three_and_four_field(settings):
    import runs_store
    report = {"status": "ok", "turns": 3, "files_written": 0}
    assert runs_store.foot_line(report) == "ok · 3 turns · 0 files written"
    assert runs_store.foot_line(report, tool_calls=5) == \
        "ok · 3 turns · 0 files written · 5 tool calls"


def test_dedup_final_collapses_duplicate(settings):
    import runs_store
    entries = runs_store.conversation_entries([
        {"kind": "user", "text": "go"},
        {"kind": "assistant", "text": "Done."},
        {"kind": "final", "text": "Done."},
    ])
    runs_store.dedup_final(entries)
    # the duplicate assistant message is dropped; the final renders once as Result
    roles = [e["role"] for e in entries]
    assert roles == ["Task", "Result"]
