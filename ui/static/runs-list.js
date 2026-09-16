// Runs list client-side filter/refresh (spec 012 US3).
//
// The list is server-rendered from disk (works with no JS and with the orchestrator stopped).
// This enhances the filter form to refresh the table via /api/runs without a full navigation.

const STATUS_INTENT = { ok: "success", failed: "failure", timeout: "error", running: "running" };

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function rowHtml(r) {
  const intent = STATUS_INTENT[r.status] || "queued";
  const cost = r.cost_usd == null ? "—" : "$" + Number(r.cost_usd).toFixed(4);
  const attempts = r.attempts == null ? "—" : esc(r.attempts);
  return (
    `<tr data-run-row>` +
    `<td><a href="/runs/${encodeURIComponent(r.run_id)}" class="ax-run-link">${esc(r.run_id.slice(0, 8))}</a></td>` +
    `<td>${esc(r.agent)}</td><td>${esc(r.date)}</td><td>${esc(r.started_time || "—")}</td>` +
    `<td><span class="ax-run-status-tag" data-status="${esc(intent)}">` +
    `<span class="ax-status-dot" data-state="${esc(intent === "success" ? "success" : intent === "failure" || intent === "error" ? "error" : intent === "running" ? "running" : "idle")}" aria-hidden="true"></span>` +
    `<span>${esc(r.status)}</span></span></td>` +
    `<td>${esc(r.model || "—")}</td><td>${cost}</td><td>${attempts}</td></tr>`
  );
}

async function refresh(form) {
  const params = new URLSearchParams();
  form.querySelectorAll("[data-runs-filter]").forEach((el) => {
    if (el.value) params.set(el.dataset.runsFilter, el.value);
  });
  let data;
  try {
    const resp = await fetch("/api/runs?" + params.toString(), { headers: { Accept: "application/json" } });
    if (!resp.ok) return;
    data = await resp.json();
  } catch (e) {
    return; // network/orchestrator issue — leave the server-rendered rows in place
  }
  const view = document.getElementById("ax-runs-list");
  let table = document.getElementById("ax-runs-table");
  const rows = data.runs || [];
  if (!rows.length) {
    if (table) table.remove();
    if (!view.querySelector(".ax-runs-empty")) {
      const empty = document.createElement("div");
      empty.className = "ax-runs-empty";
      empty.textContent = "No runs found for these filters.";
      view.appendChild(empty);
    }
    return;
  }
  const empty = view.querySelector(".ax-runs-empty");
  if (empty) empty.remove();
  if (!table) {
    location.search = params.toString(); // no table to patch — fall back to a navigation
    return;
  }
  table.querySelector("tbody").innerHTML = rows.map(rowHtml).join("");
  try {
    history.replaceState(null, "", "/runs?" + params.toString());
  } catch (e) { /* ignore */ }
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("ax-runs-filters");
  if (!form) return;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    refresh(form);
  });
  form.querySelectorAll("[data-runs-filter]").forEach((el) => {
    el.addEventListener("change", () => refresh(form));
  });
});
