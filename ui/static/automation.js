// Automation view (spec 006): one group per agent, a row per kind the agent is (asset / job /
// both). Each row switches on-demand ↔ cron independently; saving writes each agent's own
// `triggers:` block via PUT /api/automation and reloads Dagster. Uses the shared dropdown
// (dropdown.enhanceSelects) and the shared notice (shell.showStatus) — no bespoke banner.
// See specs/006-explicit-asset-job/contracts/ui-automation-and-shell.md §2.

import { showStatus, reloadDagster } from "/static/shell.js";
import { enhanceSelects } from "/static/dropdown.js";

const rowsEl = document.getElementById("ax-automation-rows");
const saveBtn = document.getElementById("ax-automation-save");

let dirty = false;

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

const KIND_LABEL = { asset: "Asset schedule", job: "Job schedule" };

// One editable schedule row for a kind: a trigger select (on demand / cron) + cron input +
// reserved warning slot, plus an optional partition-fallback marker on the asset row.
function scheduleRow(kind, sched) {
  const row = document.createElement("div");
  row.className = "ax-automation-schedule";
  row.dataset.kind = kind;

  const label = document.createElement("span");
  label.className = "ax-automation-kind";
  label.textContent = KIND_LABEL[kind] || kind;
  row.appendChild(label);

  const sel = document.createElement("select");
  sel.className = "ax-select ax-automation-mode";
  sel.innerHTML = '<option value="manual">on demand</option><option value="cron">cron</option>';
  row.appendChild(sel);

  const cronWrap = document.createElement("div");
  cronWrap.className = "ax-automation-cron-wrap";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "ax-input ax-automation-cron";
  input.placeholder = "e.g. 30 2 * * *";
  const err = document.createElement("div");
  err.className = "ax-field-error";   // always present + min-height: reserves one line so a
  err.textContent = "";               // warning never shifts the row (SC-007)
  cronWrap.append(input, err);
  row.appendChild(cronWrap);

  const isCron = !!(sched && sched.cron);
  sel.value = isCron ? "cron" : "manual";
  input.value = isCron ? sched.cron : "";
  input.disabled = !isCron;

  if (kind === "asset" && sched && sched.fallback) {
    const mark = document.createElement("span");
    mark.className = "ax-badge ax-badge--fallback";
    mark.textContent = "partition fallback";
    mark.title = "on_cron cannot target this asset's partition on the installed Dagster; a "
      + "partition-filling job schedule is used instead (FR-015).";
    // Inside the label cell, not a trailing sibling: the row is a fixed-track grid, and an
    // extra item would give asset rows a different column shape than job rows.
    label.appendChild(mark);
  }

  sel.addEventListener("change", () => {
    input.disabled = sel.value !== "cron";
    if (sel.value !== "cron") { input.value = ""; err.textContent = ""; }
    else input.focus();
    markDirty();
  });
  input.addEventListener("input", () => {
    err.textContent = cronShapeError(input.value) || "";
    markDirty();
  });

  return row;
}

function render(agents) {
  rowsEl.textContent = "";
  if (!agents.length) {
    rowsEl.innerHTML = '<p class="ax-muted">No agents.</p>';
    return;
  }
  for (const a of agents) {
    const group = document.createElement("div");
    group.className = "ax-automation-agent";
    group.dataset.name = a.name;
    if (!a.enabled) group.classList.add("ax-row--disabled");

    const head = document.createElement("div");
    head.className = "ax-automation-agent-head";
    const link = document.createElement("a");
    link.href = `/agents/${a.name}`;
    link.textContent = a.name;
    head.appendChild(link);
    const harness = document.createElement("span");
    harness.className = "ax-badge ax-badge--harness";
    harness.textContent = a.harness || "";
    head.appendChild(harness);
    if (!a.enabled) {
      const badge = document.createElement("span");
      badge.className = "ax-badge ax-badge--disabled";
      badge.textContent = "disabled";
      badge.title = "This agent is disabled — its trigger stays inactive until you enable it.";
      head.appendChild(badge);
    }
    group.appendChild(head);

    const schedules = a.schedules || [];
    if (!schedules.length) {
      const none = document.createElement("p");
      none.className = "ax-muted ax-automation-empty";
      none.textContent = "This agent is neither an asset nor a job — edit it to set a nature.";
      group.appendChild(none);
    }
    for (const s of schedules) group.appendChild(scheduleRow(s.kind, s));
    rowsEl.appendChild(group);
  }
  enhanceSelects(rowsEl);   // shared dropdown for every row select, including these new rows
}

// Gather { "<name>": { asset_schedule?, job_schedule? } } for every editable row.
function collect() {
  const triggers = {};
  let ok = true;
  for (const group of rowsEl.querySelectorAll(".ax-automation-agent")) {
    const name = group.dataset.name;
    const spec = {};
    for (const row of group.querySelectorAll(".ax-automation-schedule")) {
      const key = `${row.dataset.kind}_schedule`;
      const mode = row.querySelector(".ax-automation-mode").value;
      if (mode === "cron") {
        const cron = row.querySelector(".ax-automation-cron").value.trim();
        const e = cronShapeError(cron);
        const errEl = row.querySelector(".ax-field-error");
        if (e) { errEl.textContent = e; ok = false; continue; }
        spec[key] = cron;
      } else {
        spec[key] = null;   // on-demand: clear the schedule
      }
    }
    if (Object.keys(spec).length) triggers[name] = spec;
  }
  return ok ? triggers : null;
}

async function load() {
  try {
    const resp = await fetch("/api/automation");
    const data = await resp.json();
    if (!resp.ok) { showStatus({ message: data.message || "Failed to load automation", ok: false }); return; }
    render(data.agents || []);
  } catch (e) {
    showStatus({ message: "Failed to load automation: " + e, ok: false });
  }
}

async function save() {
  const triggers = collect();
  if (!triggers) { showStatus({ message: "Fix the highlighted cron expressions first.", ok: false }); return; }
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
      showStatus({ message: "Rejected — " + fields, ok: false });
      saveBtn.disabled = false;
      return;
    }
    if (!resp.ok) { showStatus({ message: data.message || "Save failed", ok: false }); saveBtn.disabled = false; return; }
    if (data.ok) {
      showStatus({ message: "Saved. " + (data.message || "Dagster reloaded."), ok: true });
    } else {
      showStatus({ message: "Saved, but reload failed: " + (data.message || ""), ok: false, retry: true });
    }
    dirty = false;
  } catch (e) {
    showStatus({ message: "Save failed: " + e, ok: false });
    saveBtn.disabled = false;
  }
}

saveBtn.addEventListener("click", save);
load();
