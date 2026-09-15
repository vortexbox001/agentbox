"""Unit tests for scripts/migrate-layout.py (spec 010 US1, contract migration-cli §4).

The tool is filesystem-driven with every root injected, so each test synthesizes an old-layout
fixture tree in a temp dir and asserts the computed plan (R-MIG-1/3/4/6) or the clobber refusal
(R-MIG-2). The module has a hyphenated filename, so it is loaded by path.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

# Load scripts/migrate-layout.py (hyphenated → not importable by name). Register it in
# sys.modules before executing so its dataclass annotations resolve against the module.
_MODULE_PATH = Path(__file__).resolve().parents[1] / "migrate-layout.py"
_spec = importlib.util.spec_from_file_location("migrate_layout", _MODULE_PATH)
mig = importlib.util.module_from_spec(_spec)
sys.modules["migrate_layout"] = mig
_spec.loader.exec_module(mig)


# --- Fixture: a full old-layout box under tmp, mirroring the real /data split ----------------
@pytest.fixture
def box(tmp_path):
    """An old-layout box. Returns the roots dict passed straight to ``build_plan``.

    Layout mirrors production: state lives directly under ``old_data`` (``/data``), with the new
    data root (``/data/agentbox``) and the Dagster home (``/data/dagster``) nested inside it.
    """
    product = tmp_path / "product"
    old_data = tmp_path / "data"
    config = tmp_path / "config"
    data = old_data / "agentbox"
    dagster = old_data / "dagster"

    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # Product config (moves to $CONFIG).
    write(product / "agents" / "repo.yaml",
          f"name: repo\noutput_dir: {old_data}/outputs/repo  # out\n"
          f"workspace: {old_data}/workspaces/repo  # ws\n")
    write(product / "agents" / "already.yaml",
          f"name: already\noutput_dir: {data}/outputs/already\n")   # already migrated
    write(product / "agents" / "default.yaml",
          f"name: default\noutput_dir: /output\n"
          f"env_file: {old_data}/credentials/default.env  # creds\n")
    write(product / "prompts" / "repo.md", "do the thing\n")
    write(product / "orchestrator" / "settings.yaml", "instance: box-a\n")
    write(product / ".gitignore", "/config/\n__pycache__/\n")       # /config/ already present

    # Old state under /data (moves to $DATA).
    write(old_data / "outputs" / "repo" / "result.txt", "R\n")
    write(old_data / "workspaces" / "repo" / "scratch.txt", "S\n")
    write(old_data / "credentials" / "claude" / ".creds.json", "{}\n")
    write(old_data / "logs" / "boot.log", "boot\n")                 # unrecognized — untouched

    # Dagster home: agent-logs moves OUT to $DATA/runs; storage/pipes stay.
    write(dagster / "agent-logs" / "repo" / "2026-01-01" / "run.jsonl", "{}\n")
    write(dagster / "storage" / "run-x" / "compute_logs" / "step.err", "trace\n")
    write(dagster / "pipes" / "keep", "x\n")

    return {
        "product_root": str(product),
        "old_data_root": str(old_data),
        "config_root": str(config),
        "data_root": str(data),
        "dagster_root": str(dagster),
    }


def snapshot(root: str) -> dict:
    """Map every path under ``root`` to its bytes (or symlink target), for change detection."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in list(dirnames):
            p = os.path.join(dirpath, name)
            if os.path.islink(p):
                out[os.path.relpath(p, root)] = "->" + os.readlink(p)
        for name in filenames:
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root)
            out[rel] = "->" + os.readlink(p) if os.path.islink(p) else Path(p).read_text()
    return out


# --- R-MIG-1: the planner lists exactly the expected operations -----------------------------
def test_plan_moves(box):
    plan = mig.build_plan(**box)
    pairs = {(m.src, m.dst) for m in plan.moves}
    p, od, cfg, dat, dag = (box["product_root"], box["old_data_root"], box["config_root"],
                            box["data_root"], box["dagster_root"])
    assert pairs == {
        (f"{p}/agents", f"{cfg}/agents"),
        (f"{p}/prompts", f"{cfg}/prompts"),
        (f"{p}/orchestrator/settings.yaml", f"{cfg}/settings.yaml"),
        (f"{od}/outputs", f"{dat}/outputs"),
        (f"{od}/workspaces", f"{dat}/workspaces"),
        (f"{od}/credentials", f"{dat}/credentials"),
        (f"{dag}/agent-logs", f"{dat}/runs"),
    }
    assert not plan.blockers


def test_plan_symlink_recorded(box):
    # R-MIG-4: the compatibility symlink for migrated history is in the plan.
    plan = mig.build_plan(**box)
    assert [(s.link, s.target) for s in plan.symlinks] == [
        (f"{box['dagster_root']}/agent-logs", f"{box['data_root']}/runs")
    ]


def test_plan_rewrites_only_old_root_values(box):
    # R-MIG-3: only values beginning with an old root are rewritten; already-migrated / unrelated
    # (/output) values are left alone.
    plan = mig.build_plan(**box)
    od, dat = box["old_data_root"], box["data_root"]
    triples = {(os.path.basename(r.path), r.field, r.old, r.new) for r in plan.rewrites}
    assert triples == {
        ("repo.yaml", "output_dir", f"{od}/outputs/repo", f"{dat}/outputs/repo"),
        ("repo.yaml", "workspace", f"{od}/workspaces/repo", f"{dat}/workspaces/repo"),
        ("default.yaml", "env_file", f"{od}/credentials/default.env", f"{dat}/credentials/default.env"),
    }


def test_plan_left_untouched(box):
    # R-MIG-6 / Clarification C: /data/logs and the Dagster home are recorded, not moved.
    plan = mig.build_plan(**box)
    untouched = {u.path for u in plan.untouched}
    assert f"{box['old_data_root']}/logs" in untouched
    assert box["dagster_root"] in untouched
    # neither appears as a move source
    move_srcs = {m.src for m in plan.moves}
    assert f"{box['old_data_root']}/logs" not in move_srcs
    assert box["dagster_root"] not in move_srcs


def test_plan_gitignore_absent_when_already_present(box):
    # /config/ is already in the fixture .gitignore → no gitignore op.
    plan = mig.build_plan(**box)
    assert plan.gitignore == []


def test_plan_gitignore_added_when_missing(box):
    Path(box["product_root"], ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    plan = mig.build_plan(**box)
    assert [(g.entry) for g in plan.gitignore] == ["/config/"]


# --- R-MIG-1: a dry run changes nothing -----------------------------------------------------
def test_dry_run_changes_nothing(box, monkeypatch, capsys):
    monkeypatch.setattr(mig, "PRODUCT_ROOT", box["product_root"])
    monkeypatch.setattr(mig, "OLD_DATA_ROOT", box["old_data_root"])
    monkeypatch.setenv("AGENTBOX_CONFIG", box["config_root"])
    monkeypatch.setenv("AGENTBOX_DATA", box["data_root"])
    monkeypatch.setenv("DAGSTER_HOME", box["dagster_root"])

    before = snapshot(os.path.dirname(box["product_root"]))
    rc = mig.main([])                                  # dry run
    after = snapshot(os.path.dirname(box["product_root"]))

    assert rc == 0
    assert before == after
    assert "Dry run" in capsys.readouterr().out


# --- R-MIG-2: clobber refusal ---------------------------------------------------------------
def test_clobber_refuses_and_changes_nothing(box, monkeypatch, capsys):
    # Pre-populate one destination (as a half-finished prior migration would).
    dest = Path(box["config_root"], "agents")
    dest.mkdir(parents=True)
    (dest / "leftover.yaml").write_text("name: leftover\n", encoding="utf-8")

    monkeypatch.setattr(mig, "PRODUCT_ROOT", box["product_root"])
    monkeypatch.setattr(mig, "OLD_DATA_ROOT", box["old_data_root"])
    monkeypatch.setenv("AGENTBOX_CONFIG", box["config_root"])
    monkeypatch.setenv("AGENTBOX_DATA", box["data_root"])
    monkeypatch.setenv("DAGSTER_HOME", box["dagster_root"])

    before = snapshot(os.path.dirname(box["product_root"]))
    rc = mig.main(["--apply"])                          # refuses even with --apply
    after = snapshot(os.path.dirname(box["product_root"]))

    out = capsys.readouterr().out
    assert rc == 1
    assert "REFUSING" in out
    assert str(dest) in out                             # names the blocking destination
    assert before == after                             # nothing changed


def test_build_plan_flags_blocker(box):
    Path(box["config_root"], "agents").mkdir(parents=True)
    Path(box["config_root"], "agents", "x.yaml").write_text("y\n", encoding="utf-8")
    plan = mig.build_plan(**box)
    assert any(b.dst == f"{box['config_root']}/agents" for b in plan.blockers)


# --- Apply performs the migration -----------------------------------------------------------
def test_apply_performs_moves_rewrites_symlink(box):
    plan = mig.build_plan(**box)
    mig.apply_plan(plan, **box)

    p, od, cfg, dat, dag = (box["product_root"], box["old_data_root"], box["config_root"],
                            box["data_root"], box["dagster_root"])

    # Config + state relocated; sources gone.
    assert Path(cfg, "agents", "repo.yaml").exists()
    assert Path(cfg, "prompts", "repo.md").exists()
    assert Path(cfg, "settings.yaml").exists()
    assert not Path(p, "agents").exists()
    assert not Path(p, "prompts").exists()
    assert Path(dat, "outputs", "repo", "result.txt").read_text() == "R\n"
    assert Path(dat, "runs", "repo", "2026-01-01", "run.jsonl").exists()

    # Rewrite happened at the new location, preserving the inline comment.
    moved = Path(cfg, "agents", "repo.yaml").read_text()
    assert f"output_dir: {dat}/outputs/repo  # out" in moved
    assert f"workspace: {dat}/workspaces/repo  # ws" in moved
    # An already-migrated value is left byte-for-byte intact.
    assert Path(cfg, "agents", "already.yaml").read_text() == f"name: already\noutput_dir: {dat}/outputs/already\n"

    # Compatibility symlink at the old agent-logs location resolves to the new runs dir.
    link = Path(dag, "agent-logs")
    assert link.is_symlink() and os.readlink(link) == f"{dat}/runs"

    # Left-untouched things are still where they were.
    assert Path(od, "logs", "boot.log").exists()
    assert Path(dag, "storage", "run-x", "compute_logs", "step.err").exists()
