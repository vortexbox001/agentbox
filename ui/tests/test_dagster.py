"""Agents-list activity read (dagster.activity) — asset agents read their run history from the
implicit asset job's runs, not the `agent_<name>` pipeline (bug: overview-missing-asset-runs)."""
import asyncio


def _job_row(name):
    return {"name": name, "dagster_job": f"agent_{name.replace('-', '_')}",
            "dagster_path": f"/locations/definitions.py/jobs/agent_{name.replace('-', '_')}",
            "is_asset": False, "is_job": True, "crons": [], "checks": []}


def _asset_row(name, key, *, job=False, checks=False):
    return {"name": name, "dagster_job": f"agent_{name.replace('-', '_')}",
            "dagster_path": f"/assets/{key}", "is_asset": True, "is_job": job,
            "crons": [], "checks": ([{"name": "c"}] if checks else [])}


# ── _build_query: which pipeline each kind of agent reads ────────────────────

def test_build_query_job_agent_filters_its_own_pipeline():
    import dagster
    q, index = dagster._build_query([_job_row("hello")])
    assert 'pipelineName: "agent_hello"' in q
    assert "__ASSET_JOB" not in q  # no asset agent → no shared asset read
    (_, meta) = index[0]
    assert meta["runs"] == "a0_runs"
    assert meta["asset_key"] is None


def test_build_query_asset_only_agent_has_no_job_read_and_shares_asset_read():
    import dagster
    q, index = dagster._build_query([_asset_row("notes", "notes/daily")])
    (_, meta) = index[0]
    assert meta["runs"] is None                      # asset-only agent has no agent_<name> job
    assert meta["asset_key"] == ["notes", "daily"]
    assert 'pipelineName: "__ASSET_JOB"' in q         # shared asset-job read is emitted
    assert "assetSelection" in q                      # selected so runs can be bucketed by key


def test_build_query_both_kind_agent_reads_job_and_asset():
    import dagster
    q, index = dagster._build_query([_asset_row("impl", "speckit/implement", job=True)])
    (_, meta) = index[0]
    assert meta["runs"] == "a0_runs"                  # job-launched runs still read
    assert meta["asset_key"] == ["speckit", "implement"]
    assert 'pipelineName: "agent_impl"' in q
    assert 'pipelineName: "__ASSET_JOB"' in q


# ── _agent_runs: shaping latest_run + history from the two sources ───────────

def _run(rid, status, start, key=None):
    r = {"runId": rid, "status": status, "startTime": start, "endTime": None}
    if key is not None:
        r["assetSelection"] = [{"path": key}]
    return r


def test_agent_runs_job_only_preserves_dagster_order():
    import dagster
    data = {"a0_runs": {"results": [_run("r2", "SUCCESS", 2.0), _run("r1", "FAILURE", 1.0)]}}
    latest, history = dagster._agent_runs(data, {"runs": "a0_runs", "asset_key": None}, [])
    assert latest["run_id"] == "r2"
    assert history == ["SUCCESS", "FAILURE"]


def test_agent_runs_asset_only_from_shared_read_includes_failures():
    import dagster
    key = ["notes", "daily"]
    asset_runs = [
        _run("other", "SUCCESS", 9.0, key=["refined", "daily"]),  # different asset: ignored
        _run("n2", "SUCCESS", 3.0, key=key),
        _run("n1", "FAILURE", 1.0, key=key),                      # a failed run must still show
    ]
    latest, history = dagster._agent_runs(
        {}, {"runs": None, "asset_key": key}, asset_runs)
    assert latest["run_id"] == "n2"
    assert history == ["SUCCESS", "FAILURE"]


def test_agent_runs_asset_only_no_matching_runs_is_null():
    import dagster
    asset_runs = [_run("other", "SUCCESS", 9.0, key=["refined", "daily"])]
    latest, history = dagster._agent_runs(
        {}, {"runs": None, "asset_key": ["notes", "daily"]}, asset_runs)
    assert latest is None and history is None


def test_agent_runs_both_kind_merges_job_and_asset_newest_first():
    import dagster
    key = ["speckit", "implement"]
    data = {"a0_runs": {"results": [_run("job-old", "SUCCESS", 1.0)]}}
    asset_runs = [_run("auto-new", "FAILURE", 5.0, key=key)]
    latest, history = dagster._agent_runs(
        data, {"runs": "a0_runs", "asset_key": key}, asset_runs)
    assert latest["run_id"] == "auto-new"            # automation run is newer than the job launch
    assert history == ["FAILURE", "SUCCESS"]


# ── activity(): end-to-end with the GraphQL transport stubbed ────────────────

class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json):
        return _FakeResp(self._payload)


def test_activity_populates_asset_agent_from_shared_asset_runs(settings, monkeypatch):
    import dagster
    key = ["notes", "daily"]
    payload = {"data": {
        "asset_runs": {"__typename": "Runs", "results": [
            _run("n2", "SUCCESS", 3.0, key=key),
            _run("elsewhere", "SUCCESS", 4.0, key=["refined", "daily"]),
            _run("n1", "FAILURE", 1.0, key=key),
        ]},
    }}
    monkeypatch.setattr(dagster.httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    out = asyncio.run(dagster.activity([_asset_row("notes", "notes/daily")]))
    assert out["reachable"] is True
    agent = out["agents"]["notes"]
    assert agent["latest_run"]["run_id"] == "n2"
    assert agent["history"] == ["SUCCESS", "FAILURE"]
