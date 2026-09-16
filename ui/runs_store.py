"""Read run directories from disk for the viewer (spec 012, contracts/viewer-routes.md).

A pure disk reader over ``$AGENTBOX_DATA/runs/<agent>/<date>/<run-id>/`` (mounted read-only into
the ui service). It NEVER calls Dagster, so the Runs list and run pages render with the
orchestrator stopped (FR-018/SC-007); Dagster is queried elsewhere, best-effort, only to enrich
list rows with live status.

- ``list_runs`` makes one pass over the tree, reading only ``report.json`` + ``context.json``
  headers per run (never ``events.jsonl``), and filters by agent / status / date range.
- ``read_run`` loads the four files (each optional; a partial write, a pruned run, or a legacy
  flat transcript renders whatever exists) and sets ``conversation_available``.
- ``read_events`` streams the normalized events for the Conversation tab.
- ``read_output_files`` / ``read_output_file`` back the Files tab (US3).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

import config


def _time_of_day(started: float) -> str:
    """Local ``HH:MM`` for a dir mtime, or ``""`` when unknown (FR-017 'time' column)."""
    if not started:
        return ""
    try:
        return datetime.fromtimestamp(started).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


# The four per-run filenames come from config (mirrored from orchestrator/paths, parity-tested).
_TRANSCRIPT = config.RUN_TRANSCRIPT
_EVENTS = config.RUN_EVENTS
_CONTEXT = config.RUN_CONTEXT
_REPORT = config.RUN_REPORT


def _runs_dir() -> str:
    return config.RUNS_DIR


def _load_json(path: str) -> Optional[dict]:
    """Tolerant JSON load: None if the file is absent, unreadable, or malformed."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _row_from_dir(agent: str, date: str, run_id: str, run_dir: str) -> dict:
    """A list row from the run dir's report + context headers only (never events)."""
    report = _load_json(os.path.join(run_dir, _REPORT)) or {}
    context = _load_json(os.path.join(run_dir, _CONTEXT)) or {}
    try:
        started = os.path.getmtime(run_dir)
    except OSError:
        started = 0.0
    model = ((context.get("model") or {}).get("model")) or report.get("model") or ""
    asset = context.get("asset") or {}
    return {
        "run_id": run_id,
        "agent": agent,
        "date": date,
        "started": started,                       # dir mtime, for sort + relative-time display
        "started_time": _time_of_day(started),    # HH:MM for the list 'time' column (FR-017)
        "status": report.get("status") or "unknown",
        "model": model,
        "cost_usd": report.get("cost_usd"),
        "attempts": asset.get("attempt"),
        "harness": (context.get("harness") or {}).get("harness"),
        "run_dir": run_dir,
        "conversation_available": os.path.isfile(os.path.join(run_dir, _EVENTS)),
        "legacy": False,
    }


def _row_from_legacy(agent: str, date: str, run_id: str, path: str) -> dict:
    """A list row for a pre-012 flat ``<run-id>.jsonl`` transcript (transcript-only, R1)."""
    try:
        started = os.path.getmtime(path)
    except OSError:
        started = 0.0
    return {
        "run_id": run_id,
        "agent": agent,
        "date": date,
        "started": started,
        "started_time": _time_of_day(started),
        "status": "unknown",
        "model": "",
        "cost_usd": None,
        "attempts": None,
        "harness": None,
        "run_dir": os.path.dirname(path),
        "conversation_available": False,
        "legacy": True,
    }


def _iter_run_entries():
    """Yield ``(agent, date, run_id, path, is_legacy)`` for every run under the runs root."""
    root = _runs_dir()
    if not os.path.isdir(root):
        return
    for agent in sorted(os.listdir(root)):
        agent_dir = os.path.join(root, agent)
        if not os.path.isdir(agent_dir):
            continue
        for date in sorted(os.listdir(agent_dir)):
            date_dir = os.path.join(agent_dir, date)
            if not os.path.isdir(date_dir):
                continue
            for entry in sorted(os.listdir(date_dir)):
                full = os.path.join(date_dir, entry)
                if os.path.isdir(full):
                    yield agent, date, entry, full, False
                elif entry.endswith(".jsonl"):
                    yield agent, date, entry[: -len(".jsonl")], full, True


def list_runs(agent: Optional[str] = None, status: Optional[str] = None,
              date_from: Optional[str] = None, date_to: Optional[str] = None) -> list[dict]:
    """Every run as a list row, newest first, filtered by agent / status / date range.

    Reads only ``report.json`` + ``context.json`` headers per run (never ``events.jsonl``), so a
    long transcript never slows the list. Dates compare lexicographically (ISO ``YYYY-MM-DD``).
    """
    rows: list[dict] = []
    for a, date, run_id, path, is_legacy in _iter_run_entries():
        if agent and a != agent:
            continue
        if date_from and date < date_from:
            continue
        if date_to and date > date_to:
            continue
        row = _row_from_legacy(a, date, run_id, path) if is_legacy \
            else _row_from_dir(a, date, run_id, path)
        if status and row["status"] != status:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["started"], reverse=True)
    return rows


def _find_run(run_id: str):
    """Locate a run by id → ``(agent, date, run_id, path, is_legacy)`` or None."""
    for entry in _iter_run_entries():
        if entry[2] == run_id:
            return entry
    return None


def read_run(run_id: str) -> Optional[dict]:
    """Load one run's four files (each optional) for the detail page, or None if absent.

    ``conversation_available`` is the presence of ``events.jsonl`` (false for a pruned or legacy
    run). ``context``/``report`` are the parsed files or None; the page renders whatever exists
    and never fails because one file is missing (edge case).
    """
    found = _find_run(run_id)
    if not found:
        return None
    agent, date, _run_id, path, is_legacy = found
    if is_legacy:
        run_dir = os.path.dirname(path)
        return {
            "run_id": run_id, "agent": agent, "date": date, "run_dir": run_dir,
            "legacy": True, "context": None, "report": None,
            "conversation_available": False,
            "transcript_available": os.path.isfile(path),
            "transcript_path": path,
            "events_path": None,
            "context_path": None, "report_path": None,
        }
    run_dir = path
    events_path = os.path.join(run_dir, _EVENTS)
    transcript_path = os.path.join(run_dir, _TRANSCRIPT)
    return {
        "run_id": run_id, "agent": agent, "date": date, "run_dir": run_dir, "legacy": False,
        "context": _load_json(os.path.join(run_dir, _CONTEXT)),
        "report": _load_json(os.path.join(run_dir, _REPORT)),
        "conversation_available": os.path.isfile(events_path),
        "transcript_available": os.path.isfile(transcript_path),
        "transcript_path": transcript_path if os.path.isfile(transcript_path) else None,
        "events_path": events_path if os.path.isfile(events_path) else None,
        "context_path": os.path.join(run_dir, _CONTEXT),
        "report_path": os.path.join(run_dir, _REPORT),
    }


_ARG_KEYS = ("command", "file_path", "path", "pattern", "query", "url", "notebook_path")
_ROLE = {"system": "System", "user": "Task", "assistant": "Agent",
         "final": "Result", "error": "Error"}


def _arg_summary(args) -> Optional[str]:
    """A one-line summary of tool args for the collapsed tool head."""
    if not isinstance(args, dict) or not args:
        return None
    for k in _ARG_KEYS:
        if args.get(k):
            return str(args[k])
    for v in args.values():
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            return str(v)
    return None


def _entry_meta(e: dict) -> Optional[str]:
    bits = []
    if e.get("turn"):
        bits.append(f"turn {e['turn']}")
    ti, to = e.get("tokens_in"), e.get("tokens_out")
    if ti is not None or to is not None:
        bits.append(f"{(ti or 0) + (to or 0):,} tokens")
    if e.get("cost_usd") is not None:
        bits.append(f"${e['cost_usd']:.4f}")
    return " · ".join(bits) or None


def _new_entry(role, kind, meta=None, state=None, text=""):
    return {"role": role, "kind": kind, "meta": meta, "state": state, "text": text, "tools": []}


def conversation_entries(events: list[dict]) -> list[dict]:
    """Group the flat normalized events into display entries for the Conversation tab.

    Each message event (system/user/assistant/final/error) opens an entry; tool_call/tool_result
    pairs attach as tool cards to the current entry (an orphan result becomes its own card). Order
    is preserved and content is never summarized (FR-007); a missing result is marked, not hidden
    (FR-021).
    """
    entries: list[dict] = []
    cur = None
    for e in events:
        kind = e.get("kind")
        if kind in _ROLE:
            cur = _new_entry(_ROLE[kind], kind, meta=_entry_meta(e),
                             state=("error" if kind == "error" else None), text=e.get("text") or "")
            entries.append(cur)
        elif kind == "tool_call":
            if cur is None or cur["kind"] in ("final", "error"):
                cur = _new_entry("Agent", "assistant")
                entries.append(cur)
            cur["tools"].append({
                "tool": e.get("tool") or "", "arg": _arg_summary(e.get("args")),
                "result": None, "diff": None, "missing": False, "state": None, "exit": None,
            })
        elif kind == "tool_result":
            if cur is None:
                cur = _new_entry("Agent", "assistant")
                entries.append(cur)
            slot = None
            if cur["tools"] and cur["tools"][-1]["result"] is None \
                    and cur["tools"][-1]["diff"] is None and not cur["tools"][-1]["missing"]:
                slot = cur["tools"][-1]
            if slot is None:
                slot = {"tool": "result", "arg": None, "result": None, "diff": None,
                        "missing": False, "state": None, "exit": None}
                cur["tools"].append(slot)
            slot["result"] = e.get("result") or ""
            slot["diff"] = e.get("diff")
            slot["missing"] = bool(e.get("missing"))
            if slot["missing"]:
                slot["state"] = "error"
    return entries


def _output_dir_and_session(detail: dict):
    """(output_dir, session_id) for a run, from its context, or (None, None)."""
    context = detail.get("context") or {}
    run = context.get("run") or {}
    output_dir = run.get("output_dir")
    if not output_dir:
        for m in (context.get("runtime") or {}).get("mounts") or []:
            if m.get("target") == "/output":
                output_dir = m.get("source")
                break
    return output_dir, run.get("session_id")


# Text extensions previewable inline in the viewer; everything else downloads.
_PREVIEW_EXTS = (".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".log", ".py", ".js",
                 ".html", ".css", ".toml", ".ini", ".sh", ".xml")


def read_output_files(run_id: str) -> list[dict]:
    """The run's ``/output`` artifacts (FR-019a), matched by the session id the output convention
    embeds in each filename. Empty when the run wrote none, or when it cannot be associated.
    """
    detail = read_run(run_id)
    if not detail:
        return []
    output_dir, session_id = _output_dir_and_session(detail)
    if not output_dir or not session_id or not os.path.isdir(output_dir):
        return []
    files = []
    for entry in sorted(os.listdir(output_dir)):
        if session_id not in entry:
            continue
        full = os.path.join(output_dir, entry)
        if not os.path.isfile(full):
            continue
        try:
            size = os.path.getsize(full)
        except OSError:
            continue
        files.append({
            "name": entry, "size": size,
            "previewable": entry.lower().endswith(_PREVIEW_EXTS),
        })
    return files


def read_output_file(run_id: str, name: str):
    """(absolute path, previewable) for one of the run's output artifacts, or (None, False).

    The name is validated against the run's own artifact list (a whitelist), so a traversal or an
    unrelated file can never be served (FR-019a, path-safe).
    """
    for f in read_output_files(run_id):
        if f["name"] == name:
            detail = read_run(run_id)
            output_dir, _ = _output_dir_and_session(detail)
            return os.path.join(output_dir, name), f["previewable"]
    return None, False


# Volatile groups excluded from a context comparison so a single config change surfaces exactly
# one difference (SC-005): file trees and the per-run identity are expected to differ every run.
_COMPARE_EXCLUDE = ("file_trees", "run")
_MISSING = object()


def _flatten(obj, prefix="") -> dict:
    """Flatten a context to ``dotted.path -> value``; lists compare as a whole (JSON), so element
    order/count is one field rather than noisy per-index diffs."""
    out: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        out[prefix] = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    else:
        out[prefix] = obj
    return out


def compare_contexts(a: dict, b: dict) -> list[dict]:
    """Field-by-field diff of two context snapshots (FR-023): only differing fields, each a row
    ``{path, a, b, state}`` where state ∈ added|removed|changed. A field present on only one side
    is shown as present-on-one (added/removed), never implied equivalent (edge case)."""
    fa = _flatten({k: v for k, v in (a or {}).items() if k not in _COMPARE_EXCLUDE})
    fb = _flatten({k: v for k, v in (b or {}).items() if k not in _COMPARE_EXCLUDE})
    rows = []
    for path in sorted(set(fa) | set(fb)):
        va = fa.get(path, _MISSING)
        vb = fb.get(path, _MISSING)
        if va == vb:
            continue
        if va is _MISSING:
            state = "added"
        elif vb is _MISSING:
            state = "removed"
        else:
            state = "changed"
        rows.append({
            "path": path,
            "a": None if va is _MISSING else va,
            "b": None if vb is _MISSING else vb,
            "state": state,
        })
    return rows


_RAW_MAX_BYTES = 512 * 1024


def read_transcript(run_id: str, max_bytes: int = _RAW_MAX_BYTES):
    """The native ``transcript.jsonl`` text for the Raw-log view → ``(text, truncated)``.

    Bounded so a huge transcript never bloats the page; ``text`` is None when the transcript is
    absent (pruned / never captured). Already redacted on disk.
    """
    detail = read_run(run_id)
    path = detail and detail.get("transcript_path")
    if not path:
        return None, False
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
    except OSError:
        return None, False
    truncated = len(data) > max_bytes
    return data[:max_bytes].decode("utf-8", "replace"), truncated


def read_events(run_id: str) -> list[dict]:
    """The normalized events for the conversation timeline (empty if none/pruned/legacy)."""
    detail = read_run(run_id)
    if not detail or not detail.get("events_path"):
        return []
    events: list[dict] = []
    try:
        with open(detail["events_path"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return events
