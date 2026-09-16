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
