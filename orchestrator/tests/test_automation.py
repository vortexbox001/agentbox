"""Unit tests for spec-005 automation triggering (US1, US4, US5, US6).

Drives ``definitions.discover(agents_glob, automation_glob)`` and ``factory`` helpers
against temp agent + automation dirs, so schedule/condition/sensor wiring and the
naming-rejection paths are tested without a live Dagster or the container path.
"""
import textwrap

import pytest

import definitions
import factory
from dagster import DefaultScheduleStatus, DefaultSensorStatus


def _write(d, stem, body):
    (d / f"{stem}.yaml").write_text(textwrap.dedent(body))


@pytest.fixture
def dirs(tmp_path):
    agents = tmp_path / "agents"; agents.mkdir()
    automation = tmp_path / "automation"; automation.mkdir()
    return agents, automation


def _discover(agents, automation):
    return definitions.discover(str(agents / "*.yaml"), str(automation / "*.yaml"))


JOB = """\
    name: plain-job
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/plain-job
"""

ASSET = """\
    name: repo-review-agentbox
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/repo-review/agentbox
    produces:
      asset: repo-review/agentbox
      partition: daily
"""


# --- US1: job-mode cron -> paused schedule; on_demand/absent -> none ---------

def test_job_cron_becomes_paused_schedule(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "migrated", 'plain-job:\n  cron: "30 2 * * *"\n')
    out = _discover(agents, automation)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert len(out["schedules"]) == 1
    sched = out["schedules"][0]
    assert sched.name == "sched_plain_job"
    assert sched.cron_schedule == "30 2 * * *"
    assert sched.default_status == DefaultScheduleStatus.STOPPED  # FR-021: new triggers paused


def test_job_on_demand_has_no_schedule(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "migrated", "plain-job:\n  on_demand: true\n")
    out = _discover(agents, automation)
    assert out["schedules"] == [] and [j.name for j in out["jobs"]] == ["agent_plain_job"]


def test_absent_entry_is_on_demand(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)  # no automation file mentions it
    out = _discover(agents, automation)
    assert out["schedules"] == [] and out["sensors"] == []


def test_multiple_automation_files_merge(dirs):
    agents, automation = dirs
    _write(agents, "a", JOB.replace("plain-job", "a"))
    _write(agents, "b", JOB.replace("plain-job", "b"))
    _write(automation, "one", 'a:\n  cron: "0 1 * * *"\n')
    _write(automation, "two", 'b:\n  cron: "0 2 * * *"\n')
    out = _discover(agents, automation)
    assert {s.name for s in out["schedules"]} == {"sched_a", "sched_b"}


def test_stray_schedule_key_ignored_and_warned(dirs, caplog):
    agents, automation = dirs
    _write(agents, "plain-job", JOB + '    schedule: "0 7 * * *"\n')
    with caplog.at_level("WARNING"):
        out = _discover(agents, automation)
    assert out["schedules"] == []  # the stray key is NOT turned into a trigger (R7)
    assert any("agents/plain-job.yaml" in r.message and "schedule" in r.message for r in caplog.records)


# --- crons honor TZ, not UTC (both surfaces) --------------------------------

def test_cron_uses_tz_not_utc(dirs, monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(agents, "asset-agent", ASSET.replace("repo-review-agentbox", "asset-agent")
           .replace("repo-review/agentbox", "a/b"))
    _write(automation, "m", 'plain-job:\n  cron: "7 17 * * *"\nasset-agent:\n  cron: "7 17 * * *"\n')
    out = _discover(agents, automation)
    assert out["schedules"][0].execution_timezone == "America/New_York"
    cond = next(iter(out["assets"][0].automation_conditions_by_key.values()))
    assert "America/New_York" in str(cond)


def test_cron_falls_back_to_utc(dirs, monkeypatch):
    monkeypatch.delenv("TZ", raising=False)
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "m", 'plain-job:\n  cron: "7 17 * * *"\n')
    assert _discover(agents, automation)["schedules"][0].execution_timezone == "UTC"


# --- US4: asset-mode cron -> automation condition + paused sensor ------------

def test_asset_cron_becomes_condition_and_sensor(dirs):
    agents, automation = dirs
    _write(agents, "repo-review-agentbox", ASSET)
    _write(automation, "migrated", 'repo-review-agentbox:\n  cron: "30 2 * * *"\n')
    out = _discover(agents, automation)
    assert len(out["assets"]) == 1 and out["schedules"] == []  # asset, not a ScheduleDefinition
    conds = out["assets"][0].automation_conditions_by_key
    assert conds and "on_cron(30 2 * * *" in str(next(iter(conds.values())))
    assert [s.name for s in out["sensors"]] == ["autocond_repo_review_agentbox"]
    assert out["sensors"][0].default_status == DefaultSensorStatus.STOPPED  # FR-021


def test_asset_on_demand_has_no_condition_or_sensor(dirs):
    agents, automation = dirs
    _write(agents, "repo-review-agentbox", ASSET)  # no automation entry
    out = _discover(agents, automation)
    assert len(out["assets"]) == 1 and out["sensors"] == []
    assert list(out["assets"][0].automation_conditions_by_key.values()) in ([], [None]) \
        or all(v is None for v in out["assets"][0].automation_conditions_by_key.values())


def test_on_cron_targets_latest_partition(dirs):
    # Null Action (R5/T029): on_cron on a daily-partitioned root asset targets the latest
    # time window (current day), so the primary path materializes the right partition.
    asset = factory.build_asset(
        {"name": "x", "harness": "api", "model": "cheap", "prompt_file": "x.md",
         "output_dir": "/o", "produces": {"asset": "a/b", "partition": "daily"}},
        "agents/x.yaml", cron="30 2 * * *",
    )
    cond = next(iter(asset.automation_conditions_by_key.values()))
    assert "InLatestTimeWindow" in str(cond)


# --- US5: deleting an entry leaves the agent runnable, just not triggered ----

def test_delete_entry_keeps_job_runnable(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    # entry present -> schedule
    _write(automation, "migrated", 'plain-job:\n  cron: "30 2 * * *"\n')
    assert len(_discover(agents, automation)["schedules"]) == 1
    # entry removed -> still a job, no schedule
    (automation / "migrated.yaml").write_text("{}\n")
    out = _discover(agents, automation)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"] and out["schedules"] == []


# --- US6: bad entries rejected by name --------------------------------------

def test_unknown_agent_entry_fails_reload_by_name(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "migrated", 'nope-not-an-agent:\n  cron: "0 0 * * *"\n')
    with pytest.raises(definitions.RejectAutomation) as e:
        _discover(agents, automation)
    assert "nope-not-an-agent" in str(e.value) and "automation/migrated.yaml" in str(e.value)


def test_duplicate_agent_across_files_fails_by_name(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "one", 'plain-job:\n  cron: "0 1 * * *"\n')
    _write(automation, "two", 'plain-job:\n  cron: "0 2 * * *"\n')
    with pytest.raises(definitions.RejectAutomation) as e:
        _discover(agents, automation)
    msg = str(e.value)
    assert "plain-job" in msg and "automation/one.yaml" in msg and "automation/two.yaml" in msg


def test_both_triggers_rejected(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "migrated", 'plain-job:\n  cron: "0 1 * * *"\n  on_demand: true\n')
    with pytest.raises(definitions.RejectAutomation):
        _discover(agents, automation)


def test_invalid_cron_rejected_by_name(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB)
    _write(automation, "migrated", 'plain-job:\n  cron: "@daily"\n')
    with pytest.raises(definitions.RejectAutomation) as e:
        _discover(agents, automation)
    assert "plain-job" in str(e.value)


# --- disabled/template agents are "known" (contract §3 / FR-010) -------------

def test_entry_for_disabled_agent_is_known_not_dangling(dirs):
    agents, automation = dirs
    _write(agents, "plain-job", JOB + "    enabled: false\n")
    _write(automation, "migrated", 'plain-job:\n  cron: "30 2 * * *"\n')
    out = _discover(agents, automation)  # must NOT raise (the file exists)
    assert out["jobs"] == [] and out["schedules"] == []  # disabled -> skipped, entry attaches to nothing


# --- shared cron rule -------------------------------------------------------

@pytest.mark.parametrize("cron,ok", [
    ("30 2 * * *", True), ("0 7 * * *", True),
    ("@daily", False), ("1 2 3", False), ("1 2 3 4 5 6", False), ("", False), (None, False),
])
def test_is_valid_cron(cron, ok):
    assert factory.is_valid_cron(cron) is ok
