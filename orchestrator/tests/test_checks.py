"""Tests for produces.checks — the check runner and the check-bearing asset (spec 008).

Container launches are stubbed by ``stub_launch`` (conftest.py): the producer is Popen'd and
each check container is a ``subprocess.run`` whose per-check exit/output comes from
``stub_launch.check_outcomes`` (declared order). US1 covers the check argv, the pass/fail
verdict from the exit code, and the captured-output / exit-code metadata.
"""
import os

import pytest
from dagster import materialize

import factory


class _Ctx:
    """A minimal execution context for calling ``run_checks`` directly (no producer launch)."""
    run_id = "abcd1234efgh5678"

    class log:
        @staticmethod
        def info(*a, **k):
            pass

        @staticmethod
        def error(*a, **k):
            pass


def _api_cfg(tmp_path, checks, **over):
    """A materializable api-harness cfg (no workspace) whose produces block carries checks."""
    cfg = {
        "name": "verify-checks",
        "harness": "api",
        "model": "cheap",
        "prompt_file": "x.md",
        "output_dir": str(tmp_path / "out"),
        "produces": {"asset": "verify/checks", "checks": checks},
    }
    cfg.update(over)
    return cfg


def _cc_cfg(tmp_path, checks, **over):
    """A claude-code cfg (has a workspace) for the /workspace-mount argv assertion."""
    cfg = {
        "name": "verify-checks",
        "harness": "claude-code",
        "output_dir": str(tmp_path / "out"),
        "workspace": str(tmp_path / "ws"),
        "produces": {"asset": "verify/checks", "checks": checks},
    }
    cfg.update(over)
    return cfg


# --- run_checks: argv (contract check-execution §3) --------------------------

def test_check_argv_mounts_network_and_command(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "has-output", "command": "test -n \"$(ls /output)\""}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert argv[:3] == ["docker", "run", "--rm"]
    assert "--name" in argv and f"check-verify-checks-has-output-{_Ctx.run_id[:8]}" in argv
    # no network by default
    ni = argv.index("--network")
    assert argv[ni + 1] == "none"
    # /output mounted read-only, /report.json mounted read-only, run via sh -c
    assert f"{cfg['output_dir']}:/output:ro" in argv
    assert f"{os.path.join(str(tmp_path / 'pipes'), 'report.json')}:/report.json:ro" in argv
    ei = argv.index("--entrypoint")
    assert argv[ei + 1] == "sh"
    assert argv[-2:] == ["-c", "test -n \"$(ls /output)\""]


def test_check_argv_omits_workspace_for_workspaceless_harness(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert not any("/workspace" in str(a) for a in argv)


def test_check_argv_mounts_workspace_readonly_for_workspace_harness(tmp_path, stub_launch):
    cfg = _cc_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"), cfg["workspace"])
    argv = stub_launch.check_calls[0]
    assert f"{cfg['workspace']}:/workspace:ro" in argv


def test_check_network_opt_in(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true", "network": "agentnet"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert argv[argv.index("--network") + 1] == "agentnet"


# --- run_checks: image resolution (R6) --------------------------------------

def test_check_default_image_is_harness_image(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert factory.HARNESS_IMAGE["api"] in argv


def test_check_explicit_image_wins(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true", "image": "agentbox/agent-python:pinned"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert "agentbox/agent-python:pinned" in argv


# --- run_checks: verdict, output tail, exit code ----------------------------

def test_check_passed_on_exit_zero(tmp_path, stub_launch):
    stub_launch.check_outcomes = [{"returncode": 0, "stdout": "ok\n"}]
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert len(results) == 1
    assert results[0].check_name == "c"
    assert results[0].passed is True
    assert results[0].metadata["exit_code"].value == 0
    assert results[0].metadata["output"].value == "ok\n"


def test_check_failed_on_nonzero_exit(tmp_path, stub_launch):
    stub_launch.check_outcomes = [{"returncode": 3, "stderr": "boom\n"}]
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "false"}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert results[0].passed is False
    assert results[0].metadata["exit_code"].value == 3
    assert "boom" in results[0].metadata["output"].value


def test_check_output_is_last_4kb_tail(tmp_path, stub_launch):
    big = "".join(f"line{i}\n" for i in range(5000))
    stub_launch.check_outcomes = [{"returncode": 0, "stdout": big}]
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    out = results[0].metadata["output"].value
    assert len(out.encode("utf-8")) <= 4096
    assert big.endswith(out)   # it is the TAIL of the output


def test_checks_run_in_declared_order(tmp_path, stub_launch):
    checks = [{"name": "first", "command": "true"}, {"name": "second", "command": "true"}]
    cfg = _api_cfg(tmp_path, checks)
    results = factory.run_checks(cfg, _Ctx(), checks, str(tmp_path / "pipes"), str(tmp_path / "ws"))
    assert [r.check_name for r in results] == ["first", "second"]


# --- build_asset: the check-bearing asset materializes (T010/T011) ----------

def test_check_bearing_asset_declares_check_specs(tmp_path):
    cfg = _api_cfg(tmp_path, [{"name": "has-output", "command": "true"},
                              {"name": "advisory", "command": "false"}])
    ad = factory.build_asset(cfg)
    assert [k.path for k in ad.keys] == [["verify", "checks"]]
    assert {s.name for s in ad.check_specs} == {"has-output", "advisory"}
    assert ad.op.name == "run_verify_checks"


def test_materialize_records_materialization_and_check_results(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    os.makedirs(str(tmp_path / "out"), exist_ok=True)
    stub_launch.check_outcomes = [{"returncode": 0}, {"returncode": 1}]
    cfg = _api_cfg(tmp_path, [{"name": "has-output", "command": "true"},
                              {"name": "advisory", "command": "false"}])
    ad = factory.build_asset(cfg)
    result = materialize([ad])
    assert result.success
    # exactly one materialization for the asset
    assert len(result.get_asset_materialization_events()) == 1
    evals = {e.check_name: e for e in result.get_asset_check_evaluations()}
    assert set(evals) == {"has-output", "advisory"}
    assert evals["has-output"].passed is True
    assert evals["advisory"].passed is False


def test_producer_launched_before_checks(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    os.makedirs(str(tmp_path / "out"), exist_ok=True)
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    materialize([factory.build_asset(cfg)])
    # the producer is the api image; the check container is launched afterwards
    assert "agentbox/agent-python:latest" in stub_launch.producer_cmd
    assert len(stub_launch.check_calls) == 1
