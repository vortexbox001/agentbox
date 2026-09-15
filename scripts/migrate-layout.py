#!/usr/bin/env python3
"""Relocate a live box's config + state into the three roots (spec 010, US1).

Before spec 010 a box kept its agent/prompt config in the product checkout (``agents/``,
``prompts/``, ``orchestrator/settings.yaml``) and its state directly under ``/data``
(``/data/outputs``, ``/data/workspaces``, ``/data/credentials``) with agent transcripts under
the Dagster home (``/data/dagster/agent-logs``). Spec 010 splits those into three roots:

  * ``$AGENTBOX_CONFIG`` (default ``<product>/config``) — instance configuration
  * ``$AGENTBOX_DATA``   (default ``/data/agentbox``)   — instance state
  * ``$DAGSTER_HOME``    (default ``/data/dagster``)    — Dagster's own storage (unchanged)

This tool computes an ordered **plan** of moves / in-YAML rewrites / a compatibility symlink /
left-untouched entries and, by default, prints it and changes nothing (dry run). ``--apply``
performs it. It refuses to run — with or without ``--apply`` — if any destination already has
content, so a half-finished prior migration can never be clobbered (R-MIG-2).

    python3 scripts/migrate-layout.py            # dry run: print the plan, change nothing
    python3 scripts/migrate-layout.py --apply    # perform the moves/rewrites/symlink

Reads the three roots from the same env vars as the running stack (path-resolution §1). The old
locations are the pre-010 hard-coded ones. What stays put: the Dagster home (storage, history,
compute logs, the transient pipes dir) and any unrecognized ``/data`` dir such as ``/data/logs``
— both are recorded in the plan as "left untouched" (R-MIG-6, Clarification C).
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# --- Old-layout anchors (the pre-010 hard-coded locations, contract migration-cli §1) --------
# The product checkout this script lives in (scripts/ -> product root) and the old state root.
PRODUCT_ROOT = str(Path(__file__).resolve().parent.parent)
OLD_DATA_ROOT = "/data"

# Recognized old ``/data/<x>`` state dirs that move wholesale to ``$AGENTBOX_DATA/<x>``.
DATA_SUBDIRS = ("outputs", "workspaces", "credentials")
# The agent fields whose values may hold an old-root path and get rewritten (FR-019).
REWRITE_FIELDS = ("output_dir", "workspace", "env_file")


# --- Plan operations ---------------------------------------------------------
@dataclass(frozen=True)
class Move:
    src: str
    dst: str


@dataclass(frozen=True)
class Symlink:
    link: str
    target: str


@dataclass(frozen=True)
class Rewrite:
    path: str   # the agent YAML the value lives in (its current/source location)
    field: str
    old: str
    new: str


@dataclass(frozen=True)
class GitignoreAdd:
    path: str
    entry: str


@dataclass(frozen=True)
class Untouched:
    path: str
    reason: str


@dataclass(frozen=True)
class Blocker:
    dst: str
    reason: str


@dataclass
class Plan:
    moves: list[Move] = field(default_factory=list)
    rewrites: list[Rewrite] = field(default_factory=list)
    symlinks: list[Symlink] = field(default_factory=list)
    gitignore: list[GitignoreAdd] = field(default_factory=list)
    untouched: list[Untouched] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)


# --- Root resolution ---------------------------------------------------------
def resolve_roots() -> dict:
    """The three new roots (env, path-resolution §1 defaults) plus the old anchors."""
    return {
        "product_root": PRODUCT_ROOT,
        "old_data_root": OLD_DATA_ROOT,
        "config_root": os.environ.get("AGENTBOX_CONFIG") or os.path.join(PRODUCT_ROOT, "config"),
        "data_root": os.environ.get("AGENTBOX_DATA") or "/data/agentbox",
        "dagster_root": os.environ.get("DAGSTER_HOME") or "/data/dagster",
    }


def _rewrite_rules(*, old_data_root: str, data_root: str, dagster_root: str) -> list[tuple[str, str]]:
    """(old_prefix, new_prefix) pairs for in-YAML value rewriting (FR-019, R-MIG-3).

    A value is rewritten only when it **begins with** an old prefix (equals it, or sits under it
    with a ``/`` boundary); already-migrated or unrelated values match nothing and are left as-is.
    Agent-logs is listed first so its more-specific prefix is tried before the bare data subdirs.
    """
    rules = [(os.path.join(dagster_root, "agent-logs"), os.path.join(data_root, "runs"))]
    for sub in DATA_SUBDIRS:
        rules.append((os.path.join(old_data_root, sub), os.path.join(data_root, sub)))
    return rules


def _rewritten_value(value: str, rules: list[tuple[str, str]]) -> str | None:
    """The rewritten value if ``value`` begins with an old root, else ``None`` (leave as-is)."""
    for old, new in rules:
        if value == old:
            return new
        if value.startswith(old + os.sep):
            return new + value[len(old):]
    return None


def _compute_rewrites(agents_dir: str, rules: list[tuple[str, str]]) -> list[Rewrite]:
    """Every field rewrite needed across the agent YAMLs in ``agents_dir`` (source or dest)."""
    out: list[Rewrite] = []
    if not os.path.isdir(agents_dir):
        return out
    for name in sorted(os.listdir(agents_dir)):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(agents_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(loaded, dict):
            continue
        for fld in REWRITE_FIELDS:
            val = loaded.get(fld)
            if isinstance(val, str):
                new = _rewritten_value(val, rules)
                if new is not None and new != val:
                    out.append(Rewrite(path, fld, val, new))
    return out


def _occupied(dst: str) -> bool:
    """True if ``dst`` already holds content (a non-empty dir, a file, or a symlink)."""
    if os.path.islink(dst):
        return True
    if os.path.isdir(dst):
        return bool(os.listdir(dst))
    return os.path.exists(dst)


# --- Plan construction (FR-018/019/021, R-MIG-1..6) --------------------------
def build_plan(*, product_root: str, old_data_root: str, config_root: str,
               data_root: str, dagster_root: str) -> Plan:
    """Compute the ordered migration plan from what actually exists on disk.

    Pure: reads the filesystem but never writes. Every root is injected so tests can synthesize
    an old-layout fixture tree in a temp dir. If any destination is occupied, the plan carries a
    :class:`Blocker` and the caller refuses (R-MIG-2).
    """
    plan = Plan()

    # 1. Config moves: product agents/ + prompts/ -> $CONFIG (the move removes them from the
    #    checkout — git surfaces the deletions, SC-002), and orchestrator/settings.yaml if present.
    for name in ("agents", "prompts"):
        src = os.path.join(product_root, name)
        if os.path.isdir(src):
            plan.moves.append(Move(src, os.path.join(config_root, name)))
    settings_src = os.path.join(product_root, "orchestrator", "settings.yaml")
    if os.path.isfile(settings_src):
        plan.moves.append(Move(settings_src, os.path.join(config_root, "settings.yaml")))

    # 2. State moves: recognized /data/<x> -> $DATA/<x>.
    for sub in DATA_SUBDIRS:
        src = os.path.join(old_data_root, sub)
        if os.path.isdir(src) and not os.path.islink(src):
            plan.moves.append(Move(src, os.path.join(data_root, sub)))

    # 3. Transcripts move OUT of the Dagster home: /data/dagster/agent-logs -> $DATA/runs, plus a
    #    compatibility symlink at the old location so historical transcript links still resolve
    #    (FR-021, R-MIG-4). New runs write straight to $DATA/runs and never depend on the symlink.
    runs_dst = os.path.join(data_root, "runs")
    old_agent_logs = os.path.join(dagster_root, "agent-logs")
    if os.path.isdir(old_agent_logs) and not os.path.islink(old_agent_logs):
        plan.moves.append(Move(old_agent_logs, runs_dst))
        plan.symlinks.append(Symlink(old_agent_logs, runs_dst))

    # 4. In-YAML rewrites of old-root output_dir/workspace/env_file values (computed from the
    #    source agents dir; re-derived against the moved dir at apply time).
    rules = _rewrite_rules(old_data_root=old_data_root, data_root=data_root, dagster_root=dagster_root)
    plan.rewrites = _compute_rewrites(os.path.join(product_root, "agents"), rules)

    # 5. Product-repo cleanliness: ensure /config/ is gitignored (idempotent; T001 already added
    #    it on the product repo, so this is usually a no-op on a real box).
    gitignore = os.path.join(product_root, ".gitignore")
    entry = "/config/"
    present = False
    if os.path.isfile(gitignore):
        with open(gitignore, encoding="utf-8") as f:
            present = any(line.strip() in (entry, "config/") for line in f)
    if not present:
        plan.gitignore.append(GitignoreAdd(gitignore, entry))

    # 6. Left-untouched: the Dagster home (storage/history/compute-logs/pipes) and any
    #    unrecognized /data entry (e.g. /data/logs) are neither moved nor deleted (R-MIG-6).
    seen: set[str] = set()

    def record_untouched(path: str, reason: str) -> None:
        ap = os.path.abspath(path)
        if ap in seen:
            return
        seen.add(ap)
        plan.untouched.append(Untouched(path, reason))

    if os.path.isdir(dagster_root):
        record_untouched(dagster_root, "Dagster storage/DB + pipes — stays under $DAGSTER_HOME")
    recognized = set(DATA_SUBDIRS)
    if os.path.isdir(old_data_root):
        for name in sorted(os.listdir(old_data_root)):
            full = os.path.join(old_data_root, name)
            ap = os.path.abspath(full)
            if name in recognized:
                continue                                   # a state move (handled above)
            if ap in (os.path.abspath(data_root), os.path.abspath(dagster_root)):
                continue                                   # the new data root / the Dagster home
            record_untouched(full, "unrecognized old-root entry — left as-is")

    # 7. Clobber guard: any occupied destination blocks the whole run (R-MIG-2).
    for mv in plan.moves:
        if _occupied(mv.dst):
            plan.blockers.append(Blocker(mv.dst, "destination already has content"))

    return plan


# --- Rendering ---------------------------------------------------------------
def render_plan(plan: Plan) -> str:
    lines: list[str] = []

    def section(title: str, rows: list[str]) -> None:
        lines.append(f"{title} ({len(rows)}):")
        lines.extend(f"  {r}" for r in rows) if rows else lines.append("  (none)")
        lines.append("")

    section("MOVE", [f"{m.src}  ->  {m.dst}" for m in plan.moves])
    section("REWRITE (in-YAML)",
            [f"{os.path.basename(r.path)}: {r.field}: {r.old}  ->  {r.new}" for r in plan.rewrites])
    section("SYMLINK (migrated history)", [f"{s.link}  ->  {s.target}" for s in plan.symlinks])
    section("GITIGNORE", [f"add {g.entry} to {g.path}" for g in plan.gitignore])
    section("LEFT UNTOUCHED", [f"{u.path}  ({u.reason})" for u in plan.untouched])
    return "\n".join(lines).rstrip() + "\n"


# --- Apply -------------------------------------------------------------------
def _atomic_write(path: str, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file in the same dir + ``os.replace``),
    UTF-8 with LF endings — the UI's store-write style (R-MIG-3)."""
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _apply_rewrite(rw: Rewrite) -> None:
    """Rewrite a single ``field: value`` line in place, preserving any trailing comment (R-MIG-3).

    Values in agent YAMLs are unquoted single tokens (``output_dir: /data/outputs/x  # ...``); the
    line's key + spacing and its ``# comment`` are kept, only the value token is swapped.
    """
    with open(rw.path, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(rf"^(\s*{re.escape(rw.field)}:[ \t]*)(\S+)(.*)$", re.MULTILINE)

    def repl(m: re.Match) -> str:
        return m.group(1) + rw.new + m.group(3) if m.group(2) == rw.old else m.group(0)

    _atomic_write(rw.path, pattern.sub(repl, text))


def apply_plan(plan: Plan, *, config_root: str, old_data_root: str,
               data_root: str, dagster_root: str, **_ignored) -> None:
    """Execute the plan: moves, then in-YAML rewrites on the moved agents, then the symlink,
    then the gitignore entry. Callers must have refused already if ``plan.blockers`` is non-empty.
    """
    for mv in plan.moves:
        os.makedirs(os.path.dirname(mv.dst), exist_ok=True)
        # A prior bootstrap may have created the destination as an empty dir; drop it so the move
        # renames src -> dst instead of nesting src inside it. (Non-empty dests were refused.)
        if os.path.isdir(mv.dst) and not os.path.islink(mv.dst) and not os.listdir(mv.dst):
            os.rmdir(mv.dst)
        shutil.move(mv.src, mv.dst)

    rules = _rewrite_rules(old_data_root=old_data_root, data_root=data_root, dagster_root=dagster_root)
    for rw in _compute_rewrites(os.path.join(config_root, "agents"), rules):
        _apply_rewrite(rw)

    for sl in plan.symlinks:
        os.makedirs(os.path.dirname(sl.link), exist_ok=True)
        if os.path.lexists(sl.link):
            os.remove(sl.link)
        os.symlink(sl.target, sl.link)

    for gi in plan.gitignore:
        with open(gi.path, "a", encoding="utf-8") as f:
            f.write(gi.entry + "\n")


# --- Entry point -------------------------------------------------------------
def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    roots = resolve_roots()
    plan = build_plan(**roots)

    if plan.blockers:
        print("REFUSING TO MIGRATE — a destination already has content:")
        for b in plan.blockers:
            print(f"  {b.dst}  ({b.reason})")
        print("\nNothing was changed. Move or clear the destination(s) above, then re-run.")
        return 1

    print(render_plan(plan))
    if apply:
        apply_plan(plan, **roots)
        print("Applied. Regenerate the LiteLLM config and restart the stack "
              "(see specs/010-file-layout-overhaul/quickstart.md).")
    else:
        print("Dry run — nothing changed. Re-run with --apply to perform the migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
