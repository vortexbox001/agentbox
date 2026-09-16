"""Context-snapshot builder tests (spec 012, T036 — contracts/context-snapshot.schema.json).

The builder must produce every FR-009/010/011 field, capture the image digest, and never write an
env value (FR-015). Validated against the JSON schema (dependency-free).
"""
import json
import os
from pathlib import Path

import pytest

import run_capture

SCHEMA = json.loads((
    Path(__file__).resolve().parents[2]
    / "specs" / "012-run-transparency" / "contracts" / "context-snapshot.schema.json"
).read_text())


def _assert_context_valid(ctx: dict) -> None:
    for req in SCHEMA["required"]:
        assert req in ctx, f"missing top-level group {req}"
    for req in SCHEMA["properties"]["prompt"]["required"]:
        assert req in ctx["prompt"]
    for req in SCHEMA["properties"]["harness"]["required"]:
        assert req in ctx["harness"]
    for req in SCHEMA["properties"]["runtime"]["required"]:
        assert req in ctx["runtime"]
    assert set(ctx["file_trees"]) >= {"workspace", "output"}
    for req in SCHEMA["properties"]["completeness"]["required"]:
        assert req in ctx["completeness"]


def _cfg(**over):
    cfg = {"name": "hello", "harness": "claude-code", "model": "sonnet", "prompt_file": "p.md",
           "allowed_tools": ["Read", "Write"], "permission_mode": "acceptEdits", "effort": "high"}
    cfg.update(over)
    return cfg


def test_build_context_has_every_group(tmp_path):
    ctx = run_capture.build_context(
        _cfg(),
        prompt_text="do the thing", append_system_prompt="write to /output",
        image_ref="agentbox/agent-claude:latest", image_digest="sha256:abc",
        env_names=["TZ", "CLAUDE_CONFIG_DIR"], mounts=[{"source": "/w", "target": "/workspace", "mode": "rw"}],
        network="agentnet", working_dir="/workspace",
        workspace_dir=None, output_dir=None, memory="1g", cpus="1.5",
    )
    _assert_context_valid(ctx)
    assert ctx["prompt"]["prompt_text"] == "do the thing"
    assert ctx["model"]["model"] == "sonnet" and ctx["model"]["effort"] == "high"
    assert ctx["harness"]["image_digest"] == "sha256:abc"
    assert ctx["tools"]["allowed_tools"] == ["Read", "Write"]
    assert ctx["tools"]["permission_mode"] == "acceptEdits"


def test_env_names_only_never_values(tmp_path):
    # build_context takes NAMES; there is no path by which a value can enter the snapshot (FR-015).
    ctx = run_capture.build_context(
        _cfg(), prompt_text="p", append_system_prompt=None,
        image_ref="r", image_digest="d",
        env_names=["OPENAI_API_KEY", "TZ", "TZ"],  # dedup + sort
        mounts=[], network="agentnet", working_dir=None,
        workspace_dir=None, output_dir=None,
    )
    assert ctx["runtime"]["env_names"] == ["OPENAI_API_KEY", "TZ"]
    # a value never appears anywhere
    assert "sk-" not in json.dumps(ctx)


def test_file_trees_capture_paths_and_sizes(tmp_path):
    ws = tmp_path / "ws"
    (ws / "sub").mkdir(parents=True)
    (ws / "a.txt").write_text("hello")
    (ws / "sub" / "b.txt").write_text("xy")
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.md").write_text("done")
    ctx = run_capture.build_context(
        _cfg(), prompt_text="p", append_system_prompt=None, image_ref="r", image_digest="d",
        env_names=[], mounts=[], network="n", working_dir="/workspace",
        workspace_dir=str(ws), output_dir=str(out),
    )
    ws_paths = {e["path"]: e["size"] for e in ctx["file_trees"]["workspace"]}
    assert ws_paths.get("a.txt") == 5
    assert ws_paths.get(os.path.join("sub", "b.txt")) == 2
    assert ctx["file_trees"]["output"][0]["path"] == "report.md"


def test_asset_fields_present_for_asset_run():
    ctx = run_capture.build_context(
        _cfg(), prompt_text="p", append_system_prompt=None, image_ref="r", image_digest="d",
        env_names=[], mounts=[], network="n", working_dir=None,
        workspace_dir=None, output_dir=None,
        asset={"asset_key": "repo-review/agentbox", "partition_key": "2026-09-15",
               "variant": None, "upstream_inputs": None, "attempt": 2},
    )
    assert ctx["asset"]["asset_key"] == "repo-review/agentbox"
    assert ctx["asset"]["attempt"] == 2


def test_completeness_scaffold_without_fragment_then_merge():
    ctx = run_capture.build_context(
        _cfg(), prompt_text="p", append_system_prompt=None, image_ref="r", image_digest="d",
        env_names=[], mounts=[], network="n", working_dir=None, workspace_dir=None, output_dir=None,
    )
    # without a fragment the snapshot is marked incomplete (fragment not captured yet)
    assert ctx["completeness"]["complete"] is False
    assert ctx["instruction_files"] == []
    # merging the image fragment fills instruction files, MCP tools, and completeness
    merged = run_capture.merge_fragment(ctx, {
        "instruction_files": [{"path": "/workspace/CLAUDE.md", "contents": "rules"}],
        "mcp_servers": [{"name": "github", "tools": ["create_issue"]}],
        "completeness": {"complete": False, "undisclosed": ["vendor base system prompt"],
                         "statement": "vendor prompt undisclosed"},
    })
    assert merged["instruction_files"][0]["contents"] == "rules"
    assert merged["tools"]["mcp_servers"][0]["name"] == "github"
    assert "vendor base system prompt" in merged["completeness"]["undisclosed"]


def test_launch_context_captures_image_digest(monkeypatch, tmp_path):
    # the orchestrator side (factory._launch_context) resolves + records the image digest (R10).
    import factory
    from dagster import build_op_context
    monkeypatch.setattr(factory, "_image_digest", lambda ref: "sha256:deadbeef")
    cfg = _cfg(harness="api", model="cheap")
    ctx = factory._launch_context(cfg, build_op_context(), "2026-09-15_10-00", "sess",
                                  str(tmp_path / "ws"), {}, is_asset=False)
    assert ctx["harness"]["image_ref"] == "agentbox/agent-python:latest"
    assert ctx["harness"]["image_digest"] == "sha256:deadbeef"
    # env values never captured — only names (FR-015)
    assert all(isinstance(n, str) for n in ctx["runtime"]["env_names"])


def test_launch_context_asset_upstream_inputs_from_op_config(monkeypatch, tmp_path):
    # asset.upstream_inputs is captured from the triggering run's op config (FR-011), so it is a
    # real handoff record rather than a hardcoded null.
    import factory
    from dagster import build_op_context
    monkeypatch.setattr(factory, "_image_digest", lambda ref: "sha256:x")
    cfg = _cfg(harness="api", model="cheap", produces={"asset": "repo-review/agentbox"})
    handoff = {"source_run": "abc123", "artifact": "/output/summary.md"}
    ctx = factory._launch_context(
        cfg, build_op_context(op_config={"inputs": handoff}), "2026-09-15_10-00", "sess",
        str(tmp_path / "ws"), {}, is_asset=True)
    assert ctx["asset"]["upstream_inputs"] == handoff


def test_launch_context_asset_no_handoff_is_none(monkeypatch, tmp_path):
    # No handoff → None, keeping "no upstream inputs" distinct from "not captured".
    import factory
    from dagster import build_op_context
    monkeypatch.setattr(factory, "_image_digest", lambda ref: "sha256:x")
    cfg = _cfg(harness="api", model="cheap", produces={"asset": "repo-review/agentbox"})
    ctx = factory._launch_context(
        cfg, build_op_context(), "2026-09-15_10-00", "sess", str(tmp_path / "ws"), {}, is_asset=True)
    assert ctx["asset"]["upstream_inputs"] is None


# ── US2: asset.upstream_inputs sourced from the handoff data (spec 013, R6) ──
def test_upstream_inputs_populated_from_handoff():
    import factory
    from dagster import build_op_context

    cfg = {"name": "refined-daily", "harness": "api", "model": "cheap", "prompt_file": "p.md",
           "produces": {"asset": "refined/daily", "partition": "daily",
                        "depends_on": ["notes/daily"]}}
    ctx = build_op_context(partition_key="2026-09-09")
    handoff = {"AGENTBOX_UPSTREAM_NOTES_DAILY": "/upstreams/notes_daily.json"}
    snapshot = factory._launch_context(cfg, ctx, "2026-09-09_00-00", "sid", "/ws", handoff, True,
                                       handoff_dir="/tmp/up", upstream_inputs=handoff)
    # the handoff map is the captured provenance (the file remains the launch-time transport)
    assert snapshot["asset"]["upstream_inputs"] == handoff


def test_upstream_inputs_none_when_no_handoff_and_no_op_config():
    import factory
    from dagster import build_op_context

    cfg = {"name": "refined", "harness": "api", "model": "cheap", "prompt_file": "p.md",
           "produces": {"asset": "refined/daily"}}
    ctx = build_op_context()
    snapshot = factory._launch_context(cfg, ctx, "2026-09-09_00-00", "sid", "/ws", {}, True)
    assert snapshot["asset"]["upstream_inputs"] is None
