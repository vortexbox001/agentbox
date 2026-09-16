"""Launch/Materialize a run from the agent page (spec 012 follow-up)."""
import asyncio
import datetime


# ── endpoint (with the Dagster launch stubbed) ──────────────────────────────

def test_launch_job_agent_returns_run_url(settings, client, dagster_stub):
    r = client.post("/api/agents/hello-example/launch")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["run_url"].endswith("/runs/run-abc123")
    # the job agent's cfg reached dagster.launch
    assert dagster_stub.launch_calls[0]["name"] == "hello-example"
    assert dagster_stub.launch_calls[0]["job"] is True


def test_launch_asset_agent(settings, client, dagster_stub):
    r = client.post("/api/agents/hello-asset-example/launch")
    assert r.status_code == 200 and r.json()["ok"] is True
    cfg = dagster_stub.launch_calls[0]
    assert cfg["asset"] == "reports/hello"


def test_launch_unknown_agent_404(settings, client, dagster_stub):
    assert client.post("/api/agents/nope/launch").status_code == 404


def test_launch_unsafe_name_404(settings, client, dagster_stub):
    assert client.post("/api/agents/..%2fetc/launch").status_code == 404


def test_launch_failure_is_reported(settings, client, dagster_stub):
    dagster_stub.launch_result = {"ok": False, "run_id": None, "message": "job not found"}
    body = client.post("/api/agents/hello-example/launch").json()
    assert body["ok"] is False
    assert body["run_url"] is None
    assert body["message"] == "job not found"


# ── dagster.launch query construction (httpx stubbed) ───────────────────────

class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    def __init__(self, recorder, payload):
        self._rec = recorder
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json):
        self._rec["query"] = json["query"]
        return _FakeResp(self._payload)


def _run_launch(monkeypatch, cfg, payload):
    import dagster
    rec = {}
    ok_payload = payload or {"data": {"launchRun": {"__typename": "LaunchRunSuccess",
                                                    "run": {"runId": "rid-1"}}}}
    monkeypatch.setattr(dagster.httpx, "AsyncClient",
                        lambda *a, **k: _FakeClient(rec, ok_payload))
    out = asyncio.run(dagster.launch(cfg))
    return out, rec.get("query", "")


def test_launch_job_query_targets_job(settings, monkeypatch):
    out, q = _run_launch(monkeypatch, {"name": "hello-example", "job": True}, None)
    assert out["ok"] is True and out["run_id"] == "rid-1"
    assert 'jobName: "agent_hello_example"' in q
    assert "assetSelection" not in q


def test_launch_asset_query_targets_implicit_job_with_selection(settings, monkeypatch):
    out, q = _run_launch(monkeypatch, {"name": "x", "asset": "reports/hello", "partition": "none"}, None)
    assert '__ASSET_JOB' in q
    assert 'assetSelection: [{path: ["reports", "hello"]}]' in q
    assert "dagster/partition" not in q  # unpartitioned → no partition tag


def test_launch_daily_asset_tags_todays_partition(settings, monkeypatch):
    out, q = _run_launch(monkeypatch, {"name": "x", "asset": "reports/hello", "partition": "daily"}, None)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    assert "dagster/partition" in q and today in q


def test_launch_reports_dagster_error(settings, monkeypatch):
    payload = {"data": {"launchRun": {"__typename": "PipelineNotFoundError",
                                      "message": "no such job"}}}
    out, _q = _run_launch(monkeypatch, {"name": "x", "job": True}, payload)
    assert out["ok"] is False and out["message"] == "no such job"
