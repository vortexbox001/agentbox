"""Tests for ui/automation_store.py — the Automation view's read/validate/write (US3, US5, US6)."""
import textwrap

import pytest

import automation_store as a


AGENT = """\
name: {name}
enabled: {enabled}
harness: api
model: cheap
prompt_file: p.md
output_dir: /data/outputs/{name}
"""

ASSET_AGENT = """\
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


@pytest.fixture
def repo(settings, tmp_agents, tmp_automation):
    # Start from a clean, controlled agent set (drop the copied real ones for determinism).
    for f in tmp_agents.glob("*.yaml"):
        f.unlink()
    (tmp_agents / "job-agent.yaml").write_text(AGENT.format(name="job-agent", enabled="true"))
    (tmp_agents / "off-agent.yaml").write_text(AGENT.format(name="off-agent", enabled="false"))
    (tmp_agents / "asset-agent.yaml").write_text(textwrap.dedent(ASSET_AGENT))
    (tmp_agents / "_template-api.yaml").write_text(AGENT.format(name="my-agent", enabled="false"))
    return tmp_agents, tmp_automation


# --- per_agent_view ---------------------------------------------------------

def test_view_lists_non_template_agents_default_on_demand(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert set(rows) == {"job-agent", "off-agent", "asset-agent"}  # template excluded
    assert rows["job-agent"]["trigger"] == {"on_demand": True}
    assert rows["job-agent"]["mode"] == "job"
    assert rows["asset-agent"]["mode"] == "asset"  # declares produces (feature 004)


def test_view_includes_disabled_agents(repo):
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert "off-agent" in rows  # disabled agents are listed so a trigger can be pre-set
    assert rows["off-agent"]["enabled"] is False  # surfaced so the view can badge it
    assert rows["job-agent"]["enabled"] is True


def test_view_reflects_written_cron(repo):
    a.write({"job-agent": {"cron": "30 2 * * *"}})
    rows = {r["name"]: r for r in a.per_agent_view()}
    assert rows["job-agent"]["trigger"] == {"cron": "30 2 * * *"}


# --- validate ---------------------------------------------------------------

def test_validate_accepts_known_and_valid(repo):
    a.validate({"job-agent": {"cron": "30 2 * * *"}, "off-agent": {"on_demand": True}})


def test_validate_rejects_unknown_agent(repo):
    with pytest.raises(a.AutomationError) as e:
        a.validate({"ghost": {"cron": "30 2 * * *"}})
    assert e.value.field == "ghost" and "no agent" in e.value.message


def test_validate_rejects_invalid_cron(repo):
    with pytest.raises(a.AutomationError) as e:
        a.validate({"job-agent": {"cron": "@daily"}})
    assert e.value.field == "job-agent"


def test_validate_rejects_both_triggers(repo):
    with pytest.raises(a.AutomationError):
        a.validate({"job-agent": {"cron": "0 1 * * *", "on_demand": True}})


# --- write (US5: on-demand removes the entry, never touches agents/) ---------

def test_write_persists_cron_and_omits_on_demand(repo):
    tmp_agents, tmp_automation = repo
    a.write({"job-agent": {"cron": "30 2 * * *"}, "off-agent": {"on_demand": True}})
    import yaml
    entries = yaml.safe_load((tmp_automation / "migrated.yaml").read_text())
    assert entries == {"job-agent": {"cron": "30 2 * * *"}}  # on-demand omitted
    # no agent file was touched
    assert "cron" not in (tmp_agents / "job-agent.yaml").read_text()


def test_write_on_demand_removes_prior_entry(repo):
    tmp_agents, tmp_automation = repo
    a.write({"job-agent": {"cron": "30 2 * * *"}})
    a.write({"job-agent": {"on_demand": True}})  # switch back to on-demand
    import yaml
    entries = yaml.safe_load((tmp_automation / "migrated.yaml").read_text()) or {}
    assert "job-agent" not in entries


# --- load: duplicate key across files (FR-011) ------------------------------

def test_load_rejects_duplicate_across_files(repo):
    _, tmp_automation = repo
    (tmp_automation / "one.yaml").write_text('job-agent:\n  cron: "0 1 * * *"\n')
    (tmp_automation / "two.yaml").write_text('job-agent:\n  cron: "0 2 * * *"\n')
    with pytest.raises(a.AutomationError) as e:
        a.load()
    assert e.value.field == "job-agent"


# --- shared cron rule (twin of orchestrator is_valid_cron) ------------------

@pytest.mark.parametrize("cron,ok", [
    ("30 2 * * *", True), ("*/30 * * * *", True),
    ("@daily", False), ("1 2 3", False), ("1 2 3 4 5 6", False), ("", False), (None, False),
    ("99 2 * * *", False),  # croniter catches out-of-range (stricter UI guard)
])
def test_is_valid_cron(cron, ok):
    assert a.is_valid_cron(cron) is ok
