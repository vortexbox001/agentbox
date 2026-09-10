"""Unit tests for the asset half of orchestrator/factory.py (US1).

All container launches are stubbed by the ``stub_launch`` fixture (conftest.py), so
these exercise ``build_asset``, op naming, partition-as-label, and the before/after
output snapshot without ever running ``docker run``.
"""
import os
import re

import pytest
from dagster import DailyPartitionsDefinition, materialize

import factory

# The asset-key regex is stated once per package (research R6). These shared fixtures are
# duplicated verbatim in ui/tests/test_schema.py so the two copies cannot drift silently.
ASSET_KEY_EXPECTED_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"
ASSET_KEY_ACCEPT = ["repo-review/agentbox", "code-map/agentbox", "a", "a-b/c-d/e", "x1/y2"]
ASSET_KEY_REJECT = ["Bad Key", "", "/leading", "trailing/", "Repo/Agentbox", "a//b",
                    "a_b", "a b", "-x", "x-", "a-/b"]


def test_asset_key_regex_pinned_to_shared_fixtures():
    assert factory.ASSET_KEY_RE == ASSET_KEY_EXPECTED_RE
    for s in ASSET_KEY_ACCEPT:
        assert re.match(factory.ASSET_KEY_RE, s), f"should accept {s!r}"
    for s in ASSET_KEY_REJECT:
        assert not re.match(factory.ASSET_KEY_RE, s), f"should reject {s!r}"


def _api_cfg(tmp_path, **over):
    """A minimal, materializable api-harness cfg with a produces block."""
    cfg = {
        "name": "repo-review-agentbox",
        "harness": "api",
        "model": "cheap",
        "prompt_file": "x.md",
        "output_dir": str(tmp_path / "out"),
        "produces": {"asset": "repo-review/agentbox", "partition": "daily"},
    }
    cfg.update(over)
    return cfg


# --- build_asset: key, step name, partitions --------------------------------

def test_build_asset_key_equals_split_path(tmp_path):
    ad = factory.build_asset(_api_cfg(tmp_path))
    assert [k.path for k in ad.keys] == [["repo-review", "agentbox"]]


def test_build_asset_step_name_is_run_name(tmp_path):
    # FR-010: the compute step keeps the op's run_<name> name in asset-mode.
    ad = factory.build_asset(_api_cfg(tmp_path))
    assert ad.op.name == "run_repo_review_agentbox"


def test_partition_daily_attaches_daily_partitions(tmp_path):
    ad = factory.build_asset(_api_cfg(tmp_path))
    assert isinstance(ad.partitions_def, DailyPartitionsDefinition)
    assert ad.partitions_def.start.strftime("%Y-%m-%d") == factory.PARTITION_START_DATE


def test_partition_none_attaches_no_partitions(tmp_path):
    ad = factory.build_asset(_api_cfg(tmp_path, produces={"asset": "repo-review/agentbox", "partition": "none"}))
    assert ad.partitions_def is None


def test_partition_omitted_attaches_no_partitions(tmp_path):
    ad = factory.build_asset(_api_cfg(tmp_path, produces={"asset": "repo-review/agentbox"}))
    assert ad.partitions_def is None


# --- Partition is a label only (FR-008b) ------------------------------------

def test_partition_key_never_injected_into_launch(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    ad = factory.build_asset(cfg)
    result = materialize([ad], partition_key="2026-09-09")
    assert result.success
    argv = stub_launch.cmd
    # the partition date reaches metadata only — never the command, mounts, or output_dir
    assert not any("2026-09-09" in str(a) for a in argv)
    assert f"{cfg['output_dir']}:/output" in argv


# --- Materialization metadata (FR-008) --------------------------------------

def _materialization_metadata(result):
    events = result.get_asset_materialization_events()
    assert events, "no materialization event"
    return events[0].step_materialization_data.materialization.metadata


def test_materialization_records_expected_metadata(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    ad = factory.build_asset(cfg)
    result = materialize([ad], partition_key="2026-09-09")
    md = _materialization_metadata(result)
    assert set(md) >= {"output_files", "transcript", "run_stamp", "session_id", "harness", "model", "partition"}
    assert md["harness"].value == "api"
    assert md["model"].value == "cheap"
    assert md["partition"].value == "2026-09-09"


# --- Before/after output snapshot (FR-008a / research R4) --------------------

def test_snapshot_missing_dir_is_empty(tmp_path):
    assert factory._snapshot_dir(str(tmp_path / "nope")) == {}


def test_changed_files_detects_new_file(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    before = factory._snapshot_dir(str(d))
    (d / "new.md").write_text("hi")
    after = factory._snapshot_dir(str(d))
    assert factory._changed_files(before, after) == [str(d / "new.md")]


def test_changed_files_detects_mtime_change(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    f = d / "a.md"
    f.write_text("one")
    before = factory._snapshot_dir(str(d))
    # rewrite with a later mtime; content/size change is enough for the diff
    os.utime(f, (before[str(f)][0] + 10, before[str(f)][0] + 10))
    after = factory._snapshot_dir(str(d))
    assert factory._changed_files(before, after) == [str(f)]


def test_changed_files_empty_when_nothing_written(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    (d / "a.md").write_text("one")
    before = factory._snapshot_dir(str(d))
    after = factory._snapshot_dir(str(d))
    assert factory._changed_files(before, after) == []
