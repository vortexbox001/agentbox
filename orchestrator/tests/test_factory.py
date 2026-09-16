"""Unit tests for the asset half of orchestrator/factory.py (US1).

All container launches are stubbed by the ``stub_launch`` fixture (conftest.py), so
these exercise ``build_asset``, op naming, partition-as-label, and the before/after
output snapshot without ever running ``docker run``.
"""
import os
import re

import pytest
from dagster import (
    DailyPartitionsDefinition, TimeWindowPartitionMapping, AssetKey, DagsterInstance, materialize,
)

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


# --- validate_depends_on: load-time shape backstop (spec 013, contract agent-model §5) ------

def test_validate_depends_on_returns_keys_when_valid(tmp_path):
    cfg = _api_cfg(tmp_path, produces={"asset": "refined/daily", "partition": "daily",
                                       "depends_on": ["notes/daily", "extras/daily"]})
    assert factory.validate_depends_on(cfg, "agents/x.yaml") == ["notes/daily", "extras/daily"]


def test_validate_depends_on_absent_is_empty(tmp_path):
    assert factory.validate_depends_on(_api_cfg(tmp_path), "agents/x.yaml") == []


def test_validate_depends_on_rejects_non_list_naming_file(tmp_path):
    cfg = _api_cfg(tmp_path, produces={"asset": "refined/daily", "depends_on": "notes/daily"})
    with pytest.raises(factory.RejectAgent) as ei:
        factory.validate_depends_on(cfg, "agents/bad.yaml")
    assert "agents/bad.yaml" in str(ei.value)


def test_validate_depends_on_rejects_bad_entry_naming_file(tmp_path):
    cfg = _api_cfg(tmp_path, produces={"asset": "refined/daily", "depends_on": ["notes/daily", "Bad Key"]})
    with pytest.raises(factory.RejectAgent) as ei:
        factory.validate_depends_on(cfg, "agents/bad.yaml")
    assert "agents/bad.yaml" in str(ei.value) and "Bad Key" in str(ei.value)


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


# --- build_materializing_job: the both-kind agent_<name> (US1, FR-006) ------

def test_materializing_job_selects_the_asset(tmp_path):
    cfg = _api_cfg(tmp_path)
    asset = factory.build_asset(cfg)
    mjob = factory.build_materializing_job(cfg, asset)
    assert mjob.name == "agent_repo_review_agentbox"
    # it is an asset-selection job over the agent's asset (not a plain op job)
    sel = str(mjob.selection)
    assert "repo-review" in sel or "agentbox" in sel


def test_build_schedule_works_on_materializing_job(tmp_path):
    cfg = _api_cfg(tmp_path)
    mjob = factory.build_materializing_job(cfg, factory.build_asset(cfg))
    sched = factory.build_schedule(mjob, "30 2 * * *")
    assert sched.name == "sched_repo_review_agentbox"
    assert sched.cron_schedule == "30 2 * * *"


def test_partition_on_cron_supported_default_and_forced(monkeypatch):
    monkeypatch.delenv("AGENTBOX_PARTITION_FALLBACK", raising=False)
    assert factory.partition_on_cron_supported() is True
    monkeypatch.setenv("AGENTBOX_PARTITION_FALLBACK", "1")
    assert factory.partition_on_cron_supported() is False


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


# ── US1: depends_on → deps, composed condition, sensor gate (spec 013) ──────

def _upstream_cfg(tmp_path, **over):
    """A daily api-harness asset with a depends_on edge onto notes/daily."""
    return _api_cfg(tmp_path, produces={"asset": "refined/daily", "partition": "daily",
                                        "depends_on": ["notes/daily"]}, **over)


def test_depends_on_attaches_checkless_dep(tmp_path):
    ad = factory.build_asset(_upstream_cfg(tmp_path), depends_on=["notes/daily"], on_upstream=True)
    assert AssetKey(["notes", "daily"]) in ad.dependency_keys


def test_depends_on_attaches_checked_dep_with_identity_mapping(tmp_path):
    cfg = _upstream_cfg(tmp_path)
    cfg["produces"]["checks"] = [{"name": "c", "command": "true"}]
    ad = factory.build_asset(cfg, depends_on=["notes/daily"], on_upstream=True)
    up = AssetKey(["notes", "daily"])
    assert up in ad.dependency_keys
    # daily → daily identity mapping on the checked path (contract §1, FR-007)
    assert isinstance(ad.get_partition_mapping(up), TimeWindowPartitionMapping)


def test_compose_condition_none_when_no_triggers():
    assert factory.compose_automation_condition(
        {"name": "x"}, cron=None, on_upstream=False, on_missing=False, partitioned=False) is None


def test_compose_condition_on_upstream_yields_any_deps_updated():
    cond = factory.compose_automation_condition(
        {"name": "x"}, cron="0 6 * * *", on_upstream=True, on_missing=False, partitioned=False)
    text = str(cond)
    assert "any_deps_updated" in text and "on_cron" in text and "in_progress" in text


def test_on_upstream_only_asset_gets_stopped_sensor(tmp_path):
    # An on_upstream-only asset (no cron) still has a sensor-driven condition, so it needs the
    # paused per-asset sensor (spec 013, R4).
    cfg = _upstream_cfg(tmp_path)
    assert factory.asset_has_automation_condition(
        {"name": cfg["name"]}, cron=None, on_upstream=True, on_missing=False, partitioned=True)
    ad = factory.build_asset(cfg, depends_on=["notes/daily"], on_upstream=True)
    sensor = factory.build_asset_automation_sensor({"name": cfg["name"]}, ad)
    from dagster import DefaultSensorStatus
    assert sensor.name == f"autocond_{cfg['name'].replace('-', '_')}"
    assert sensor.default_status == DefaultSensorStatus.STOPPED


def test_partition_upstream_supported_default_and_forced(monkeypatch):
    monkeypatch.delenv("AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY", raising=False)
    assert factory.partition_upstream_supported() is True
    monkeypatch.setenv("AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY", "1")
    assert factory.partition_upstream_supported() is False


def test_partitioned_on_upstream_fallback_drops_condition_and_warns(tmp_path, monkeypatch, caplog):
    # When partitioned upstream is unsupported, a daily on_upstream asset loads WITHOUT its upstream
    # condition and a load-warning names the asset (R2/FR-007).
    monkeypatch.setenv("AGENTBOX_UPSTREAM_UNPARTITIONED_ONLY", "1")
    cfg = _upstream_cfg(tmp_path)
    assert factory.compose_automation_condition(
        cfg, cron=None, on_upstream=True, on_missing=False, partitioned=True) is None
    import logging
    with caplog.at_level(logging.WARNING):
        factory.build_asset(cfg, "agents/refined-daily.yaml", depends_on=["notes/daily"],
                            on_upstream=True)
    assert any("refined/daily" in r.getMessage() and "on_upstream" in r.getMessage()
               for r in caplog.records)


def test_failed_producer_records_observation_not_materialization(tmp_path, stub_launch, monkeypatch):
    # FR-006 gating mechanism: a run whose producer fails records an AssetObservation, NOT a
    # materialization — so any_deps_updated() sees no new materialization and cannot fire a
    # downstream. (A failed blocking check likewise never greens the partition.)
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.report = {"status": "failed", "tokens_in": None, "tokens_out": None,
                          "turns": None, "cost_usd": None, "files_written": 0,
                          "transcript_path": None, "error": "boom", "notes": None}
    stub_launch.returncode = 1
    cfg = _upstream_cfg(tmp_path)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    ad = factory.build_asset(cfg, depends_on=["notes/daily"], on_upstream=True)
    instance = DagsterInstance.ephemeral()
    result = materialize([ad], partition_key="2026-09-09",
                         instance=instance, raise_on_error=False)
    assert not result.success
    # the observation is emitted via log_event (survives the raise) — read it off the event log.
    types = [r.dagster_event.event_type_value for r in instance.all_logs(result.run_id)
             if r.dagster_event]
    assert "ASSET_MATERIALIZATION" not in types
    assert types.count("ASSET_OBSERVATION") == 1


# ── US2: upstream handoff files + env vars (spec 013, contract §3) ───────────
import json as _json
import tempfile as _tempfile
from dagster import AssetMaterialization, MetadataValue, build_op_context


def test_upstream_env_key_and_slug_transforms():
    assert factory.upstream_env_key("notes/daily") == "NOTES_DAILY"
    assert factory.upstream_env_key("repo-review/list-commits") == "REPO_REVIEW_LIST_COMMITS"
    assert factory.upstream_key_slug("notes/daily") == "notes_daily"
    assert factory.upstream_key_slug("repo-review/list-commits") == "repo-review_list-commits"


def _handoff_cfg():
    return {"name": "refined-daily", "harness": "api", "model": "cheap", "prompt_file": "x.md",
            "output_dir": "/tmp/o",
            "produces": {"asset": "refined/daily", "partition": "daily",
                         "depends_on": ["notes/daily", "extras/daily"]}}


def _validate_handoff(doc):
    # structural validation against contracts/upstream-handoff.schema.json (required keys/types).
    required = {"asset_key", "partition", "materialized", "output_files", "report",
                "materialized_at", "chain_depth", "automated"}
    assert set(doc) == required
    assert isinstance(doc["asset_key"], str)
    assert isinstance(doc["materialized"], bool)
    assert isinstance(doc["output_files"], list)


def test_handoff_selects_matching_partition_and_names_env_var(tmp_path):
    inst = DagsterInstance.ephemeral()
    inst.report_runless_asset_event(AssetMaterialization(
        asset_key=AssetKey(["notes", "daily"]), partition="2026-09-09",
        metadata={"output_files": MetadataValue.json(["/data/out/a.md"]),
                  "status": MetadataValue.text("ok"), "tokens_in": MetadataValue.int(10)}))
    ctx = build_op_context(instance=inst, partition_key="2026-09-09")
    d = str(tmp_path / "up"); os.makedirs(d)
    env = factory.build_upstream_handoff(_handoff_cfg(), ctx, d)
    # one env var per declared upstream, upper-snaked
    assert env["AGENTBOX_UPSTREAM_NOTES_DAILY"] == "/upstreams/notes_daily.json"
    assert env["AGENTBOX_UPSTREAM_EXTRAS_DAILY"] == "/upstreams/extras_daily.json"
    doc = _json.load(open(os.path.join(d, "notes_daily.json")))
    _validate_handoff(doc)
    assert doc["materialized"] is True
    assert doc["partition"] == "2026-09-09"
    assert doc["output_files"] == ["/data/out/a.md"]
    assert doc["report"]["status"] == "ok"
    # files are world-readable so the non-root container can read them
    assert (os.stat(os.path.join(d, "notes_daily.json")).st_mode & 0o644) == 0o644


def test_handoff_no_materialization_writes_null_file(tmp_path):
    inst = DagsterInstance.ephemeral()  # nothing materialized
    ctx = build_op_context(instance=inst, partition_key="2026-09-09")
    d = str(tmp_path / "up"); os.makedirs(d)
    factory.build_upstream_handoff(_handoff_cfg(), ctx, d)
    doc = _json.load(open(os.path.join(d, "extras_daily.json")))
    _validate_handoff(doc)
    assert doc["materialized"] is False
    assert doc["output_files"] == [] and doc["report"] is None
    assert doc["materialized_at"] is None and doc["chain_depth"] is None


def test_handoff_selects_latest_of_many(tmp_path):
    inst = DagsterInstance.ephemeral()
    for n in (1, 2, 3):
        inst.report_runless_asset_event(AssetMaterialization(
            asset_key=AssetKey(["notes", "daily"]), partition="2026-09-09",
            metadata={"output_files": MetadataValue.json([f"/data/out/{n}.md"]),
                      "status": MetadataValue.text("ok")}))
    ctx = build_op_context(instance=inst, partition_key="2026-09-09")
    d = str(tmp_path / "up"); os.makedirs(d)
    factory.build_upstream_handoff(_handoff_cfg(), ctx, d)
    doc = _json.load(open(os.path.join(d, "notes_daily.json")))
    assert doc["output_files"] == ["/data/out/3.md"]  # newest wins


def test_launch_snapshot_carries_upstream_mount_and_env(tmp_path, stub_launch, monkeypatch):
    # An end-to-end materialize records the :ro /upstreams mount and the AGENTBOX_UPSTREAM_* env
    # names in the launch (contract §3, FR-013).
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path, produces={"asset": "refined/daily", "partition": "daily",
                                       "depends_on": ["notes/daily"]}, name="refined-daily")
    os.makedirs(cfg["output_dir"], exist_ok=True)
    ad = factory.build_asset(cfg, depends_on=["notes/daily"], on_upstream=True)
    result = materialize([ad], partition_key="2026-09-09",
                         instance=DagsterInstance.ephemeral())
    assert result.success
    argv = stub_launch.cmd
    # the read-only handoff mount is present, and the env var was passed to the container
    assert any(str(a).endswith(":/upstreams:ro") for a in argv)
    assert any("AGENTBOX_UPSTREAM_NOTES_DAILY=" in str(a) for a in argv)
