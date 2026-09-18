// Run-detail page behaviour (spec 017): five collapsible sections with per-browser persistence,
// IN/OUT tool-card clamp/expand (+ expand-all/collapse-all), transcript search over message and
// tool IN/OUT content with auto-expand-on-match, the Readable/Raw-log toggle, and the context-card
// rows. All view chrome — nothing is written to the run record.

const SECTIONS_KEY = "agentbox.runDetail.sections";

function loadSectionState() {
  try {
    const raw = localStorage.getItem(SECTIONS_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (e) {
    return {}; // disabled / unavailable localStorage → server defaults, no error (FR-004)
  }
}

function saveSectionState(state) {
  try {
    localStorage.setItem(SECTIONS_KEY, JSON.stringify(state));
  } catch (e) {
    /* persistence unavailable — the session still works, just unremembered */
  }
}

function applySection(section, open) {
  const head = section.querySelector("[data-section-toggle]");
  const body = section.querySelector(".ax-section-body");
  if (open) section.removeAttribute("data-collapsed");
  else section.setAttribute("data-collapsed", "");
  if (head) head.setAttribute("aria-expanded", open ? "true" : "false");
  if (body) body.hidden = !open;
}

// Section disclosure toggles + persistence, under ONE shared localStorage key across all
// /runs/{id} pages, NOT keyed per run id (FR-004).
function initSections(root) {
  const sections = Array.from(root.querySelectorAll("[data-section]"));
  const state = loadSectionState();
  sections.forEach((sec) => {
    const id = sec.dataset.sectionId;
    const serverOpen = !sec.hasAttribute("data-collapsed");
    const open = id in state ? !!state[id] : serverOpen;
    applySection(sec, open);
    const head = sec.querySelector("[data-section-toggle]");
    if (!head) return;
    head.addEventListener("click", () => {
      const nowOpen = sec.hasAttribute("data-collapsed"); // collapsed → opening
      applySection(sec, nowOpen);
      state[id] = nowOpen;
      saveSectionState(state);
    });
  });
}

// Readable ⇄ Raw-log segmented view toggle (now inside the Transcript section header).
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

// Flip one IN/OUT row's clamp; the "Show all N lines" link becomes "Show less".
function setIoRow(row, expanded) {
  if (!row.classList.contains("is-overflow")) return;
  row.classList.toggle("is-expanded", expanded);
  const btn = row.querySelector("[data-io-toggle]");
  if (btn) {
    btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    const n = row.dataset.ioLines || "";
    btn.textContent = expanded ? "Show less" : `Show all ${n} lines`;
  }
}

// Click/keyboard collapse toggles: IN/OUT rows (clamp), and context-card rows.
function bindToggles(root) {
  function toggleCtx(row) {
    const body = row.nextElementSibling;
    if (!body || body.dataset.ctxBody === undefined) return;
    body.hidden = !body.hidden;
    row.setAttribute("aria-expanded", body.hidden ? "false" : "true");
  }
  function toggleIo(row) {
    setIoRow(row, !row.classList.contains("is-expanded"));
  }
  root.addEventListener("click", (e) => {
    const ioBtn = e.target.closest("[data-io-toggle]");
    if (ioBtn) { toggleIo(ioBtn.closest("[data-io-row]")); return; }
    const ioRow = e.target.closest(".ax-io-row.is-overflow");
    if (ioRow) { toggleIo(ioRow); return; }
    const row = e.target.closest("[data-ctx-toggle]");
    if (row) toggleCtx(row);
  });
  root.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const ioBtn = e.target.closest("[data-io-toggle]");
    const row = e.target.closest("[data-ctx-toggle]");
    if (ioBtn) { e.preventDefault(); toggleIo(ioBtn.closest("[data-io-row]")); }
    else if (row) { e.preventDefault(); toggleCtx(row); }
  });
}

// Transcript-toolbar Expand-all / Collapse-all output — view-only, non-persistent (FR-028): it
// resets to clamped on reload and a single card may still be collapsed while "all" is on.
function initExpandAll(root) {
  const btn = root.querySelector("[data-expand-all]");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const on = btn.getAttribute("aria-pressed") !== "true";
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    const label = btn.querySelector("span");
    if (label) label.textContent = on ? "Collapse all output" : "Expand all output";
    root.querySelectorAll(".ax-io-row.is-overflow").forEach((row) => setIoRow(row, on));
  });
}

// In-page transcript search over message text AND tool IN/OUT content (both are in the DOM), with
// auto-expand of a card that matches only on clamped content while the search is active (FR-029).
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
      entry.querySelectorAll(".ax-io-row.is-overflow").forEach((row) => {
        if (q && hit && !row.classList.contains("is-expanded")) {
          row.dataset.searchExpanded = "1";
          setIoRow(row, true);
        } else if (!q && row.dataset.searchExpanded) {
          delete row.dataset.searchExpanded;
          setIoRow(row, false);
        }
      });
    });
    if (count) count.textContent = q ? `${shown} matching` : "";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".ax-run-view") || document;
  initSections(root);
  initSegmented(root);
  bindToggles(root);
  initExpandAll(root);
  initSearch(root);
});
