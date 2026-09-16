"""Tests for lib/agent_events.py (spec 012, T007).

Schema round-trip, kind coverage, and the null-vs-0 numeric rule. The schema check is
dependency-free (no jsonschema) — it validates a produced event against the required keys,
the kind enum, and the per-kind conditionals in ``normalized-event.schema.json``.
"""
import json
from pathlib import Path

import pytest

IMAGES_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    IMAGES_DIR.parent
    / "specs" / "012-run-transparency" / "contracts" / "normalized-event.schema.json"
)


@pytest.fixture
def events_mod():
    # images/ is on sys.path (conftest), so this resolves exactly as `import lib.agent_events`
    # does inside the container — and registers the module so @dataclass can find its namespace.
    import lib.agent_events as mod
    return mod


def _assert_event_valid(evt: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    for req in schema["required"]:
        assert req in evt, f"missing required key {req}"
    assert evt["kind"] in schema["properties"]["kind"]["enum"], evt["kind"]
    assert isinstance(evt["turn"], int) and evt["turn"] >= 0
    assert isinstance(evt["ts"], str) and evt["ts"]
    if evt["kind"] == "tool_call":
        assert "tool" in evt and "args" in evt
        assert isinstance(evt["args"], dict)
    if evt["kind"] in ("system", "user", "assistant", "final", "error"):
        assert "text" in evt and isinstance(evt["text"], str)
    # numeric fields, when present, are int/number or null (never bool)
    for k in ("tokens_in", "tokens_out"):
        if k in evt and evt[k] is not None:
            assert isinstance(evt[k], int) and not isinstance(evt[k], bool)
    if "cost_usd" in evt and evt["cost_usd"] is not None:
        assert isinstance(evt["cost_usd"], (int, float)) and not isinstance(evt["cost_usd"], bool)


def test_every_kind_serializes_valid(events_mod):
    E = events_mod.NormalizedEvent
    samples = [
        E(kind="system", turn=0, text="init"),
        E(kind="user", turn=0, text="do the thing"),
        E(kind="assistant", turn=1, text="on it", tokens_in=100, tokens_out=20),
        E(kind="tool_call", turn=1, tool="Read", args={"file_path": "x.py"}),
        E(kind="tool_result", turn=1, result="contents"),
        E(kind="tool_result", turn=2, result="", diff="--- a\n+++ b\n-old\n+new"),
        E(kind="tool_result", turn=3, missing=True),
        E(kind="final", turn=4, text="done", tokens_in=8000, tokens_out=1500, cost_usd=0.02),
        E(kind="error", turn=4, text="boom"),
    ]
    kinds = set()
    for ev in samples:
        d = ev.to_dict()
        _assert_event_valid(d)
        kinds.add(d["kind"])
    assert kinds == set(events_mod.KINDS)


def test_tool_result_missing_and_diff(events_mod):
    E = events_mod.NormalizedEvent
    missing = E(kind="tool_result", turn=1, missing=True).to_dict()
    assert missing["missing"] is True
    # a non-missing result never carries the missing flag (default false → omitted)
    ok = E(kind="tool_result", turn=1, result="ok").to_dict()
    assert "missing" not in ok
    diff = E(kind="tool_result", turn=1, result="", diff="--- a\n+++ b").to_dict()
    assert diff["diff"].startswith("--- a")


def test_null_vs_zero_numeric_rule(events_mod):
    E = events_mod.NormalizedEvent
    zero = E(kind="assistant", turn=1, text="x", tokens_in=0, cost_usd=0.0).to_dict()
    # a real 0 survives, distinct from "not reported"
    assert zero["tokens_in"] == 0
    assert zero["cost_usd"] == 0.0
    not_reported = E(kind="assistant", turn=1, text="x").to_dict()
    # not reported → the key is absent (reads back as null), never a spurious 0
    assert "tokens_in" not in not_reported
    assert "cost_usd" not in not_reported
    assert not_reported.get("tokens_in") is None


def test_write_events_round_trips(events_mod, tmp_path):
    E = events_mod.NormalizedEvent
    events = [
        E(kind="system", turn=0, text="init"),
        E(kind="assistant", turn=1, text="hi", tokens_in=5),
        E(kind="final", turn=2, text="bye"),
    ]
    path = tmp_path / "events.jsonl"
    events_mod.write_events(events, str(path))
    lines = path.read_text().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(l) for l in lines]
    assert [p["kind"] for p in parsed] == ["system", "assistant", "final"]
    for p in parsed:
        _assert_event_valid(p)


def test_edit_diff_shapes_across_harnesses(events_mod):
    ed = events_mod.edit_diff
    # whole-file write (claude Write / generic content)
    d = ed("Write", {"file_path": "x.py", "content": "line1\nline2"})
    assert d and "+line1" in d and "b/x.py" in d
    # old/new replace (claude Edit and generic old_str/new_str)
    d = ed("Edit", {"file_path": "x.py", "old_string": "a", "new_string": "b"})
    assert "-a" in d and "+b" in d
    assert "-a" in ed("edit_file", {"path": "x", "old_str": "a", "new_str": "b"})
    # multi-edit list
    d = ed("MultiEdit", {"file_path": "x", "edits": [
        {"old_string": "a", "new_string": "b"}, {"old_string": "c", "new_string": "d"}]})
    assert "-a" in d and "-c" in d
    # a non-edit tool yields no diff (guards on arg shape — nothing reconstructed)
    assert ed("Read", {"file_path": "x.py"}) is None


def test_looks_like_edit(events_mod):
    assert events_mod.looks_like_edit("Write")
    assert events_mod.looks_like_edit("apply_patch")
    assert events_mod.looks_like_edit("write_file")
    assert not events_mod.looks_like_edit("Read")
    assert not events_mod.looks_like_edit(None)


def test_mcp_servers_from_names(events_mod):
    servers = events_mod.mcp_servers_from_names(
        ["Read", "mcp__github__create_issue", "mcp__github__list_prs", "mcp__db__query"])
    by = {s["name"]: s["tools"] for s in servers}
    assert by["github"] == ["create_issue", "list_prs"]
    assert by["db"] == ["query"]
    assert events_mod.mcp_servers_from_names(["Read", "Write"]) == []


def test_cli_version_missing_binary_is_none(events_mod):
    assert events_mod.cli_version(["definitely-not-a-real-binary-xyz", "--version"]) is None


def test_instruction_file_helpers(events_mod, tmp_path):
    (tmp_path / "CLAUDE.md").write_text("root rules")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "CLAUDE.md").write_text("pkg rules")
    (sub / "other.md").write_text("ignore")
    found = events_mod.find_files(str(tmp_path), "CLAUDE.md")
    assert len(found) == 2
    files = events_mod.instruction_files(found + [str(tmp_path / "missing.md")])
    assert [f["path"] for f in files] == found  # missing skipped
    assert files[0]["contents"] in ("root rules", "pkg rules")
