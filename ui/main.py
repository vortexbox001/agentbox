"""Agentbox control center: CRUD over agent YAMLs + Dagster reload + deep links."""
import glob, os, yaml, httpx
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

AGENTS_DIR = "/opt/agentbox/agents"
DAGSTER_URL = os.environ.get("DAGSTER_URL", "http://dagster-webserver:3000")

app = FastAPI(title="Agentbox")

def load_agents():
    out = []
    for p in sorted(glob.glob(f"{AGENTS_DIR}/*.yaml")):
        with open(p) as f:
            out.append(yaml.safe_load(f))
    return out

@app.get("/", response_class=HTMLResponse)
def index():
    rows = ""
    for a in load_agents():
        jobname = "agent_" + a["name"].replace("-", "_")
        rows += (
            f"<tr><td>{a['name']}</td><td>{a['harness']}</td>"
            f"<td>{a.get('schedule') or 'manual'}</td>"
            f"<td>{'on' if a.get('enabled', True) else 'off'}</td>"
            f"<td><a href='{DAGSTER_URL}/jobs/{jobname}'>runs</a></td></tr>"
        )
    return f"""
    <h1>Agentbox</h1>
    <table border=1 cellpadding=6>
      <tr><th>agent</th><th>harness</th><th>schedule</th><th>enabled</th><th>history</th></tr>
      {rows}
    </table>
    <p><form method=post action=/reload><button>Reload Dagster</button></form></p>
    """

@app.post("/reload")
async def reload():
    async with httpx.AsyncClient() as c:
        await c.post(
            f"{DAGSTER_URL}/graphql",
            json={"query": 'mutation { reloadWorkspace { __typename } }'},
        )
    return RedirectResponse("/", status_code=303)
