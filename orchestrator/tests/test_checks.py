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
    # the failing check is non-blocking (advisory) so the run still succeeds; blocking
    # gating is exercised in the US2 tests below.
    cfg = _api_cfg(tmp_path, [{"name": "has-output", "command": "true"},
                              {"name": "advisory", "command": "false", "blocking": False}])
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


# --- US2: blocking vs. non-blocking (severity + gating) ---------------------
# blocking -> AssetCheckSpec(blocking=...) on the asset and
# severity=ERROR/WARN on the AssetCheckResult; absent blocking defaults to
# blocking (contract check-execution §3–§4, quickstart §3).

def test_blocking_check_result_severity_is_error(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "false", "blocking": True}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert results[0].severity == factory.AssetCheckSeverity.ERROR


def test_non_blocking_check_result_severity_is_warn(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "false", "blocking": False}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert results[0].severity == factory.AssetCheckSeverity.WARN


def test_absent_blocking_defaults_to_error_severity(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "false"}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert results[0].severity == factory.AssetCheckSeverity.ERROR


def test_check_specs_carry_blocking(tmp_path):
    cfg = _api_cfg(tmp_path, [{"name": "gate", "command": "true", "blocking": True},
                              {"name": "advisory", "command": "true", "blocking": False},
                              {"name": "default", "command": "true"}])
    ad = factory.build_asset(cfg)
    blocking = {s.name: s.blocking for s in ad.check_specs}
    # absent -> blocking (default true)
    assert blocking == {"gate": True, "advisory": False, "default": True}


def test_failing_non_blocking_check_run_succeeds_and_materializes(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    os.makedirs(str(tmp_path / "out"), exist_ok=True)
    stub_launch.check_outcomes = [{"returncode": 0}, {"returncode": 1}]
    cfg = _api_cfg(tmp_path, [{"name": "passes", "command": "true"},
                              {"name": "advisory", "command": "false", "blocking": False}])
    result = materialize([factory.build_asset(cfg)])
    # a failing NON-blocking check is advisory: run still succeeds, asset materialized
    assert result.success
    assert len(result.get_asset_materialization_events()) == 1
    evals = {e.check_name: e for e in result.get_asset_check_evaluations()}
    assert evals["advisory"].passed is False


def test_failing_blocking_check_fails_run_but_records_materialization(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    os.makedirs(str(tmp_path / "out"), exist_ok=True)
    stub_launch.check_outcomes = [{"returncode": 1}]
    cfg = _api_cfg(tmp_path, [{"name": "gate", "command": "false", "blocking": True}])
    result = materialize([factory.build_asset(cfg)], raise_on_error=False)
    # a failing BLOCKING check gates automation: the run fails, but the
    # materialization is still recorded (asset counts as materialized).
    assert not result.success
    assert len(result.get_asset_materialization_events()) == 1


# --- US3: read-only isolation (contract check-execution §5, quickstart §4) ---
# A check sees the produced output but cannot change it: /output and /workspace
# are mounted :ro, /report.json is mounted, no env/env_file/credential mounts
# reach the check container, and it defaults to no network. FR-003/FR-009,
# Constitution I & V.

def test_check_argv_mounts_output_report_readonly_and_no_network(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "guard", "command": "touch /output/x"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    # /output read-only and /report.json mounted (read-only) — the check observes, never writes.
    assert f"{cfg['output_dir']}:/output:ro" in argv
    assert f"{os.path.join(str(tmp_path / 'pipes'), 'report.json')}:/report.json:ro" in argv
    # no /output write mount ever (only the :ro form appears)
    assert f"{cfg['output_dir']}:/output" not in argv
    # no network by default
    assert argv[argv.index("--network") + 1] == "none"


def test_check_workspace_mounted_readonly_and_omitted_when_absent(tmp_path, stub_launch):
    # workspace harness: /workspace present and read-only, never writable
    cc = _cc_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cc, _Ctx(), cc["produces"]["checks"], str(tmp_path / "pipes"), cc["workspace"])
    cc_argv = stub_launch.check_calls[-1]
    assert f"{cc['workspace']}:/workspace:ro" in cc_argv
    assert f"{cc['workspace']}:/workspace" not in cc_argv
    # workspaceless (api) harness: no /workspace mount at all
    api = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(api, _Ctx(), api["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    api_argv = stub_launch.check_calls[-1]
    assert not any("/workspace" in str(a) for a in api_argv)


def test_check_argv_passes_no_env_or_env_file(tmp_path, stub_launch):
    # even when the agent forwards env and an env_file to its producer, no environment
    # or env-file reaches the check container (Constitution V — no creds/secrets).
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}],
                   env={"FOO": "bar", "TOKEN": "${SECRET}"},
                   env_file="/data/credentials/some.env")
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    argv = stub_launch.check_calls[0]
    assert "-e" not in argv
    assert "--env-file" not in argv
    assert not any("some.env" in str(a) for a in argv)


def test_check_argv_mounts_no_credentials(tmp_path, stub_launch):
    # a claude-code producer mounts host credentials; its checks never do.
    cfg = _cc_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"), cfg["workspace"])
    argv = stub_launch.check_calls[0]
    assert not any("/creds" in str(a) for a in argv)
    assert not any(".credentials.json" in str(a) for a in argv)
    assert not any("/data/credentials" in str(a) for a in argv)
    # the only bind mounts are the read-only observation mounts
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert all(m.endswith(":ro") for m in mounts)


# --- US4: per-check timeout (contract check-execution §3, quickstart §5) ------
# Each check enforces its own timeout_seconds (default 300, never unbounded). On
# expiry the container is docker-killed by name and the result is failed with
# metadata.timed_out=True; every declared check still runs in order (no
# short-circuit). FR-008/FR-017/SC-004.

def test_check_timeout_marks_failed_and_timed_out(tmp_path, stub_launch):
    stub_launch.check_outcomes = [{"timeout": True}]
    cfg = _api_cfg(tmp_path, [{"name": "slow", "command": "sleep 60", "timeout_seconds": 2}])
    results = factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                                 str(tmp_path / "ws"))
    assert results[0].passed is False
    assert results[0].metadata["timed_out"].value is True


def test_check_timeout_kills_container_by_name(tmp_path, stub_launch):
    stub_launch.check_outcomes = [{"timeout": True}]
    cfg = _api_cfg(tmp_path, [{"name": "slow", "command": "sleep 60", "timeout_seconds": 2}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    cname = f"check-verify-checks-slow-{_Ctx.run_id[:8]}"
    # the kill-by-name path fired so no check container survives (`--rm` + kill)
    assert ["docker", "kill", cname] in stub_launch.kill_calls


def test_check_timeout_does_not_short_circuit(tmp_path, stub_launch):
    stub_launch.check_outcomes = [{"timeout": True}, {"returncode": 0}]
    checks = [{"name": "slow", "command": "sleep 60", "timeout_seconds": 1},
              {"name": "after", "command": "true"}]
    cfg = _api_cfg(tmp_path, checks)
    results = factory.run_checks(cfg, _Ctx(), checks, str(tmp_path / "pipes"), str(tmp_path / "ws"))
    # both checks run in declared order; the timed-out one fails, the next still runs
    assert [r.check_name for r in results] == ["slow", "after"]
    assert results[0].passed is False
    assert results[0].metadata["timed_out"].value is True
    assert results[1].passed is True
    assert results[1].metadata["timed_out"].value is False


def test_check_default_timeout_is_300_when_omitted(tmp_path, stub_launch):
    # never unbounded: a check with no timeout_seconds is bounded at 300s.
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true"}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    assert stub_launch.check_timeouts[0] == 300


def test_check_explicit_timeout_is_passed_through(tmp_path, stub_launch):
    cfg = _api_cfg(tmp_path, [{"name": "c", "command": "true", "timeout_seconds": 5}])
    factory.run_checks(cfg, _Ctx(), cfg["produces"]["checks"], str(tmp_path / "pipes"),
                       str(tmp_path / "ws"))
    assert stub_launch.check_timeouts[0] == 5
