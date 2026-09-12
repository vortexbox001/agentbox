"""Generic light-agent runner: reads env vars, calls LiteLLM, writes output.

Also emits the common run report (spec 007) over Dagster Pipes. The runner STILL
prints its native event to stdout unchanged (as it did before this feature), so the
orchestrator's ``.jsonl`` transcript for api runs is byte-for-byte what it was — the
Pipes report travels over ``/pipes/messages``, not in place of stdout (FR-006).
"""
import os, sys, json, uuid, datetime, urllib.request

from lib.agent_report import RunReport, emit, snapshot_output, count_written

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000/v1/chat/completions")
MODEL = os.environ.get("AGENT_MODEL", "cheap")
PROMPT_FILE = os.environ.get("AGENT_PROMPT_FILE", "/config/prompt.md")
OUT_DIR = os.environ.get("AGENT_OUTPUT_DIR", "/output")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "1024"))


def report_from_response(data: dict, cost_header, files_written: int, text: str) -> RunReport:
    """Build the run report from a LiteLLM chat-completions response.

    Tokens come from the response ``usage``; ``cost_usd`` from LiteLLM's
    ``x-litellm-response-cost`` response header (non-null for api, SC-001); one turn;
    the model's message text is the run's closing note.
    """
    usage = data.get("usage") or {}
    cost = None
    if cost_header not in (None, ""):
        try:
            cost = float(cost_header)
        except (TypeError, ValueError):
            cost = None
    return RunReport(
        status="ok",
        tokens_in=usage.get("prompt_tokens"),
        tokens_out=usage.get("completion_tokens"),
        turns=1,
        cost_usd=cost,
        files_written=files_written,
        error=None,
        notes=text or None,
    )


def main() -> None:
    before = snapshot_output(OUT_DIR)
    with open(PROMPT_FILE) as f:
        prompt = f.read()

    req = urllib.request.Request(
        LITELLM_URL,
        data=json.dumps({
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['LITELLM_KEY']}",
        },
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
        # LiteLLM reports the computed request cost in a response header (non-null)
        cost_header = resp.headers.get("x-litellm-response-cost")

    text = data["choices"][0]["message"]["content"]
    # the orchestrator supplies both; fall back to local values when run by hand
    stamp = os.environ.get("AGENTBOX_RUN_STAMP") or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    session_id = os.environ.get("AGENTBOX_SESSION_ID") or str(uuid.uuid4())
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{stamp}_response_{session_id}.md")
    with open(out_path, "w") as f:
        f.write(text)
    # native event to stdout — unchanged from before spec 007 (FR-006)
    print(json.dumps({"status": "ok", "output": out_path, "chars": len(text)}))

    report = report_from_response(data, cost_header, count_written(before, path=OUT_DIR), text)
    emit(report)


if __name__ == "__main__":
    main()
