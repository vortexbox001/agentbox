"""Unit tests for orchestrator/definitions.py — explicit asset/job nature + per-agent
triggers (spec 006, US1/US2).

``discover(agents_glob)`` is driven against a temp directory of agent YAML files so kind
routing (asset / job / both / neither) and trigger routing (asset_schedule → on_cron + sensor,
job_schedule → schedule) can be tested without the container path or a live Dagster. There is
no ``automation/`` store any more — triggering is read only from each agent's ``triggers:``
block.
"""
import logging
import textwrap

import pytest
from dagster import DefaultScheduleStatus, DefaultSensorStatus

import definitions
import factory


def _write(agents_dir, stem, body):
    (agents_dir / f"{stem}.yaml").write_text(textwrap.dedent(body))


@pytest.fixture
def agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    return d


def _discover(agents_dir):
    return definitions.discover(str(agents_dir / "*.yaml"))


JOB_AGENT = """\
    name: plain-job
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/plain-job
    job: true
"""

ASSET_AGENT = """\
    name: repo-review-agentbox
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/repo-review/agentbox
    produces:
      asset: repo-review/agentbox
      partition: daily
"""

BOTH_AGENT = """\
    name: both-agent
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/both-agent
    job: true
    produces:
      asset: repo-review/both
      partition: none
"""

NEITHER_AGENT = """\
    name: neither-agent
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/neither-agent
"""


# --- US1: three kinds route correctly ---------------------------------------

def test_asset_only_builds_asset_and_no_job(agents_dir):
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    out = _discover(agents_dir)
    assert [k.path for a in out["assets"] for k in a.keys] == [["repo-review", "agentbox"]]
    assert [j.name for j in out["jobs"]] == []  # no agent_<name> job for an asset-only agent


def test_job_only_builds_plain_job_and_no_asset(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT)
    out = _discover(agents_dir)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert out["assets"] == []


def test_both_builds_asset_and_materializing_job(agents_dir):
    _write(agents_dir, "both-agent", BOTH_AGENT)
    out = _discover(agents_dir)
    assert [k.path for a in out["assets"] for k in a.keys] == [["repo-review", "both"]]
    assert [j.name for j in out["jobs"]] == ["agent_both_agent"]
    # the job materializes the asset (an asset-selection job, not a plain op job)
    job = out["jobs"][0]
    assert "repo-review" in str(job.selection) or "both" in str(job.selection)


def test_neither_flag_agent_rejected_by_name(agents_dir, caplog):
    _write(agents_dir, "neither-agent", NEITHER_AGENT)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # the neither-agent is skipped by name; the good agent still loads
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert out["assets"] == []
    assert "agents/neither-agent.yaml" in caplog.text


def test_mixed_set_routes_each_correctly(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT)
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    _write(agents_dir, "both-agent", BOTH_AGENT)
    out = _discover(agents_dir)
    assert {j.name for j in out["jobs"]} == {"agent_plain_job", "agent_both_agent"}
    assert {tuple(k.path) for a in out["assets"] for k in a.keys} == {
        ("repo-review", "agentbox"), ("repo-review", "both"),
    }


def test_disabled_agent_skipped(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT + "    enabled: false\n")
    out = _discover(agents_dir)
    assert out["jobs"] == [] and out["assets"] == []


# --- US1: shared op name across kinds (SC / FR-008) -------------------------

def test_job_and_asset_share_the_same_op_name():
    cfg = {"name": "repo-review-agentbox", "harness": "api", "model": "cheap",
           "prompt_file": "x.md", "output_dir": "/o"}
    job = factory.build_job(cfg)
    asset = factory.build_asset(dict(cfg, produces={"asset": "repo-review/agentbox"}))
    assert job.name == "agent_repo_review_agentbox"
    assert job.graph.node_defs[0].name == "run_repo_review_agentbox"
    assert asset.op.name == "run_repo_review_agentbox"


def test_job_only_still_launches_unchanged(stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = {"name": "plain-job", "harness": "api", "model": "cheap",
           "prompt_file": "x.md", "output_dir": "/data/outputs/plain-job"}
    job = factory.build_job(cfg)
    result = job.execute_in_process()
    assert result.success
    assert f"{cfg['output_dir']}:/output" in stub_launch.cmd


# --- US2: trigger routing (read only from the agent's triggers block) --------

def test_job_schedule_becomes_paused_schedule_on_the_job(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT + '    triggers:\n      job_schedule: "30 2 * * *"\n')
    out = _discover(agents_dir)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert len(out["schedules"]) == 1
    sched = out["schedules"][0]
    assert sched.name == "sched_plain_job"
    assert sched.cron_schedule == "30 2 * * *"
    assert sched.default_status == DefaultScheduleStatus.STOPPED  # new triggers paused


def test_asset_schedule_becomes_condition_and_paused_sensor(agents_dir):
    _write(agents_dir, "repo-review-agentbox",
           ASSET_AGENT + '    triggers:\n      asset_schedule: "20 17 * * *"\n')
    out = _discover(agents_dir)
    assert len(out["assets"]) == 1 and out["schedules"] == []  # asset, not a ScheduleDefinition
    conds = out["assets"][0].automation_conditions_by_key
    assert conds and "on_cron(20 17 * * *" in str(next(iter(conds.values())))
    assert [s.name for s in out["sensors"]] == ["autocond_repo_review_agentbox"]
    assert out["sensors"][0].default_status == DefaultSensorStatus.STOPPED


def test_both_agent_asset_and_job_schedules_independent(agents_dir):
    body = BOTH_AGENT + '    triggers:\n      asset_schedule: "20 17 * * *"\n      job_schedule: "30 2 * * *"\n'
    _write(agents_dir, "both-agent", body)
    out = _discover(agents_dir)
    # asset gets the on_cron condition + a paused sensor; the materializing job gets sched_<name>
    conds = out["assets"][0].automation_conditions_by_key
    assert conds and "on_cron(20 17 * * *" in str(next(iter(conds.values())))
    assert [s.name for s in out["sensors"]] == ["autocond_both_agent"]
    assert [s.name for s in out["schedules"]] == ["sched_both_agent"]
    assert out["schedules"][0].cron_schedule == "30 2 * * *"


def test_no_triggers_means_no_schedule_or_sensor(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT)
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    out = _discover(agents_dir)
    assert out["schedules"] == [] and out["sensors"] == []


def test_absent_triggers_block_leaves_agent_runnable(agents_dir):
    # An agent with no triggers is still built (runnable by hand), just not triggered.
    _write(agents_dir, "plain-job", JOB_AGENT)
    out = _discover(agents_dir)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]


# --- crons honor TZ, not UTC (both surfaces, FR-016) ------------------------

def test_cron_uses_tz_not_utc(agents_dir, monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    _write(agents_dir, "plain-job", JOB_AGENT + '    triggers:\n      job_schedule: "7 17 * * *"\n')
    _write(agents_dir, "repo-review-agentbox",
           ASSET_AGENT + '    triggers:\n      asset_schedule: "7 17 * * *"\n')
    out = _discover(agents_dir)
    assert out["schedules"][0].execution_timezone == "America/New_York"
    cond = next(iter(out["assets"][0].automation_conditions_by_key.values()))
    assert "America/New_York" in str(cond)


def test_cron_falls_back_to_utc(agents_dir, monkeypatch):
    monkeypatch.delenv("TZ", raising=False)
    _write(agents_dir, "plain-job", JOB_AGENT + '    triggers:\n      job_schedule: "7 17 * * *"\n')
    assert _discover(agents_dir)["schedules"][0].execution_timezone == "UTC"


# --- state-preservation guard: names are unchanged from spec 005 -------------

def test_instigator_names_unchanged(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT + '    triggers:\n      job_schedule: "30 2 * * *"\n')
    _write(agents_dir, "repo-review-agentbox",
           ASSET_AGENT + '    triggers:\n      asset_schedule: "20 17 * * *"\n')
    out = _discover(agents_dir)
    assert {s.name for s in out["schedules"]} == {"sched_plain_job"}
    assert {s.name for s in out["sensors"]} == {"autocond_repo_review_agentbox"}


# --- US4-ish: invalid / duplicate produces still rejected by name ------------

BAD_KEY_AGENT = """\
    name: bad-key
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/bad-key
    produces:
      asset: "Bad Key"
"""

DUP_A = """\
    name: dup-a
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/dup-a
    produces:
      asset: shared/key
"""

DUP_B = DUP_A.replace("dup-a", "dup-b")


def test_invalid_asset_rejects_only_that_file(agents_dir, caplog):
    _write(agents_dir, "bad-key", BAD_KEY_AGENT)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/bad-key.yaml" in caplog.text and "Bad Key" in caplog.text


def test_duplicate_asset_keys_reject_all_by_name(agents_dir, caplog):
    _write(agents_dir, "dup-a", DUP_A)
    _write(agents_dir, "dup-b", DUP_B)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert 'asset key "shared/key"' in caplog.text
    assert "agents/dup-a.yaml" in caplog.text and "agents/dup-b.yaml" in caplog.text


# --- legacy automation path is gone (FR-010 / SC-008) -----------------------

def test_no_automation_reader_or_on_demand_remains():
    # The spec-005 automation machinery must be fully removed from the module.
    assert not hasattr(definitions, "load_automation")
    assert not hasattr(definitions, "AUTOMATION_GLOB")
    assert not hasattr(definitions, "RejectAutomation")
    src = open(definitions.__file__).read()
    assert "on_demand" not in src


# --- FR-015: partition Null-Action fallback (forced via env) -----------------

def test_partition_fallback_adds_filling_schedule_and_warns(agents_dir, monkeypatch, caplog):
    monkeypatch.setenv("AGENTBOX_PARTITION_FALLBACK", "1")
    _write(agents_dir, "repo-review-agentbox",
           ASSET_AGENT + '    triggers:\n      asset_schedule: "20 17 * * *"\n')
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # fallback: a materializing job is defined for the asset-only agent + a partition-filling
    # schedule on it; the on_cron sensor is NOT registered.
    assert [j.name for j in out["jobs"]] == ["agent_repo_review_agentbox"]
    assert [s.name for s in out["schedules"]] == ["sched_repo_review_agentbox"]
    assert out["sensors"] == []
    assert "FR-015" in caplog.text or "fall" in caplog.text.lower()


def test_primary_path_is_default(agents_dir, monkeypatch):
    monkeypatch.delenv("AGENTBOX_PARTITION_FALLBACK", raising=False)
    _write(agents_dir, "repo-review-agentbox",
           ASSET_AGENT + '    triggers:\n      asset_schedule: "20 17 * * *"\n')
    out = _discover(agents_dir)
    # primary: on_cron sensor, no job, no schedule
    assert out["jobs"] == [] and out["schedules"] == []
    assert [s.name for s in out["sensors"]] == ["autocond_repo_review_agentbox"]


# --- US5: checks require an asset; malformed checks reject the file by name --
# (contract check-execution §6, FR-010). One bad file is skipped by name; all others load.

CHECKS_NO_ASSET = """\
    name: checks-no-asset
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/checks-no-asset
    job: true
    produces:
      checks:
        - name: has-output
          command: "true"
"""

CHECKS_DUP_NAME = """\
    name: checks-dup
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/checks-dup
    produces:
      asset: verify/dup
      checks:
        - name: c
          command: "true"
        - name: c
          command: "false"
"""

CHECKS_MISSING_COMMAND = """\
    name: checks-nocmd
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/checks-nocmd
    produces:
      asset: verify/nocmd
      checks:
        - name: c
"""

CHECKS_MISSING_NAME = """\
    name: checks-noname
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/checks-noname
    produces:
      asset: verify/noname
      checks:
        - command: "true"
"""

VALID_CHECKS_AGENT = """\
    name: good-checks
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/good-checks
    produces:
      asset: verify/good
      checks:
        - name: has-output
          command: "test -n \\"$(ls /output)\\""
"""


def test_checks_without_asset_reject_only_that_file(agents_dir, caplog):
    _write(agents_dir, "checks-no-asset", CHECKS_NO_ASSET)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # the bad file is skipped by name; the good agent still loads
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/checks-no-asset.yaml" in caplog.text


def test_duplicate_check_names_reject_by_name(agents_dir, caplog):
    _write(agents_dir, "checks-dup", CHECKS_DUP_NAME)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/checks-dup.yaml" in caplog.text and "duplicate check name" in caplog.text


def test_check_missing_command_rejects_by_name(agents_dir, caplog):
    _write(agents_dir, "checks-nocmd", CHECKS_MISSING_COMMAND)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/checks-nocmd.yaml" in caplog.text


def test_check_missing_name_rejects_by_name(agents_dir, caplog):
    _write(agents_dir, "checks-noname", CHECKS_MISSING_NAME)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/checks-noname.yaml" in caplog.text


def test_valid_checks_agent_loads_as_asset(agents_dir):
    _write(agents_dir, "good-checks", VALID_CHECKS_AGENT)
    out = _discover(agents_dir)
    # a well-formed checks agent still builds its asset (with its asset checks)
    assert [tuple(k.path) for a in out["assets"] for k in a.keys] == [("verify", "good")]


def test_bad_checks_file_does_not_take_down_valid_checks_agent(agents_dir, caplog):
    _write(agents_dir, "checks-dup", CHECKS_DUP_NAME)
    _write(agents_dir, "good-checks", VALID_CHECKS_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # only the bad file is skipped; the valid checks agent still loads
    assert [tuple(k.path) for a in out["assets"] for k in a.keys] == [("verify", "good")]
    assert "agents/checks-dup.yaml" in caplog.text


# --- US4: dependency graph — cycle + dangling rejection at load (spec 013 §4) ------

def _asset(name, key, depends_on=None, partition="daily"):
    dep_lines = ""
    if depends_on:
        dep_lines = "\n  depends_on:\n" + "\n".join(f"    - {d}" for d in depends_on)
    return (
        f"name: {name}\n"
        "harness: api\nmodel: cheap\nprompt_file: x.md\n"
        f"output_dir: /data/outputs/{name}\n"
        "produces:\n"
        f"  asset: {key}\n"
        f"  partition: {partition}{dep_lines}\n"
    )


def _asset_keys(out):
    return {k.to_user_string() for ad in out["assets"] for k in ad.keys}


def test_acyclic_graph_loads_unchanged(agents_dir):
    _write(agents_dir, "notes", _asset("notes", "notes/daily"))
    _write(agents_dir, "refined", _asset("refined", "refined/daily", depends_on=["notes/daily"]))
    out = _discover(agents_dir)
    assert _asset_keys(out) == {"notes/daily", "refined/daily"}


def test_dangling_ref_rejects_that_agent_naming_the_key(agents_dir, caplog):
    _write(agents_dir, "notes", _asset("notes", "notes/daily"))
    _write(agents_dir, "refined", _asset("refined", "refined/daily", depends_on=["ghost/daily"]))
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # the dangling asset is skipped; the unrelated asset still loads
    assert _asset_keys(out) == {"notes/daily"}
    assert "agents/refined.yaml" in caplog.text and "ghost/daily" in caplog.text


def test_cycle_rejects_both_naming_them(agents_dir, caplog):
    _write(agents_dir, "bx", _asset("bx", "b/x", depends_on=["c/y"]))
    _write(agents_dir, "cy", _asset("cy", "c/y", depends_on=["b/x"]))
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert _asset_keys(out) == set()          # both cycle members rejected
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]   # unrelated job still loads
    assert "dependency cycle" in caplog.text and "b/x" in caplog.text and "c/y" in caplog.text


def test_cascade_rejects_dependents_of_a_rejected_asset(agents_dir, caplog):
    # d/z depends on refined/daily which dangles → refined AND d/z are both rejected; notes loads.
    _write(agents_dir, "notes", _asset("notes", "notes/daily"))
    _write(agents_dir, "refined", _asset("refined", "refined/daily", depends_on=["ghost/daily"]))
    _write(agents_dir, "dz", _asset("dz", "d/z", depends_on=["refined/daily"]))
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert _asset_keys(out) == {"notes/daily"}
    assert "agents/dz.yaml" in caplog.text


def test_bad_graph_produces_no_sensor(agents_dir):
    # A rejected cyclic asset gets no automation sensor — no automation runs against a bad graph.
    _write(agents_dir, "bx", _asset("bx", "b/x", depends_on=["c/y"]))
    _write(agents_dir, "cy", _asset("cy", "c/y", depends_on=["b/x"]))
    out = _discover(agents_dir)
    assert out["sensors"] == []


# ── spec 016: the on_project_status trigger wiring + load-time rejection ─────

PS_JOB_AGENT = """\
    name: board-job
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/board-job
    job: true
    triggers:
      on_project_status:
        owner: vortexbox001
        project: 1
        status: In progress
"""

PS_ASSET_AGENT = """\
    name: board-asset
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/board-asset
    produces:
      asset: board/asset
      partition: none
    triggers:
      on_project_status:
        owner: vortexbox001
        project: 1
        status: In progress
"""


def test_project_status_builds_sensor_for_job_and_asset(agents_dir):
    _write(agents_dir, "board-job", PS_JOB_AGENT)
    _write(agents_dir, "board-asset", PS_ASSET_AGENT)
    out = _discover(agents_dir)
    names = {s.name for s in out["sensors"]}
    assert "project_status_board_job" in names
    assert "project_status_board_asset" in names


def test_project_status_composes_with_existing_triggers(agents_dir):
    # An asset agent with both asset_schedule and on_project_status gets BOTH the autocond sensor
    # and the project-status sensor (composition, FR-002).
    body = PS_ASSET_AGENT.replace(
        "    triggers:\n      on_project_status:",
        "    triggers:\n      asset_schedule: \"0 9 * * *\"\n      on_project_status:")
    _write(agents_dir, "board-asset", body)
    out = _discover(agents_dir)
    names = {s.name for s in out["sensors"]}
    assert {"autocond_board_asset", "project_status_board_asset"} <= names


# ── US8: a malformed block rejects only that agent (FR-023) ─────────────────

@pytest.mark.parametrize("bad_block,frag", [
    ("        owner: o\n        status: In progress\n", "project"),      # missing project
    ("        owner: o\n        project: 0\n        status: In progress\n", "positive integer"),
    ("        owner: o\n        project: 1\n        status: In progress\n        interval_seconds: 10\n",
     "interval_seconds"),
    ("        owner: o\n        project: 1\n", "status"),                # missing status
])
def test_bad_block_rejects_only_that_agent(agents_dir, caplog, bad_block, frag):
    import logging
    bad = ("name: bad-board\nharness: api\nmodel: cheap\nprompt_file: x.md\n"
           "output_dir: /data/outputs/bad-board\njob: true\ntriggers:\n"
           "      on_project_status:\n" + bad_block)
    (agents_dir / "bad-board.yaml").write_text(bad)
    _write(agents_dir, "plain-job", JOB_AGENT)   # an unrelated, valid agent
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # the bad agent is skipped by name; the good one still loads
    assert "agents/bad-board.yaml" in caplog.text
    assert frag in caplog.text
    job_names = {j.name for j in out["jobs"]}
    assert "agent_plain_job" in job_names
    assert "agent_bad_board" not in job_names


def test_non_int_interval_rejected(agents_dir, caplog):
    import logging
    bad = ("name: bad-board\nharness: api\nmodel: cheap\nprompt_file: x.md\n"
           "output_dir: /data/outputs/bad-board\njob: true\ntriggers:\n"
           "      on_project_status:\n        owner: o\n        project: 1\n"
           "        status: In progress\n        interval_seconds: sixty\n")
    (agents_dir / "bad-board.yaml").write_text(bad)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    assert "interval_seconds" in caplog.text
    assert "agent_bad_board" not in {j.name for j in out["jobs"]}


def test_bad_repo_shape_rejected(agents_dir, caplog):
    import logging
    bad = ("name: bad-board\nharness: api\nmodel: cheap\nprompt_file: x.md\n"
           "output_dir: /data/outputs/bad-board\njob: true\ntriggers:\n"
           "      on_project_status:\n        owner: o\n        project: 1\n"
           "        status: In progress\n        repo: not-a-full-name\n")
    (agents_dir / "bad-board.yaml").write_text(bad)
    with caplog.at_level(logging.WARNING):
        _discover(agents_dir)
    assert "repo must be a full owner/repo name" in caplog.text
