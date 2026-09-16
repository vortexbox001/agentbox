"""Run-retention prune tests (spec 012, T064 — contracts/settings.md, FR-027)."""
import datetime
import json
import os

import pytest

import prune


def _seed_run(root, agent, date, run_id):
    d = os.path.join(root, agent, date, run_id)
    os.makedirs(d)
    for name, payload in (("events.jsonl", '{"kind":"system"}\n'),
                          ("transcript.jsonl", '{"type":"result"}\n'),
                          ("context.json", json.dumps({"harness": {"harness": "api"}})),
                          ("report.json", json.dumps({"status": "ok"}))):
        with open(os.path.join(d, name), "w") as f:
            f.write(payload)
    return d


def test_prune_removes_only_events_and_transcript(tmp_path):
    root = tmp_path / "runs"
    today = datetime.date(2026, 9, 15)
    old = _seed_run(str(root), "hello", "2026-09-12", "old-run")   # 3 days ago
    recent = _seed_run(str(root), "hello", "2026-09-15", "new-run")  # today
    result = prune.prune_runs({"mode": "prune_after_days", "days": 1}, now=today, runs_root=str(root))
    assert result["pruned"] == 1 and result["files_removed"] == 2
    # the old run keeps report/context/output; events+transcript are gone
    assert not os.path.exists(os.path.join(old, "events.jsonl"))
    assert not os.path.exists(os.path.join(old, "transcript.jsonl"))
    assert os.path.isfile(os.path.join(old, "report.json"))
    assert os.path.isfile(os.path.join(old, "context.json"))
    # the recent run is untouched (within the retention window)
    assert os.path.isfile(os.path.join(recent, "events.jsonl"))
    assert os.path.isfile(os.path.join(recent, "transcript.jsonl"))


def test_keep_forever_is_a_noop(tmp_path):
    root = tmp_path / "runs"
    old = _seed_run(str(root), "hello", "2026-01-01", "run")
    result = prune.prune_runs({"mode": "keep_forever", "days": None},
                              now=datetime.date(2026, 9, 15), runs_root=str(root))
    assert result["skipped"] is True and result["pruned"] == 0
    assert os.path.isfile(os.path.join(old, "events.jsonl"))


def test_load_retention_reads_settings(tmp_path):
    sf = tmp_path / "settings.yaml"
    sf.write_text("retention:\n  mode: prune_after_days\n  days: 7\n")
    policy = prune.load_retention(str(sf))
    assert policy == {"mode": "prune_after_days", "days": 7}


def test_load_retention_defaults_when_absent(tmp_path):
    policy = prune.load_retention(str(tmp_path / "missing.yaml"))
    assert policy == {"mode": "keep_forever", "days": None}


def test_load_retention_ignores_invalid_days(tmp_path):
    sf = tmp_path / "settings.yaml"
    sf.write_text("retention:\n  mode: prune_after_days\n  days: 0\n")
    assert prune.load_retention(str(sf)) == {"mode": "keep_forever", "days": None}
