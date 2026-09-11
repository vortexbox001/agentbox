"""Tests for ui/automation_store.py — per-agent triggers read/validate/write (spec 006, US3)."""
import textwrap

import pytest

import automation_store as a
import agents_store


JOB_AGENT = """\
# agentbox-schema: 4
name: {name}
enabled: {enabled}
harness: api
model: cheap
prompt_file: p.md
output_dir: /data/outputs/{name}
job: true
"""

ASSET_AGENT = """\
# agentbox-schema: 4
name: asset-agent
enabled: true
harness: api
model: cheap
prompt_file: p.md
output_dir: /data/outputs/asset-agent
produces:
  asset: repo-review/agentbox
  partition: daily
"""

BOTH_AGENT = """\
# agentbox-schema: 4
name: both-agent
enabled: true
harness: api
model: cheap
prompt_file: p.md
output_dir: /data/outputs/both-agent
job: true
produces:
  asset: repo-review/both
  partition: none
"""


@pytest.fixture
def repo(settings, tmp_agents):
    # Start from a clean, controlled agent set (drop the copied real ones for determinism).
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    (tmp_agents / "job-agent.yaml").write_text(JOB_AGENT.format(name="job-agent", enabled="true"))
    (tmp_agents / "off-agent.yaml").write_text(JOB_AGENT.format(name="off-agent", enabled="false"))
    (tmp_agents / "asset-agent.yaml").write_text(textwrap.dedent(ASSET_AGENT))
    (tmp_agents / "both-agent.yaml").write_text(textwrap.dedent(BOTH_AGENT))
    (tmp_agents / "_template-api.yaml").write_text(JOB_AGENT.format(name="my-agent", enabled="false"))
    return tmp_agents


# --- per_agent_view: per-kind rows ------------------------------------------

def test_view_lists_non_template_agents(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert set(rows) == {"job-agent", "off-agent", "asset-agent", "both-agent"}  # template excluded


def test_view_reports_kinds_per_agent(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert rows["job-agent"]["kinds"] == ["job"]
    assert rows["asset-agent"]["kinds"] == ["asset"]
    assert rows["both-agent"]["kinds"] == ["asset", "job"]


def test_view_emits_one_schedule_row_per_kind(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert [s["kind"] for s in rows["both-agent"]["schedules"]] == ["asset", "job"]
    # on-demand by default: cron is null
    assert all(s["cron"] is None for s in rows["both-agent"]["schedules"])


def test_view_includes_disabled_agents(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert rows["off-agent"]["enabled"] is False
    assert rows["job-agent"]["enabled"] is True


def test_view_reflects_written_cron_off_the_agent_file(repo):
    a.write({"job-agent": {"job_schedule": "30 2 * * *"}})
    rows = {r["name"]: r for r in a.per_agent_view()}
    job_row = next(s for s in rows["job-agent"]["schedules"] if s["kind"] == "job")
    assert job_row["cron"] == "30 2 * * *"


def test_asset_fallback_marker_off_by_default(repo):
    a.write({"asset-agent": {"asset_schedule": "20 17 * * *"}})
    rows = {r["name"]: r for r in a.per_agent_view()}
    asset_row = next(s for s in rows["asset-agent"]["schedules"] if s["kind"] == "asset")
    assert asset_row["cron"] == "20 17 * * *"
    assert asset_row["fallback"] is False  # primary on_cron path ships by default


def test_asset_fallback_marker_when_forced(repo, monkeypatch):
    monkeypatch.setenv("AGENTBOX_PARTITION_FALLBACK", "1")
    a.write({"asset-agent": {"asset_schedule": "20 17 * * *"}})
    rows = {r["name"]: r for r in a.per_agent_view()}
    asset_row = next(s for s in rows["asset-agent"]["schedules"] if s["kind"] == "asset")
    assert asset_row["fallback"] is True  # daily partition + forced fallback


# --- validate ---------------------------------------------------------------

def test_validate_accepts_valid_per_kind(repo):
    a.validate({"job-agent": {"job_schedule": "30 2 * * *"}, "asset-agent": {"asset_schedule": "20 17 * * *"}})


def test_validate_rejects_unknown_agent(repo):
    with pytest.raises(a.AutomationError) as e:
        a.validate({"ghost": {"job_schedule": "30 2 * * *"}})
    assert e.value.field == "ghost" and "no agent" in e.value.message


def test_validate_rejects_invalid_cron(repo):
    with pytest.raises(a.AutomationError) as e:
        a.validate({"job-agent": {"job_schedule": "@daily"}})
    assert e.value.field == "job-agent"


def test_validate_rejects_off_kind_schedule(repo):
    # asset_schedule on a job-only agent, and job_schedule on an asset-only agent.
    with pytest.raises(a.AutomationError) as e:
        a.validate({"job-agent": {"asset_schedule": "30 2 * * *"}})
    assert e.value.field == "job-agent"
    with pytest.raises(a.AutomationError) as e2:
        a.validate({"asset-agent": {"job_schedule": "30 2 * * *"}})
    assert e2.value.field == "asset-agent"


def test_validate_allows_clearing_any_schedule(repo):
    # Setting a schedule to null (on-demand) is always allowed, even off-kind.
    a.validate({"job-agent": {"asset_schedule": None}, "asset-agent": {"job_schedule": None}})


# --- write: edits agents/*.yaml, never a separate store ---------------------

def test_write_persists_onto_agent_file(repo):
    a.write({"job-agent": {"job_schedule": "30 2 * * *"}})
    agent = agents_store.read_agent("job-agent")["agent"]
    assert agent["job_schedule"] == "30 2 * * *"
    # written into the triggers block of the agent file itself
    assert "triggers:" in (repo / "job-agent.yaml").read_text()


def test_write_clears_schedule_when_set_to_manual(repo):
    a.write({"job-agent": {"job_schedule": "30 2 * * *"}})
    a.write({"job-agent": {"job_schedule": None}})   # null = manual / no schedule
    agent = agents_store.read_agent("job-agent")["agent"]
    assert not agent.get("job_schedule")


def test_write_leaves_the_other_schedule_untouched(repo):
    # Editing the job schedule of a both-kind agent must not disturb its asset schedule (FR-020).
    a.write({"both-agent": {"asset_schedule": "20 17 * * *"}})
    a.write({"both-agent": {"job_schedule": "30 2 * * *"}})
    agent = agents_store.read_agent("both-agent")["agent"]
    assert agent["asset_schedule"] == "20 17 * * *"
    assert agent["job_schedule"] == "30 2 * * *"


def test_write_does_not_touch_a_separate_trigger_store(repo, tmp_path):
    a.write({"job-agent": {"job_schedule": "30 2 * * *"}})
    # the retired standalone store is never written: nothing lands beside the agents dir
    stray = tmp_path / "automation"
    assert not stray.exists() or list(stray.iterdir()) == []
    assert not hasattr(a, "_migrated_path")


# --- shared cron rule (twin of orchestrator is_valid_cron) ------------------

@pytest.mark.parametrize("cron,ok", [
    ("30 2 * * *", True), ("*/30 * * * *", True),
    ("@daily", False), ("1 2 3", False), ("1 2 3 4 5 6", False), ("", False), (None, False),
    ("99 2 * * *", False),  # croniter catches out-of-range (stricter UI guard)
])
def test_is_valid_cron(cron, ok):
    assert a.is_valid_cron(cron) is ok
