// User settings modal (contract shell-and-modal §D/§E, FR-005–011).
//
// Opened from the "Settings" foot link into the shared #ax-modal-root. Holds one
// Preferences section with a Theme row; the theme control is the shared custom listbox
// (dropdown.js enhancing a native <select>), so it keeps one keyboard model across the
// app (spec 002, research R5). Choosing an option applies the theme immediately —
// stamping/clearing data-theme on <html> with no reload — and persists it to
// localStorage["agentbox.theme"] ∈ {light, dark, system}; `system` follows the OS live
// (shell.js keeps that in sync). There is no Save: Done, Escape (no open panel) and a
// backdrop click all just close, returning focus to the Settings link.

import { enhanceSelect } from "./dropdown.js";

const THEME_KEY = "agentbox.theme";   // preference ∈ {light, dark, system}

function readTheme() {
  try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
}

// Stamp/clear data-theme on <html> for the chosen preference (light/dark/system),
// resolving `system` against the OS setting — the same rule as the pre-paint script.
function applyTheme(pref) {
  const root = document.documentElement;
  const dark = pref === "dark" ||
    (pref !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (dark) root.setAttribute("data-theme", "dark");
  else root.removeAttribute("data-theme");
}

function persistTheme(pref) {
  try { localStorage.setItem(THEME_KEY, pref); } catch (e) { /* not persisted */ }
}

function focusables(container) {
  return Array.from(container.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

export function openSettings() {
  const root = document.getElementById("ax-modal-root");
  const tpl = document.getElementById("ax-settings-modal");
  const opener = document.getElementById("ax-settings-link");
  if (!root || !tpl) return null;

  root.replaceChildren(tpl.content.cloneNode(true));
  const modal = root.querySelector(".ax-modal");
  const select = root.querySelector("#ax-theme-select");
  const done = root.querySelector("#ax-settings-done");

  // Reflect the persisted preference before enhancing, so the trigger shows the right
  // option + lead glyph.
  if (select) {
    select.value = readTheme();
    enhanceSelect(select);
    select.addEventListener("change", () => {
      applyTheme(select.value);
      persistTheme(select.value);
    });
  }

  const close = () => {
    root.hidden = true;
    root.replaceChildren();
    modal.removeEventListener("keydown", onKeyDown);
    if (opener && opener.isConnected) opener.focus();
  };

  // Bubble phase, on the modal — so an open dropdown panel handles Escape/Tab first
  // (dropdown.js stops propagation on Escape while open, and closes its panel on Tab).
  // A second Escape (no open panel) reaches here and closes the modal (US3 scenario 5).
  function onKeyDown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "Tab") {
      const items = focusables(modal);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  if (done) done.addEventListener("click", close);
  root.addEventListener("click", (e) => { if (e.target === root) close(); }, { once: true });
  modal.addEventListener("keydown", onKeyDown);

  root.hidden = false;
  // Move focus into the modal (the theme dropdown trigger, else Done).
  const trigger = modal.querySelector(".ax-dropdown-trigger") || done;
  if (trigger) trigger.focus();
  return close;
}

// Retention section on the /settings page (spec 012 US5). Toggles the days field with the mode,
// and saves via POST /api/settings/retention (the page also works without JS via a full submit).
function initRetention() {
  const form = document.getElementById("ax-retention-form");
  if (!form) return;
  const mode = form.querySelector("#ax-retention-mode");
  const daysField = document.getElementById("ax-retention-days-field");
  const daysInput = form.querySelector("#ax-retention-days");
  const status = document.getElementById("ax-retention-status");

  if (mode) enhanceSelect(mode);
  function syncDays() {
    if (daysField) daysField.hidden = mode.value !== "prune_after_days";
  }
  if (mode) {
    mode.addEventListener("change", syncDays);
    syncDays();
  }

  function setStatus(msg, error) {
    if (!status) return;
    status.textContent = msg;
    if (error) status.setAttribute("data-state", "error");
    else status.removeAttribute("data-state");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = { mode: mode ? mode.value : "keep_forever" };
    if (payload.mode === "prune_after_days") payload.days = Number(daysInput && daysInput.value);
    setStatus("Saving…", false);
    try {
      const resp = await fetch("/api/settings/retention", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setStatus(data.message || "Could not save", true);
        return;
      }
      setStatus("Saved.", false);
    } catch (err) {
      setStatus("Could not reach the server", true);
    }
  });
}

// Governors section on the /settings page (spec 013 US5). Two positive-integer inputs saved via
// POST /api/settings/governors, using the shared notice/status pattern (mirrors initRetention).
function initGovernors() {
  const form = document.getElementById("ax-governors-form");
  if (!form) return;
  const runs = form.querySelector("#ax-governors-runs");
  const depth = form.querySelector("#ax-governors-depth");
  const status = document.getElementById("ax-governors-status");

  function setStatus(msg, error) {
    if (!status) return;
    status.textContent = msg;
    if (error) status.setAttribute("data-state", "error");
    else status.removeAttribute("data-state");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      max_runs_per_hour: Number(runs && runs.value),
      max_chain_depth: Number(depth && depth.value),
    };
    setStatus("Saving…", false);
    try {
      const resp = await fetch("/api/settings/governors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setStatus(data.message || "Could not save", true);
        return;
      }
      setStatus("Saved.", false);
    } catch (err) {
      setStatus("Could not reach the server", true);
    }
  });
}

function init() {
  const link = document.getElementById("ax-settings-link");
  if (link) link.addEventListener("click", openSettings);
  initRetention();
  initGovernors();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
