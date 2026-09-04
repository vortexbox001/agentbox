"""Generic light-agent runner: reads env vars, calls LiteLLM, writes output."""
import os, sys, json, datetime, urllib.request

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
stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, f"{stamp}.md")
with open(out_path, "w") as f:
    f.write(text)
print(json.dumps({"status": "ok", "output": out_path, "chars": len(text)}))
