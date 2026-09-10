"""Unit tests for orchestrator/definitions.py agent routing (US1/US2/US4).

``discover(glob)`` is driven against a temp directory of agent YAML files so the
job-vs-asset routing, reversibility, and invalid/duplicate rejection can be tested
without the container path or a live Dagster.
"""
import logging
import textwrap

import pytest

import definitions
import factory


def _write(agents_dir, stem, body):
    (agents_dir / f"{stem}.yaml").write_text(textwrap.dedent(body))


@pytest.fixture
def agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    return d


def _discover(agents_dir, automation_dir=None):
    # Default to a non-existent automation glob so existing tests see zero triggers
    # deterministically (never the host's real /opt/agentbox/automation).
    auto = automation_dir if automation_dir is not None else (agents_dir / "__no_automation__")
    return definitions.discover(str(agents_dir / "*.yaml"), str(auto / "*.yaml"))


JOB_AGENT = """\
    name: plain-job
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/plain-job
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


def test_produces_agent_becomes_asset_not_job(agents_dir):
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    out = _discover(agents_dir)
    assert [k.path for a in out["assets"] for k in a.keys] == [["repo-review", "agentbox"]]
    # no bare job for the asset agent
    assert [j.name for j in out["jobs"]] == []


def test_plain_agent_stays_job(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT)
    out = _discover(agents_dir)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert out["assets"] == []


def test_mixed_set_routes_each_correctly(agents_dir):
    _write(agents_dir, "plain-job", JOB_AGENT)
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    out = _discover(agents_dir)
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert [k.path for a in out["assets"] for k in a.keys] == [["repo-review", "agentbox"]]


# --- US2: reversibility and job-mode is untouched ---------------------------

def _reversible_cfg(**over):
    cfg = {
        "name": "repo-review-agentbox",
        "harness": "api",
        "model": "cheap",
        "prompt_file": "x.md",
        "output_dir": "/data/outputs/repo-review/agentbox",
    }
    cfg.update(over)
    return cfg


def test_job_and_asset_share_the_same_op_name():
    # SC-004: the only observable difference between modes is job-vs-asset; the op
    # (and thus the launch) is the same run_<name> in both.
    job = factory.build_job(_reversible_cfg())
    asset = factory.build_asset(_reversible_cfg(produces={"asset": "repo-review/agentbox"}))
    assert job.name == "agent_repo_review_agentbox"
    assert job.graph.node_defs[0].name == "run_repo_review_agentbox"
    assert asset.op.name == "run_repo_review_agentbox"


def test_removing_produces_reverts_to_job(agents_dir):
    # produces present -> asset, no job
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT)
    out = _discover(agents_dir)
    assert out["assets"] and not out["jobs"]
    # produces removed (same file) -> job agent_<name>, no asset, nothing else changed
    _write(agents_dir, "repo-review-agentbox", ASSET_AGENT.split("produces:")[0])
    out = _discover(agents_dir)
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_repo_review_agentbox"]


def test_job_mode_still_launches_unchanged(stub_launch, monkeypatch):
    # T012: the op's new nominal output + add_output_metadata are harmless in job-mode.
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    job = factory.build_job(_reversible_cfg())
    result = job.execute_in_process()
    assert result.success
    assert f"{_reversible_cfg()['output_dir']}:/output" in stub_launch.cmd


# --- US4: invalid and conflicting declarations rejected by name -------------

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

DUP_B = """\
    name: dup-b
    harness: api
    model: cheap
    prompt_file: x.md
    output_dir: /data/outputs/dup-b
    produces:
      asset: shared/key
"""


def test_invalid_asset_rejects_only_that_file(agents_dir, caplog):
    _write(agents_dir, "bad-key", BAD_KEY_AGENT)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # the bad file is dropped (no asset, no job); the good agent still loads
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert "agents/bad-key.yaml" in caplog.text
    assert "Bad Key" in caplog.text


def test_duplicate_asset_keys_reject_all_by_name(agents_dir, caplog):
    _write(agents_dir, "dup-a", DUP_A)
    _write(agents_dir, "dup-b", DUP_B)
    _write(agents_dir, "plain-job", JOB_AGENT)
    with caplog.at_level(logging.WARNING):
        out = _discover(agents_dir)
    # both conflicting files rejected; the unrelated job still loads
    assert out["assets"] == []
    assert [j.name for j in out["jobs"]] == ["agent_plain_job"]
    assert 'asset key "shared/key"' in caplog.text
    assert "agents/dup-a.yaml" in caplog.text and "agents/dup-b.yaml" in caplog.text


def test_unique_asset_key_still_loads(agents_dir):
    _write(agents_dir, "dup-a", DUP_A)  # only one file uses shared/key here
    out = _discover(agents_dir)
    assert [k.path for a in out["assets"] for k in a.keys] == [["shared", "key"]]
