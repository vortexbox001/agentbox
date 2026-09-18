// Runs overview client behaviour (spec 015 US2/US5).
//
// The list is server-rendered from disk and works with no JS (tabs render server-side, the
// filter form GETs /runs, pagination Prev/Next are real ?page= links). This module enhances it:
// toggle the ghost-Filter form, filter-as-you-type, switch tabs, and page — each keeping
// tab/q/agent/date_from/date_to/page in the URL (history.replaceState) and refreshing rows from
// GET /api/runs without a full reload. It degrades to a full navigation when history/fetch fail.

const root = document.getElementById("ax-runs-list");
const TAB_IDS = ["all", "in_progress", "succeeded", "failed"];

const state = { tab: "all", q: "", agent: "", date_from: "", date_to: "", page: 1 };

// Presented status → tag intent / dot state / label (mirrors dagster._status_intent, R8).
const PRESENT = {
  succeeded: { intent: "success", dot: "success", label: "succeeded" },
  failed: { intent: "failure", dot: "error", label: "failed" },
  timed_out: { intent: "error", dot: "error", label: "timed out" },
  cancelled: { intent: "error", dot: "error", label: "cancelled" },
  in_progress: { intent: "running", dot: "running", label: "in progress" },
  queued: { intent: "queued", dot: "idle", label: "queued" },
  unknown: { intent: "queued", dot: "idle", label: "unknown" },
};

const CHECK_META = {
  "pass": { cls: "ax-result--pass", icon: "check-circle", label: "Passed" },
  "warn": { cls: "ax-result--warn", icon: "warn-tri", label: "Failed (warning)" },
  "fail-blocking": { cls: "ax-result--fail", icon: "x-circle", label: "Failed" },
  "not-run": { cls: "", icon: "check-circle", label: "Not run" },
};

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function icon(id) {
  return `<svg class="ax-icon" width="16" height="16" aria-hidden="true"><use href="#${esc(id)}"></use></svg>`;
}

// Re-localise a machine-readable ISO timestamp to the browser tz as `Sep 17, 1:15 PM` (R7).
function fmtCreated(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  const date = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${date}, ${time}`;
}

// Rewrite every server-rendered (or JS-rendered) Created cell to the browser's local time.
function localizeCreated(scope) {
  (scope || document).querySelectorAll(".ax-run-created[data-created-iso]").forEach((el) => {
    const iso = el.dataset.createdIso;
    if (!iso) return;
    const label = fmtCreated(iso);
    if (label) { el.textContent = label; el.setAttribute("title", iso); }
  });
}

// ── Row rendering (matches runs/list.html cell-for-cell) ─
function statusCell(r) {
  const p = PRESENT[r.status] || PRESENT.unknown;
  const tag =
    `<span class="ax-run-status-tag" data-status="${esc(p.intent)}">` +
    `<span class="ax-status-dot" data-state="${esc(p.dot)}" aria-hidden="true"></span>` +
    `<span>${esc(p.label)}</span></span>`;
  const mark = r.last_known
    ? ` <span class="ax-badge ax-badge--last-known" title="Dagster is unreachable or has no record for this run — showing the last known status.">last-known</span>`
    : "";
  return `<td>${tag}${mark}</td>`;
}

function runCell(r) {
  const link = `<a href="/runs/${encodeURIComponent(r.run_id)}" class="ax-run-link">${esc(r.run_id.slice(0, 8))}</a>`;
  const ext = r.dagster_url
    ? `<a class="ax-run-dagster-link" href="${esc(r.dagster_url)}" target="_blank" rel="noopener" title="Open this run in Dagster" aria-label="Open this run in Dagster">${icon("external")}</a>`
    : "";
  return `<td class="ax-run-cell">${link}${ext}</td>`;
}

function muted() { return `<span class="ax-muted">—</span>`; }

function checksCell(r) {
  if (!Array.isArray(r.checks) || !r.checks.length) return `<td class="ax-col-checks">${muted()}</td>`;
  const cells = r.checks.map((c) => {
    const m = CHECK_META[c.status] || CHECK_META["not-run"];
    const title = `${esc(c.name || "check")} — ${m.label}`;
    return `<span class="ax-result ${m.cls}" role="img" title="${title}" aria-label="${title}">${icon(m.icon)}</span>`;
  }).join("");
  return `<td class="ax-col-checks"><div class="ax-check-grid">${cells}</div></td>`;
}

function rowHtml(r) {
  const agent = r.agent
    ? `<a class="ax-mono" href="/agents/${encodeURIComponent(r.agent)}">${esc(r.agent)}</a>` : muted();
  const model = r.model ? `<span class="ax-mono" title="${esc(r.model)}">${esc(r.model)}</span>` : muted();
  const target = r.target && r.target !== "—" ? esc(r.target) : muted();
  const launched = r.launched_by && r.launched_by !== "—" ? esc(r.launched_by) : muted();
  const created = r.created
    ? `<span class="ax-run-created" data-created-iso="${esc(r.created_iso)}" title="${esc(r.created_iso)}">${esc(r.created)}</span>` : muted();
  const duration = r.duration ? esc(r.duration) : muted();
  const cost = r.cost_usd != null ? esc(r.cost_usd) : muted();
  return (
    `<tr data-run-row>` +
    runCell(r) +
    `<td>${agent}</td><td>${model}</td><td>${target}</td><td>${launched}</td>` +
    checksCell(r) + statusCell(r) +
    `<td>${created}</td><td>${duration}</td><td>${cost}</td></tr>`
  );
}

// ── URL / query state ───────────────────────────────────
function buildParams(includePage) {
  const p = new URLSearchParams();
  if (state.tab !== "all") p.set("tab", state.tab);
  if (state.q) p.set("q", state.q);
  if (state.agent) p.set("agent", state.agent);
  if (state.date_from) p.set("date_from", state.date_from);
  if (state.date_to) p.set("date_to", state.date_to);
  if (includePage && state.page > 1) p.set("page", String(state.page));
  return p;
}

function syncUrl() {
  try {
    const qs = buildParams(true).toString();
    window.history.replaceState(null, "", qs ? "/runs?" + qs : "/runs");
  } catch (e) { /* history unavailable: refresh still works, URL just not synced */ }
}

// ── Tabs + pagination reflection ────────────────────────
function reflectTabs(counts) {
  if (!root) return;
  root.querySelectorAll(".ax-tabs [data-tab]").forEach((btn) => {
    const on = btn.dataset.tab === state.tab;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
    if (counts) {
      const badge = btn.querySelector(".ax-tab-count");
      const n = counts[btn.dataset.tab];
      if (badge && n !== undefined) badge.textContent = n;
    }
  });
}

function pageLink(cls, rel, label, disabled, page) {
  if (disabled) return `<span class="ax-btn ax-btn--ghost ax-btn--outlined ${cls}" aria-disabled="true">${label}</span>`;
  const p = buildParams(false);
  p.set("page", String(page));
  return `<a class="ax-btn ax-btn--ghost ax-btn--outlined ${cls}" rel="${rel}" href="?${p.toString()}">${label}</a>`;
}

function renderPagination(page, pages) {
  let nav = root.querySelector(".ax-pagination");
  if (pages <= 1) { if (nav) nav.remove(); return; }
  if (!nav) {
    nav = document.createElement("nav");
    nav.className = "ax-pagination";
    nav.setAttribute("aria-label", "Pagination");
    root.appendChild(nav);
  }
  nav.innerHTML =
    pageLink("ax-pagination-prev", "prev", "Prev", page <= 1, page - 1) +
    `<span class="ax-pagination-indicator">Page ${page} of ${pages}</span>` +
    pageLink("ax-pagination-next", "next", "Next", page >= pages, page + 1);
  bindPagination(nav);
}

function bindPagination(nav) {
  nav.querySelectorAll("a[rel='prev'], a[rel='next']").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      state.page = a.rel === "prev" ? Math.max(1, state.page - 1) : state.page + 1;
      refresh();
    });
  });
}

// ── Refresh from /api/runs ──────────────────────────────
async function refresh() {
  let data;
  try {
    const resp = await fetch("/api/runs?" + buildParams(true).toString(),
      { headers: { Accept: "application/json" } });
    if (!resp.ok) return;
    data = await resp.json();
  } catch (e) {
    // Network issue: fall back to a full navigation so the view still updates.
    try { location.search = buildParams(true).toString(); } catch (_) { /* ignore */ }
    return;
  }
  state.page = data.page || 1;               // adopt the server's clamped page
  const rows = data.runs || [];
  let table = document.getElementById("ax-runs-table");
  let empty = root.querySelector(".ax-runs-empty");
  if (!rows.length) {
    if (table) table.remove();
    if (!empty) {
      empty = document.createElement("div");
      empty.className = "ax-runs-empty";
      empty.textContent = "No runs found for this view.";
      const nav = root.querySelector(".ax-pagination");
      root.insertBefore(empty, nav || null);
    }
  } else {
    if (empty) empty.remove();
    if (!table) { location.search = buildParams(true).toString(); return; }
    const tbody = table.querySelector("tbody");
    tbody.innerHTML = rows.map(rowHtml).join("");
    localizeCreated(tbody);
  }
  reflectTabs(data.counts);
  renderPagination(data.page || 1, data.pages || 1);
  syncUrl();
}

// ── Wiring ──────────────────────────────────────────────
function initTabs() {
  root.querySelectorAll(".ax-tabs [data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab;
      state.page = 1;                         // changing tab returns to page 1 (FR-027)
      const hidden = document.querySelector("[data-runs-tab]");
      if (hidden) hidden.value = state.tab;
      reflectTabs();
      refresh();
    });
  });
}

function initFilters() {
  const toggle = document.getElementById("ax-runs-filter-toggle");
  const form = document.getElementById("ax-runs-filters");
  if (toggle && form) {
    toggle.addEventListener("click", () => {
      const show = form.hidden;
      form.hidden = !show;
      toggle.setAttribute("aria-expanded", show ? "true" : "false");
      if (show) { const q = document.getElementById("ax-runs-q"); if (q) q.focus(); }
    });
    // Progressive enhancement: keep the form working, but refresh in place on submit.
    form.addEventListener("submit", (e) => { e.preventDefault(); state.page = 1; refresh(); });
  }
  const onChange = () => { state.page = 1; refresh(); };  // any filter change → page 1 (FR-027)
  const q = document.getElementById("ax-runs-q");
  if (q) q.addEventListener("input", () => { state.q = q.value.trim(); onChange(); });
  document.querySelectorAll("[data-runs-filter]").forEach((el) => {
    const key = el.dataset.runsFilter;
    if (key === "q") return;
    el.addEventListener("change", () => { state[key] = el.value; onChange(); });
  });
}

function boot() {
  if (!root) return;
  try {
    const url = new URL(window.location.href);
    const tab = url.searchParams.get("tab");
    if (tab && TAB_IDS.includes(tab)) state.tab = tab;
    state.q = url.searchParams.get("q") || "";
    state.agent = url.searchParams.get("agent") || "";
    state.date_from = url.searchParams.get("date_from") || "";
    state.date_to = url.searchParams.get("date_to") || "";
    const page = parseInt(url.searchParams.get("page") || "1", 10);
    state.page = page >= 1 ? page : 1;
  } catch (e) { /* defaults */ }

  initTabs();
  initFilters();
  reflectTabs();
  localizeCreated(document);                  // localise the server-rendered first paint
  const nav = root.querySelector(".ax-pagination");
  if (nav) bindPagination(nav);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
