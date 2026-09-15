// Agents list view: after first paint, fill the Dagster-derived columns (Latest run, Checks,
// Run history) and each schedule pill's toggle state from GET /api/agents/activity, and narrow
// the already-rendered rows client-side by tab / filter / show-disabled (contract
// agents-list-view §D, FR-013/014/017/020). Columns 1–5 already rendered server-side; this
// module never blocks them — a degraded (reachable:false) read just leaves 6–8 as em-dashes.

const SHOW_DISABLED_KEY = "agentbox.showDisabled";
const TAB_IDS = ["all", "assets", "jobs", "scheduled", "disabled"];

const root = document.getElementById("ax-agents-list");

// ── Narrowing state ─────────────────────────────────────
let activeTab = "all";
let filterText = "";
let showDisabled = false;

function rows() {
  return root ? Array.from(root.querySelectorAll("tbody tr[data-name]")) : [];
}

function matchesTab(row) {
  const kinds = (row.dataset.kind || "").split(/\s+/);
  switch (activeTab) {
    case "assets": return kinds.includes("asset");
    case "jobs": return kinds.includes("job");
    case "scheduled": return row.dataset.scheduled === "true";
    case "disabled": return row.dataset.enabled === "false";
    default: return true;   // all
  }
}

function matchesDisabled(row) {
  if (showDisabled || activeTab === "disabled") return true;
  return row.dataset.enabled !== "false";
}

function matchesFilter(row) {
  if (!filterText) return true;
  const hay = `${row.dataset.name} ${row.dataset.harness} ${row.dataset.model}`.toLowerCase();
  return hay.includes(filterText);
}

function narrow() {
  rows().forEach((row) => {
    row.hidden = !(matchesTab(row) && matchesDisabled(row) && matchesFilter(row));
  });
}

// ── Tabs (bottom-border indicator; syncs to ?tab=) ──────
function reflectTabs() {
  if (!root) return;
  root.querySelectorAll(".ax-tabs [data-tab]").forEach((btn) => {
    const on = btn.dataset.tab === activeTab;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
  });
}

function syncUrl() {
  try {
    const url = new URL(window.location.href);
    if (activeTab === "all") url.searchParams.delete("tab");
    else url.searchParams.set("tab", activeTab);
    window.history.replaceState(null, "", url);
  } catch (e) { /* history unavailable: narrowing still works, URL just not synced */ }
}

function initTabs() {
  if (!root) return;
  root.querySelectorAll(".ax-tabs [data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;
      reflectTabs();
      syncUrl();
      narrow();
    });
  });
}

// ── Toolbar (filter reveal + show-disabled) ─────────────
function initToolbar() {
  const toggle = document.getElementById("ax-filter-toggle");
  const input = document.getElementById("ax-filter-input");
  if (toggle && input) {
    toggle.addEventListener("click", () => {
      const show = input.hidden;
      input.hidden = !show;
      toggle.setAttribute("aria-expanded", show ? "true" : "false");
      if (show) input.focus();
      else { input.value = ""; filterText = ""; narrow(); }
    });
    input.addEventListener("input", () => {
      filterText = input.value.trim().toLowerCase();
      narrow();
    });
  }
  const cb = document.getElementById("ax-show-disabled");
  if (cb) {
    cb.checked = showDisabled;
    cb.addEventListener("change", () => {
      showDisabled = cb.checked;
      try { localStorage.setItem(SHOW_DISABLED_KEY, showDisabled ? "1" : "0"); } catch (e) { /* not persisted */ }
      narrow();
    });
  }
}

// ── After-paint activity fill ───────────────────────────
const RUN_DOT = { SUCCESS: "success", FAILURE: "error", STARTED: "running", CANCELED: "idle", QUEUED: "idle" };
const HIST_STATE = { SUCCESS: "success", FAILURE: "failure" };
const CHECK_META = {
  "pass": { cls: "ax-result--pass", icon: "check-circle", label: "Passed" },
  "warn": { cls: "ax-result--warn", icon: "warn-tri", label: "Failed (warning)" },
  "fail-blocking": { cls: "ax-result--fail", icon: "x-circle", label: "Failed" },
  "not-run": { cls: "", icon: "check-circle", label: "Not run" },
};

function relativeTime(latest) {
  const status = (latest.status || "").toUpperCase();
  if (status === "STARTED" && !latest.end_time) return "running now";
  const t = latest.end_time || latest.start_time;
  if (!t) return status.toLowerCase() || "—";
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - t));
  const units = [["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [name, size] of units) {
    const n = Math.floor(secs / size);
    if (n >= 1) return `${n} ${name}${n === 1 ? "" : "s"} ago`;
  }
  return "just now";
}

function icon(id) {
  return `<svg class="ax-icon" width="16" height="16" aria-hidden="true"><use href="#${id}"></use></svg>`;
}

function fillLatest(row, latest, base) {
  const cell = row.querySelector(".ax-col-latest");
  if (!cell || !latest) return;
  const state = RUN_DOT[(latest.status || "").toUpperCase()] || "idle";
  const text = relativeTime(latest);
  const inner = `<span class="ax-status-dot" data-state="${state}" aria-hidden="true"></span><span>${text}</span>`;
  if (latest.run_id && base) {
    cell.innerHTML =
      `<a class="ax-latest-run" href="${base}/runs/${encodeURIComponent(latest.run_id)}" target="_blank" rel="noopener">${inner}</a>`;
  } else {
    cell.innerHTML = `<span class="ax-latest-run">${inner}</span>`;
  }
}

function fillHistory(row, history) {
  const cell = row.querySelector(".ax-col-history");
  if (!cell || !Array.isArray(history)) return;
  // History arrives newest-first; render newest-at-right (contract §C).
  const bars = history
    .slice()
    .reverse()
    .map((s) => `<i data-state="${HIST_STATE[(s || "").toUpperCase()] || "none"}"></i>`)
    .join("");
  cell.innerHTML = `<div class="ax-run-history">${bars}</div>`;
}

function fillChecks(row, checks) {
  const cell = row.querySelector(".ax-col-checks");
  if (!cell || !Array.isArray(checks) || !checks.length) return;
  const cells = checks
    .map((c) => {
      const meta = CHECK_META[c.status] || CHECK_META["not-run"];
      const title = `${c.name || "check"} — ${meta.label}`;
      return `<span class="ax-result ${meta.cls}" title="${title}" role="img" aria-label="${title}">${icon(meta.icon)}</span>`;
    })
    .join("");
  cell.innerHTML = `<div class="ax-check-grid">${cells}</div>`;
}

// Toggle kind is derived from the store's canonical cron type (contract §0):
// job_schedule → schedule, asset_schedule → sensor.
function kindFromType(type) {
  return type === "asset_schedule" ? "sensor" : "schedule";
}

// Flip one schedule/sensor: POST {name, kind, running}, then reflect the returned state.
// On failure, revert to the prior state and surface the message (contract §B/§C, FR-021).
function bindToggle(input, pill) {
  if (input.dataset.bound === "1") return;
  input.dataset.bound = "1";
  input.addEventListener("change", async () => {
    const name = pill.dataset.dagsterName || input.name;
    const kind = kindFromType(pill.dataset.type);
    const running = input.checked;
    input.disabled = true;
    let out;
    try {
      const resp = await fetch("/api/schedules/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, kind, running }),
      });
      out = await resp.json();
    } catch (e) {
      out = { ok: false, running: null, message: "Dagster unreachable" };
    }
    if (out && out.ok) {
      input.checked = out.running === true;
      input.disabled = false;
      pill.removeAttribute("title");
    } else {
      input.checked = !running;                 // revert; state change did not take
      input.disabled = false;
      const msg = (out && out.message) || "Schedule toggle failed";
      pill.setAttribute("title", msg);
      if (window.agentbox && window.agentbox.showStatus) {
        window.agentbox.showStatus({ message: msg, ok: false });
      }
    }
  });
}

function fillToggles(row, schedules, reachable) {
  const rowDisabled = row.dataset.enabled === "false";
  row.querySelectorAll(".ax-schedule-pill").forEach((pill) => {
    const input = pill.querySelector('input[type="checkbox"]');
    if (!input) return;
    const dname = pill.dataset.dagsterName;
    const sched = schedules ? schedules[dname] : null;
    let title = "";
    if (rowDisabled) title = "Agent is disabled — turn on from Dagster";
    else if (!reachable) title = "Dagster is not reachable";
    else if (!sched || sched.running === null || sched.running === undefined) title = "Turn on from Dagster";

    if (title) {
      input.disabled = true;
      input.checked = sched && sched.running === true;
      pill.setAttribute("title", title);
    } else {
      input.disabled = false;
      input.checked = sched.running === true;
      pill.removeAttribute("title");
      bindToggle(input, pill);                   // enabled: wire the write endpoint
    }
  });
}

function disableAllToggles() {
  rows().forEach((row) => {
    row.querySelectorAll('.ax-schedule-pill input[type="checkbox"]').forEach((i) => { i.disabled = true; });
  });
}

async function loadActivity() {
  const base = root ? root.dataset.runsBase : "";
  let data;
  try {
    const resp = await fetch("/api/agents/activity");
    data = await resp.json();
  } catch (e) {
    data = { reachable: false, agents: {} };
  }
  if (!data || !data.reachable) {
    if (window.agentbox && window.agentbox.showStatus) {
      window.agentbox.showStatus({ message: "Run data unavailable: Dagster is not reachable", ok: false });
    }
    rows().forEach((row) => fillToggles(row, {}, false));
    return;
  }
  const agents = data.agents || {};
  rows().forEach((row) => {
    const a = agents[row.dataset.name];
    fillToggles(row, a ? a.schedules : {}, true);
    if (!a) return;
    fillLatest(row, a.latest_run, base);
    fillHistory(row, a.history);
    fillChecks(row, a.checks);
  });
}

// ── Boot ────────────────────────────────────────────────
function boot() {
  if (!root) return;
  // Active tab from the URL (shareable, survives reload); default All.
  try {
    const tab = new URL(window.location.href).searchParams.get("tab");
    if (tab && TAB_IDS.includes(tab)) activeTab = tab;
  } catch (e) { /* default all */ }
  try { showDisabled = localStorage.getItem(SHOW_DISABLED_KEY) === "1"; } catch (e) { /* default off */ }

  initTabs();
  initToolbar();
  reflectTabs();
  disableAllToggles();   // unknown until the activity read resolves
  narrow();
  loadActivity();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
