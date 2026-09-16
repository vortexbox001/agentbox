// Run-detail page behaviour (spec 012) — composed as the design-system run-detail specimen:
// a Readable/Raw-log segmented toggle over the transcript, collapsible tool cards + context-card
// rows, and in-page conversation search.

// Readable ⇄ Raw-log segmented view toggle.
function initSegmented(root) {
  const seg = root.querySelector("[data-segmented]");
  if (!seg) return;
  const buttons = Array.from(seg.querySelectorAll("[data-view]"));
  const panels = Array.from(root.querySelectorAll("[data-view-panel]"));
  if (!buttons.length || !panels.length) return;
  function show(view) {
    buttons.forEach((b) => {
      const active = b.dataset.view === view;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((p) => { p.hidden = p.dataset.viewPanel !== view; });
  }
  buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  show("readable");
}

// Generic click/keyboard collapse toggle: an element carrying `attr` toggles `.is-collapsed` on
// its `closest(sel)` (tool cards), or the immediately following [data-ctx-body] (context rows).
function bindToggles(root) {
  function toggleTool(head) {
    const tool = head.closest("[data-tool]");
    if (!tool) return;
    const collapsed = tool.classList.toggle("is-collapsed");
    head.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }
  function toggleCtx(row) {
    const body = row.nextElementSibling;
    if (!body || body.dataset.ctxBody === undefined) return;
    body.hidden = !body.hidden;
    row.setAttribute("aria-expanded", body.hidden ? "false" : "true");
  }
  root.addEventListener("click", (e) => {
    const head = e.target.closest("[data-tool-toggle]");
    if (head) { toggleTool(head); return; }
    const row = e.target.closest("[data-ctx-toggle]");
    if (row) toggleCtx(row);
  });
  root.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const head = e.target.closest("[data-tool-toggle]");
    const row = e.target.closest("[data-ctx-toggle]");
    if (head) { e.preventDefault(); toggleTool(head); }
    else if (row) { e.preventDefault(); toggleCtx(row); }
  });
}

// In-page conversation search: hide entries whose text does not contain the query; report count.
function initSearch(root) {
  const timeline = root.querySelector("[data-conversation]");
  const search = root.querySelector("#ax-conv-search");
  const count = root.querySelector("[data-conv-count]");
  if (!timeline || !search) return;
  const entries = Array.from(timeline.querySelectorAll("[data-entry]"));
  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    entries.forEach((entry) => {
      const hit = !q || entry.textContent.toLowerCase().includes(q);
      entry.classList.toggle("is-hidden", !hit);
      if (hit) shown += 1;
    });
    if (count) count.textContent = q ? `${shown} matching` : "";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".ax-run-view") || document;
  initSegmented(root);
  bindToggles(root);
  initSearch(root);
});
