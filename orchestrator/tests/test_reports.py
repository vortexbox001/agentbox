"""Orchestrator-side report routing and the launch-isolation invariant (spec 007).

All container launches are stubbed by ``stub_launch`` (conftest.py): the op runs
in-process via ``materialize()`` with no ``docker run``, and the canned report on
``stub_launch.report`` stands in for what the container would emit over Dagster
Pipes. These tests cover the Foundational isolation proof (T006) and US1's metadata
union (T014). Failure-path and streaming tests are added by US2/US3.
"""
import factory
from dagster import AssetKey, DagsterInstance, DailyPartitionsDefinition, materialize
from dagster._core.storage.partition_status_cache import get_and_update_asset_status_cache_value


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


def _materialization_metadata(result):
    events = result.get_asset_materialization_events()
    assert events, "no materialization event"
    return events[0].step_materialization_data.materialization.metadata


# --- SC-007 / FR-011: launch isolation preserved ----------------------------

def test_launch_isolation_preserved_except_pipes_additions(tmp_path, stub_launch, monkeypatch):
    """The launched ``docker run`` argv is byte-for-byte the pre-feature argv EXCEPT
    for exactly the ``-v <pipes>:/pipes`` + ``-v <staging>:/staging`` mounts and the two
    ``-e DAGSTER_PIPES_*`` env vars (contract §4 + spec 012 T010a). No prior isolation
    flag is removed, reordered, or altered.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")

    # spy on the pre-feature argv builder: it produces the launch WITHOUT any capture
    # additions (those are layered on by the op).
    captured = {}
    orig = factory._build_agent_cmd

    def spy(*a, **k):
        cmd = orig(*a, **k)
        captured["base"] = list(cmd)
        return cmd

    monkeypatch.setattr(factory, "_build_agent_cmd", spy)

    cfg = _api_cfg(tmp_path)
    assert materialize([factory.build_asset(cfg)], partition_key="2026-09-09").success

    base = captured["base"]
    launched = stub_launch.cmd

    # the pre-feature argv carries none of the capture additions
    assert not any(":/pipes" in a for a in base)
    assert not any(":/staging" in a for a in base)
    assert not any("DAGSTER_PIPES" in a for a in base)

    # the four additions, taken from the launched argv (spec 012 adds the staging mount)
    pipes_flags = [
        "-v", next(a for a in launched if a.endswith(":/pipes")),
        "-v", next(a for a in launched if a.endswith(":/staging")),
        "-e", next(a for a in launched if a.startswith("DAGSTER_PIPES_CONTEXT=")),
        "-e", next(a for a in launched if a.startswith("DAGSTER_PIPES_MESSAGES=")),
    ]

    # the launched argv is EXACTLY the base with those additions inserted immediately
    # before the image name — nothing else differs.
    img_idx = next(i for i, a in enumerate(base) if a.startswith("agentbox/"))
    assert launched == base[:img_idx] + pipes_flags + base[img_idx:]
    assert len(launched) == len(base) + 8  # two mounts + two env vars

    # the capture mounts are distinct from the immutable /output mount (Constitution V)
    assert f"{cfg['output_dir']}:/output" in launched
    assert not any(a.endswith(":/output") and ":/pipes" in a for a in launched)
    assert not any(a.endswith(":/output") and ":/staging" in a for a in launched)
    # T010a invariant: the staging source resolves under $AGENTBOX_DATA (STAGING_ROOT), never /tmp
    staging_mount = next(a for a in launched if a.endswith(":/staging"))
    staging_src = staging_mount[: -len(":/staging")]
    # under STAGING_ROOT (which resolves under $AGENTBOX_DATA in production, not container /tmp —
    # paths.STAGING_ROOT is pinned under DATA_ROOT by the paths tests; here it is redirected to tmp).
    assert staging_src.startswith(factory.STAGING_ROOT + "/")
    # a representative sample of preserved isolation flags
    for flag in ("--rm", "--name", "--network", "--memory", "--cpus"):
        assert flag in launched


def test_staging_dir_removed_after_run(tmp_path, stub_launch, monkeypatch):
    """The per-run staging dir is --rm-cleaned: nothing survives under STAGING_ROOT (T010a)."""
    import os
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    assert materialize([factory.build_asset(cfg)], partition_key="2026-09-09").success
    leftover = []
    if os.path.isdir(factory.STAGING_ROOT):
        leftover = os.listdir(factory.STAGING_ROOT)
    assert leftover == [], f"staging dirs survived the run: {leftover}"


def test_run_directory_written_with_four_files_metadata_link(tmp_path, stub_launch, monkeypatch):
    """A successful run writes the run directory and links it in metadata (spec 012 FR-001/002)."""
    import json
    import os
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    result = materialize([factory.build_asset(cfg)], partition_key="2026-09-09")
    md = _materialization_metadata(result)
    assert "run_dir" in md
    run_dir = str(md["run_dir"].value)
    assert os.path.isdir(run_dir)
    # context.json + report.json are always written; transcript.jsonl was streamed.
    assert os.path.isfile(os.path.join(run_dir, "context.json"))
    assert os.path.isfile(os.path.join(run_dir, "report.json"))
    assert os.path.isfile(os.path.join(run_dir, "transcript.jsonl"))
    # context.json is schema-shaped and records the harness + image ref
    ctx = json.load(open(os.path.join(run_dir, "context.json")))
    assert ctx["harness"]["harness"] == "api"
    assert ctx["runtime"]["env_names"]  # names captured, values never
    # the report co-located in the run dir carries the run's transcript path
    rep = json.load(open(os.path.join(run_dir, "report.json")))
    assert rep["status"] == "ok"
    assert rep["transcript_path"].endswith("transcript.jsonl")


def test_timeout_still_writes_context_and_report(tmp_path, stub_launch, monkeypatch):
    """On a timeout the orchestrator authors the report and the run dir still has context+report
    (spec 012 FR-001; the failed/timed-out asset run is recorded, not thrown away)."""
    import json
    import os
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.timeout = True
    cfg = _api_cfg(tmp_path)
    result, obs, _instance = _materialize_expecting_failure(cfg)
    assert not result.success
    assert obs, "no asset observation for the timed-out run"
    md = obs[0].metadata
    run_dir = str(md["run_dir"].value)
    assert os.path.isfile(os.path.join(run_dir, "context.json"))
    rep = json.load(open(os.path.join(run_dir, "report.json")))
    assert rep["status"] == "timeout"


# --- FR-004/FR-005: the metadata union (T014) -------------------------------

EXISTING_KEYS = {"output_files", "transcript", "run_stamp", "session_id", "harness", "model"}
REPORT_KEYS = {"status", "tokens_in", "tokens_out", "turns", "cost_usd", "files_written"}


def test_metadata_union_attaches_report_and_context_fields(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.report = {
        "status": "ok", "tokens_in": 5231, "tokens_out": 812, "turns": 4,
        "cost_usd": 0.0231, "files_written": 1, "transcript_path": None,
        "error": None, "notes": "Documented the factory; **start** from definitions.py.",
    }
    cfg = _api_cfg(tmp_path)
    result = materialize([factory.build_asset(cfg)], partition_key="2026-09-09")
    md = _materialization_metadata(result)

    # union: every existing context key AND every report field is present
    assert set(md) >= EXISTING_KEYS | REPORT_KEYS | {"partition"}
    assert md["status"].value == "ok"
    assert md["tokens_in"].value == 5231
    assert md["cost_usd"].value == 0.0231
    assert md["files_written"].value == 1
    # transcript_path maps onto the existing `transcript` key — not a second key
    assert "transcript_path" not in md
    assert str(md["transcript"].value).endswith(".jsonl")


def test_notes_is_markdown_metadata(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.report = dict(stub_launch.report, notes="a **bold** closing note")
    cfg = _api_cfg(tmp_path)
    md = _materialization_metadata(materialize([factory.build_asset(cfg)], partition_key="2026-09-09"))
    # FR-010/SC-006: notes render inline as markdown, not a file reference
    assert type(md["notes"]).__name__ == "MarkdownMetadataValue"
    assert md["notes"].value == "a **bold** closing note"


def test_null_numeric_is_distinct_from_zero(tmp_path, stub_launch, monkeypatch):
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.report = dict(
        stub_launch.report, cost_usd=None, tokens_in=None, tokens_out=0,
    )
    cfg = _api_cfg(tmp_path)
    md = _materialization_metadata(materialize([factory.build_asset(cfg)], partition_key="2026-09-09"))
    # a genuine 0 stays an int; a null numeric is a text placeholder, never coerced to 0
    assert md["tokens_out"].value == 0
    assert md["cost_usd"].value == factory.NULL_NUMERIC_PLACEHOLDER
    assert md["tokens_in"].value == factory.NULL_NUMERIC_PLACEHOLDER
    assert md["cost_usd"].value != 0 and md["tokens_in"].value != 0


def test_success_records_exactly_one_materialization(tmp_path, stub_launch, monkeypatch):
    """I1: the reported result is consumed for its fields only; the success asset
    path records exactly ONE materialization (the from_op output), not a second one.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    result = materialize([factory.build_asset(cfg)], partition_key="2026-09-09")
    assert result.success
    assert len(result.get_asset_materialization_events()) == 1


# --- US2: failed/timed-out asset runs are recorded, not thrown away (T017) ----

def _materialize_expecting_failure(cfg, partition_key="2026-09-09"):
    """Materialize an asset agent that will fail, returning (result, observations, instance).

    On failure the op records an ``AssetObservation`` — NOT a materialization: a
    materialization event is Dagster's positive signal that greens a partition, so emitting
    one on failure rendered a failed partition MATERIALIZED (bug
    failed-asset-shows-materialized). The observation attaches the report without marking the
    partition materialized. A failed step's events are not surfaced by
    ``ExecuteInProcessResult``, so read them back from the instance event log — where the
    explicit ``log_event`` observation is durably recorded (the persistence is the point of
    SC-003). The instance is returned so callers can assert the derived partition status.
    """
    instance = DagsterInstance.ephemeral()
    result = materialize([factory.build_asset(cfg)], partition_key=partition_key,
                         raise_on_error=False, instance=instance)
    obs = [
        r.dagster_event.event_specific_data.asset_observation
        for r in instance.all_logs(result.run_id)
        if r.dagster_event and r.dagster_event.event_type_value == "ASSET_OBSERVATION"
    ]
    return result, obs, instance


def _partition_status(instance, cfg, partition_key):
    """The (materialized, failed) partition-key sets Dagster derives for the asset — exactly
    what the UI partitions view colors green vs red. Regression guard for the bug: a failed
    run must leave its partition in ``failed`` and out of ``materialized``.
    """
    key = AssetKey(cfg["produces"]["asset"].split("/"))
    partitions_def = DailyPartitionsDefinition(start_date=factory.PARTITION_START_DATE)
    val = get_and_update_asset_status_cache_value(instance, key, partitions_def)
    materialized = set(val.deserialize_materialized_partition_subsets(partitions_def).get_partition_keys())
    failed = set(val.deserialize_failed_partition_subsets(partitions_def).get_partition_keys())
    return materialized, failed


def _job_cfg(tmp_path, **over):
    """A minimal job-only (no `produces`) api-harness cfg."""
    cfg = {
        "name": "hello-x",
        "harness": "api",
        "model": "cheap",
        "prompt_file": "x.md",
        "output_dir": str(tmp_path / "out"),
    }
    cfg.update(over)
    return cfg


def test_failed_asset_records_observation_and_partition_shows_red(tmp_path, stub_launch, monkeypatch):
    """SC-003/FR-007 (bug failed-asset-shows-materialized): a non-ok asset run records an
    AssetObservation carrying ``status: failed`` — NOT a materialization — and the run fails,
    so the partition renders red (failed) WITH the report, never green (materialized)."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.returncode = 1
    stub_launch.report = {
        "status": "failed", "tokens_in": 10, "tokens_out": 0, "turns": 1,
        "cost_usd": 0.0, "files_written": 0, "transcript_path": None,
        "error": "the model hit its turn cap", "notes": None,
    }
    cfg = _api_cfg(tmp_path)
    result, obs, instance = _materialize_expecting_failure(cfg)
    assert not result.success
    assert len(obs) == 1  # exactly the failure observation
    md = obs[0].metadata
    assert md["status"].value == "failed"
    assert md["error"].value == "the model hit its turn cap"
    assert str(md["transcript"].value).endswith(".jsonl")
    # no materialization was emitted — the failure must not green the partition
    mat_events = [
        r for r in instance.all_logs(result.run_id)
        if r.dagster_event and r.dagster_event.event_type_value == "ASSET_MATERIALIZATION"
    ]
    assert not mat_events
    # the derived partition status Dagster's UI colors: red (failed), not green (materialized)
    materialized, failed = _partition_status(instance, cfg, "2026-09-09")
    assert "2026-09-09" in failed
    assert "2026-09-09" not in materialized


def test_missing_report_authors_failed(tmp_path, stub_launch, monkeypatch):
    """A normal exit with no readable/well-formed report is authored as ``failed``."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.report = None  # nothing recovered from Pipes
    cfg = _api_cfg(tmp_path)
    result, obs, _instance = _materialize_expecting_failure(cfg)
    assert not result.success
    md = obs[0].metadata
    assert md["status"].value == "failed"
    assert "missing or malformed" in md["error"].value


def test_timeout_authors_timeout_with_null_numerics_and_kills(tmp_path, stub_launch, monkeypatch):
    """SC-004/FR-009: a timeout authors ``status: timeout`` with null numerics, kills
    the named container, and records the failure as an observation (not a materialization)."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.timeout = True
    cfg = _api_cfg(tmp_path, timeout_seconds=1)
    result, obs, _instance = _materialize_expecting_failure(cfg)
    assert not result.success
    md = obs[0].metadata
    assert md["status"].value == "timeout"
    # every numeric is the null placeholder, never coerced to 0
    for key in ("tokens_in", "tokens_out", "turns", "cost_usd"):
        assert md[key].value == factory.NULL_NUMERIC_PLACEHOLDER
    assert "timeout_seconds" in md["error"].value
    # the container was killed by its deterministic name (nothing survives, --rm)
    kill_calls = [c for c in stub_launch.calls if c[:2] == ["docker", "kill"]]
    assert len(kill_calls) == 1
    assert kill_calls[0][2].startswith("agent-repo-review-agentbox-")


def test_job_only_failure_raises_without_materialization(tmp_path, stub_launch, monkeypatch):
    """FR-008: a job-only agent raises on non-zero exit (no asset key ⇒ no
    materialization), the report visible via the logged custom message + transcript."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    stub_launch.returncode = 1
    stub_launch.report = None
    cfg = _job_cfg(tmp_path)
    result = factory.build_job(cfg).execute_in_process(raise_on_error=False)
    assert not result.success
    # job-only routing records no asset materialization
    assert not result.get_asset_materialization_events()


# --- US3: live log streaming (T019) -----------------------------------------

def test_stream_output_forwards_each_line_and_writes_transcript():
    """Unit: ``_stream_output`` forwards each line as it is read (one call per line, in
    order — not buffered to the end) and writes the transcript byte-for-byte
    (FR-003/FR-006)."""
    import io

    forwarded = []
    transcript = io.StringIO()
    factory._stream_output(iter(["a\n", "b\n", "c\n"]), transcript, forwarded.append)
    assert forwarded == ["a", "b", "c"]        # one forward per line, in order
    assert transcript.getvalue() == "a\nb\nc\n"  # transcript unchanged


def test_run_streams_stdout_live_and_writes_full_transcript(tmp_path, stub_launch, monkeypatch):
    """Integration (US3/SC-005): each stdout line is forwarded to the Dagster run log as
    it arrives — a separate message per line, not one end-of-run dump — and the full
    stream is still written to the transcript."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    lines = ['{"type":"system"}', '{"type":"assistant"}', '{"type":"result"}']
    stub_launch.stdout = "\n".join(lines) + "\n"
    cfg = _api_cfg(tmp_path)
    instance = DagsterInstance.ephemeral()
    result = materialize([factory.build_asset(cfg)], partition_key="2026-09-09",
                         instance=instance)
    assert result.success

    # every stdout line reached the run log as its own forwarded message
    logged = [r.user_message for r in instance.all_logs(result.run_id) if r.dagster_event is None]
    for line in lines:
        assert line in logged

    # the transcript holds the full stream, byte-for-byte (FR-006)
    md = _materialization_metadata(result)
    with open(md["transcript"].value) as f:
        assert f.read() == stub_launch.stdout


# --- Regression: Pipes messages dir must be on a host<->container shared mount ---
# Bug pipes-dir-tmp-mismatch: agent containers launch Docker-outside-of-Docker, so the
# host daemon resolves the `-v <pipes_dir>:/pipes` source against the HOST filesystem.
# When pipes_dir was a bare tempfile.mkdtemp() it landed in the orchestrator container's
# private /tmp, which the host does not share, so the report was written to a different
# filesystem than the one PipesFileMessageReader watched — every run recorded status=failed
# ("run report was missing or malformed") despite the agent succeeding.

def test_pipes_root_is_under_shared_data_mount():
    """The production PIPES_ROOT must sit under /data (mounted host==container), never /tmp.

    This is the cheapest check that would have caught the bug — the DooD mount boundary
    itself cannot be exercised in-process. Uses the unpatched module value (no stub_launch).
    """
    assert factory.PIPES_ROOT.startswith("/data/"), factory.PIPES_ROOT


def test_pipes_dir_created_under_pipes_root(tmp_path, stub_launch, monkeypatch):
    """The `:/pipes` mount source is created under PIPES_ROOT (via mkdtemp(dir=...)),
    not the default temp root — so it inherits PIPES_ROOT's shared-mount guarantee."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    cfg = _api_cfg(tmp_path)
    assert materialize([factory.build_asset(cfg)], partition_key="2026-09-09").success

    pipes_mount = next(a for a in stub_launch.cmd if a.endswith(":/pipes"))
    pipes_src = pipes_mount[: -len(":/pipes")]
    assert pipes_src.startswith(factory.PIPES_ROOT + "/"), pipes_src


def test_pipes_dir_world_writable_for_nonroot_agents(tmp_path, stub_launch, monkeypatch):
    """The per-run pipes dir AND its messages file must be reachable/writable by non-root
    agent containers.

    The orchestrator runs as root; all harnesses but api run their container as node (uid 1000).
    mkdtemp makes the dir 0700, and PipesFileMessageReader creates `messages` root-owned 0644 —
    so without intervention a non-root container can neither traverse the dir nor append to the
    file, and emit() hits PermissionError on /pipes/messages. The op therefore chmods the dir
    0777 (traversal) and the messages file 0666 (append). Regression for the claude-code/codex/pi
    failure (bug pipes-dir-tmp-mismatch, runs e003f919 / fd1596d6)."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")

    chmods = []
    real_chmod = factory.os.chmod

    def spy_chmod(path, mode, *a, **k):
        chmods.append((path, mode))
        return real_chmod(path, mode, *a, **k)

    monkeypatch.setattr(factory.os, "chmod", spy_chmod)

    cfg = _api_cfg(tmp_path)
    assert materialize([factory.build_asset(cfg)], partition_key="2026-09-09").success

    pipes_mount = next(a for a in stub_launch.cmd if a.endswith(":/pipes"))
    pipes_src = pipes_mount[: -len(":/pipes")]
    # dir made traversable/world-writable, and the messages file made world-writable
    assert (pipes_src, 0o777) in chmods, chmods
    assert (f"{pipes_src}/messages", 0o666) in chmods, chmods
