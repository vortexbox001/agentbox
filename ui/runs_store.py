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
import re
from datetime import datetime, timezone
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


# ── Runs-overview presentation helpers (spec 015) ───────────────────────────
# Built at render time from the store row's `started` epoch (dir mtime) and, where the
# Dagster enrichment supplies them, its start/end times. No new disk reads on the hot path.

def created_iso(started: float) -> str:
    """The full ISO-8601 timestamp (UTC) for a `started` epoch, or ``""`` when unknown.

    The machine-readable companion to the `Sep 17, 1:15 PM` label: runs-list.js re-localises
    it to the browser timezone on first paint, and it is the `title=` hover value (FR-017,
    research R7). UTC + offset so a browser parses it as an unambiguous instant.
    """
    if not started:
        return ""
    try:
        return datetime.fromtimestamp(started, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def created_label(started: float) -> str:
    """The server-rendered `Sep 17, 1:15 PM` fallback label in the server's local time
    (research R7); ``""`` when unknown. runs-list.js replaces it with the browser-local
    rendering on first paint."""
    if not started:
        return ""
    try:
        return datetime.fromtimestamp(started).strftime("%b %-d, %-I:%M %p")
    except (OverflowError, OSError, ValueError):
        return ""


def duration_seconds(started, ended) -> Optional[float]:
    """Elapsed seconds between two epochs: `ended − started` for a finished run, or
    `now − started` for an in-progress run (ended is None/0). None when start is unknown
    (FR-018). No live ticker: an in-progress duration advances only on refresh."""
    if not started:
        return None
    end = ended if ended else datetime.now(tz=timezone.utc).timestamp()
    delta = end - started
    return delta if delta >= 0 else None


def matches_text(row: dict, q: Optional[str]) -> bool:
    """Whether a presented row matches the case-insensitive text filter `q` — a substring over
    agent, model, run id, and (once enrichment supplies it) target (FR-009, research R3). An
    absent/em-dash target never matches."""
    if not q:
        return True
    needle = q.lower()
    hay = [row.get("agent"), row.get("model"), row.get("run_id")]
    target = row.get("target")
    if target and target != "—":
        hay.append(target)
    return any(needle in str(h).lower() for h in hay if h)


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


# ── Run-detail section view-model helpers (spec 017) ────────────────────────
# All pure functions over data the page already loads (read_events → conversation_entries,
# read_output_files, read_run); nothing here writes the run record or reads new disk (FR-035).

_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
_PR_URL_RE = re.compile(r"https://github\.com/[^\s\"')]+/pull/\d+", re.I)
_COMMIT_MARKER_RE = re.compile(r"\b(?:commit|committed|push|pushed)\b", re.I)
# The `[branch sha] message` form git commit/push prints, e.g. `[main 1a2b3c4] wire it up`.
_COMMIT_BRACKET_RE = re.compile(r"\[[\w./-]+\s+([0-9a-f]{7,40})\]", re.I)
_SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b", re.I)
_EXIT_RE = re.compile(r"\bexit(?:\s*code)?[:\s]+(\d+)", re.I)
_REFUSAL_RE = re.compile(
    r"permission denied|not permitted|operation not permitted|permission to use|"
    r"\brefused\b|blocked by (?:the )?permission", re.I)


def produced_elsewhere(events: list[dict]) -> list[dict]:
    """Best-effort miner over the normalized event stream (contract §B, R4).

    Returns ``{kind, identifier, action}`` rows grouped **pull_request → commit → file**, event
    order preserved within each kind. Pure; ``[]`` when nothing matches; never raises (FR-013).
    """
    prs: list[dict] = []
    commits: list[dict] = []
    files: list[dict] = []
    for e in events or []:
        kind = e.get("kind")
        if kind == "tool_result":
            result = e.get("result") or ""
            m = _PR_URL_RE.search(result)
            if m:
                prs.append({"kind": "pull_request", "identifier": m.group(0), "action": m.group(0)})
                continue
            bracket = _COMMIT_BRACKET_RE.search(result)
            if bracket:
                commits.append({"kind": "commit", "identifier": bracket.group(1), "action": None})
            elif _COMMIT_MARKER_RE.search(result):
                sm = _SHA_RE.search(result)
                if sm:
                    commits.append({"kind": "commit", "identifier": sm.group(1), "action": None})
        elif kind == "tool_call" and (e.get("tool") or "") in _WRITE_TOOLS:
            args = e.get("args") if isinstance(e.get("args"), dict) else {}
            path = args.get("file_path") or args.get("path")
            if path:
                files.append({"kind": "file", "identifier": str(path), "action": None})
    return prs + commits + files


def _line_count(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _derive_marker(tool: dict):
    """(marker, out_intent) for a tool card head (FR-022, R6). The event schema has no exit
    field, so the marker is derived from the result text: ``failed`` for a missing/refused result,
    ``exit N`` only when the text carries a recognizable exit code, else neither."""
    if tool.get("missing"):
        return "failed", "missing"
    result = tool.get("result") or ""
    if _REFUSAL_RE.search(result):
        return "failed", "failed"
    m = _EXIT_RE.search(result)
    if m:
        n = m.group(1)
        return f"exit {n}", ("failed" if n != "0" else None)
    return None, None


def enrich_tool_cards(entries: list[dict]) -> list[dict]:
    """Add IN/OUT tool-card presentation fields to each tool in ``conversation_entries`` output
    (contract §C). Clamp height is fixed at 3 lines; diff OUT rows never clamp (expanded by
    default, FR-026). Mutates and returns ``entries``."""
    for entry in entries:
        for t in entry.get("tools") or []:
            diff = t.get("diff")
            is_diff = diff is not None
            in_text = t.get("arg") or ""
            out_text = diff if is_diff else (t.get("result") or "")
            if t.get("missing") and not out_text:
                out_text = "result not captured — recorded as missing"
            in_lines = _line_count(in_text)
            out_lines = _line_count(out_text)
            marker, out_intent = _derive_marker(t)
            t["name"] = t.get("tool") or ""
            t["description"] = t.get("arg")
            t["marker"] = marker
            t["in_text"] = in_text
            t["out_text"] = out_text
            t["in_lines"] = in_lines
            t["out_lines"] = out_lines
            t["in_overflow"] = in_lines > 3
            t["out_overflow"] = out_lines > 3 and not is_diff
            t["is_diff"] = is_diff
            t["out_intent"] = out_intent
    return entries


def dedup_final(entries: list[dict]) -> list[dict]:
    """Collapse a final assistant message that duplicates the final event into a single Result
    (FR-032): drop the assistant entry immediately preceding a ``final`` entry when their text
    matches and the assistant entry carries no tools. Mutates and returns ``entries``."""
    if len(entries) < 2 or entries[-1].get("kind") != "final":
        return entries
    final_text = (entries[-1].get("text") or "").strip()
    if not final_text:
        return entries
    for i in range(len(entries) - 2, -1, -1):
        e = entries[i]
        if e.get("kind") == "assistant":
            if (e.get("text") or "").strip() == final_text and not e.get("tools"):
                entries.pop(i)
            break
    return entries


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def section_note_output(files: list, produced: list) -> str:
    """Output closed-state note: "N files · M pull request(s)" — the files part always shows,
    the pull-request part only when non-zero; "0 files" alone when nothing was produced (FR-014)."""
    n_prs = sum(1 for p in (produced or []) if p.get("kind") == "pull_request")
    parts = [_plural(len(files or []), "file")]
    if n_prs:
        parts.append(_plural(n_prs, "pull request"))
    return " · ".join(parts)


def section_note_checks(checks: list) -> str:
    """Checks note counting outcomes across the full vocabulary; "—" when zero recorded checks
    (a not-run check still counts and does not yield "—") (FR-017/FR-018)."""
    if not checks:
        return "—"
    passed = sum(1 for c in checks if c.get("status") == "pass")
    warn = sum(1 for c in checks if c.get("status") == "warn")
    failed = sum(1 for c in checks if c.get("status") == "fail-blocking")
    not_run = sum(1 for c in checks if c.get("status") == "not-run")
    parts = []
    if passed:
        parts.append(f"{passed} passed")
    if warn:
        parts.append(_plural(warn, "warning"))
    if failed:
        parts.append(f"{failed} failed")
    if not_run:
        parts.append(f"{not_run} not run")
    return " · ".join(parts) if parts else "—"


def section_note_context(context: dict) -> str:
    """Context note: "prompt · appended · N instruction file(s)" (FR-020)."""
    context = context or {}
    prompt = context.get("prompt") or {}
    parts = []
    if prompt.get("prompt_text"):
        parts.append("prompt")
    if prompt.get("append_system_prompt"):
        parts.append("appended")
    parts.append(_plural(len(context.get("instruction_files") or []), "instruction file"))
    return " · ".join(parts)


def section_note_transcript(entries: list, report: dict) -> str:
    """Transcript note: "N turns · M tool calls" (FR-034)."""
    report = report or {}
    tool_calls = sum(len(e.get("tools") or []) for e in entries)
    turns = report.get("turns")
    if turns is None:
        turns = sum(1 for e in entries if e.get("kind") in ("user", "assistant", "final"))
    return f"{turns} turns · {_plural(tool_calls, 'tool call')}"


def foot_line(report: dict, tool_calls: Optional[int] = None) -> str:
    """The run foot line: status · turns · files written [· M tool calls]. Three fields for the
    Summary fallback (FR-008); pass ``tool_calls`` for the four-field Transcript foot (FR-033)."""
    report = report or {}
    bits = [report.get("status") or "unknown"]
    if report.get("turns") is not None:
        bits.append(f"{report['turns']} turns")
    if report.get("files_written") is not None:
        bits.append(f"{report['files_written']} files written")
    if tool_calls is not None:
        bits.append(_plural(tool_calls, "tool call"))
    return " · ".join(bits)


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
