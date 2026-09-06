"""Generic light-agent runner: reads env vars, calls LiteLLM, writes output."""
import os, sys, json, uuid, datetime, urllib.request

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000/v1/chat/completions")
MODEL = os.environ.get("AGENT_MODEL", "cheap")
PROMPT_FILE = os.environ.get("AGENT_PROMPT_FILE", "/config/prompt.md")
OUT_DIR = os.environ.get("AGENT_OUTPUT_DIR", "/output")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "1024"))

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

text = data["choices"][0]["message"]["content"]
# the orchestrator supplies both; fall back to local values when run by hand
stamp = os.environ.get("AGENTBOX_RUN_STAMP") or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
session_id = os.environ.get("AGENTBOX_SESSION_ID") or str(uuid.uuid4())
os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, f"{stamp}_response_{session_id}.md")
with open(out_path, "w") as f:
    f.write(text)
print(json.dumps({"status": "ok", "output": out_path, "chars": len(text)}))
