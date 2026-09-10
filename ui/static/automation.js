// Automation view (spec 005): list every non-template agent with its trigger, let the
// operator switch on-demand ↔ cron, and save the whole set to automation/ with a Dagster
// reload. Triggering lives here, not in the agent form. See contracts/ui-automation.md.

const rowsEl = document.getElementById("ax-automation-rows");
const saveBtn = document.getElementById("ax-automation-save");
const banner = document.getElementById("ax-automation-banner");

let dirty = false;

function showBanner(kind, text) {
  banner.hidden = false;
  banner.className = "ax-banner ax-banner--" + kind;
  banner.textContent = text;
}

function markDirty() {
  dirty = true;
  saveBtn.disabled = false;
}

const CRON_RE = /^\S+\s+\S+\s+\S+\s+\S+\s+\S+$/;
function cronShapeError(v) {
  const s = (v || "").trim();
  if (!s) return "a cron trigger needs an expression";
  if (s.startsWith("@")) return "cron macros like @daily are not supported; use a 5-field expression";
  if (!CRON_RE.test(s)) return "cron must have exactly five fields (minute hour day month weekday)";
  return null;
}

function render(agents) {
  rowsEl.textContent = "";
  if (!agents.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="4"><span class="ax-muted">No agents.</span></td>';
    rowsEl.appendChild(tr);
    return;
  }
  for (const a of agents) {
    const tr = document.createElement("tr");
    tr.dataset.name = a.name;
    if (!a.enabled) tr.className = "ax-row--disabled";

    const nameTd = document.createElement("td");
    nameTd.innerHTML = `<a href="/agents/${a.name}">${a.name}</a>`;
    if (!a.enabled) {
      const badge = document.createElement("span");
      badge.className = "ax-badge ax-badge--disabled";
      badge.textContent = "disabled";
      badge.title = "This agent is disabled — its trigger stays inactive until you enable it.";
      nameTd.append(" ", badge);
    }

    const modeTd = document.createElement("td");
    modeTd.innerHTML = `<span class="ax-badge ax-badge--harness">${a.mode}</span>`;

    const trigTd = document.createElement("td");
    const sel = document.createElement("select");
    sel.className = "ax-select ax-automation-mode";
    sel.innerHTML = '<option value="on_demand">on demand</option><option value="cron">cron</option>';
    trigTd.appendChild(sel);

    const cronTd = document.createElement("td");
    const input = document.createElement("input");
    input.type = "text";
    input.className = "ax-input ax-automation-cron";
    input.placeholder = "e.g. 30 2 * * *";
    cronTd.appendChild(input);
    const err = document.createElement("div");
    err.className = "ax-field-error";
    err.hidden = true;
    cronTd.appendChild(err);

    const isCron = a.trigger && a.trigger.cron;
    sel.value = isCron ? "cron" : "on_demand";
    input.value = isCron ? a.trigger.cron : "";
    input.disabled = !isCron;

    sel.addEventListener("change", () => {
      input.disabled = sel.value !== "cron";
      if (sel.value !== "cron") { input.value = ""; err.hidden = true; }
      else input.focus();
      markDirty();
    });
    input.addEventListener("input", () => {
      const e = cronShapeError(input.value);
      err.hidden = !e;
      err.textContent = e || "";
      markDirty();
    });

    tr.append(nameTd, modeTd, trigTd, cronTd);
    rowsEl.appendChild(tr);
  }
}

function collect() {
  const triggers = {};
  let ok = true;
  for (const tr of rowsEl.querySelectorAll("tr[data-name]")) {
    const name = tr.dataset.name;
    const mode = tr.querySelector(".ax-automation-mode").value;
    if (mode === "cron") {
      const cron = tr.querySelector(".ax-automation-cron").value.trim();
      const e = cronShapeError(cron);
      const errEl = tr.querySelector(".ax-field-error");
      if (e) { errEl.hidden = false; errEl.textContent = e; ok = false; continue; }
      triggers[name] = { cron };
    } else {
      triggers[name] = { on_demand: true };
    }
  }
  return ok ? triggers : null;
}

async function load() {
  try {
    const resp = await fetch("/api/automation");
    const data = await resp.json();
    if (!resp.ok) { showBanner("error", data.message || "Failed to load automation"); return; }
    render(data.agents || []);
  } catch (e) {
    showBanner("error", "Failed to load automation: " + e);
  }
}

async function save() {
  const triggers = collect();
  if (!triggers) { showBanner("error", "Fix the highlighted cron expressions first."); return; }
  saveBtn.disabled = true;
  try {
    const resp = await fetch("/api/automation", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ triggers }),
    });
    const data = await resp.json();
    if (resp.status === 400 && data.error === "validation") {
      const fields = Object.entries(data.fields || {}).map(([k, v]) => `${k}: ${v}`).join("; ");
      showBanner("error", "Rejected — " + fields);
      saveBtn.disabled = false;
      return;
    }
    if (!resp.ok) { showBanner("error", data.message || "Save failed"); saveBtn.disabled = false; return; }
    showBanner(data.ok ? "ok" : "error", data.ok ? "Saved. " + (data.message || "Reloaded.") : ("Saved, but reload failed: " + (data.message || "")));
    dirty = false;
  } catch (e) {
    showBanner("error", "Save failed: " + e);
    saveBtn.disabled = false;
  }
}

saveBtn.addEventListener("click", save);
load();
