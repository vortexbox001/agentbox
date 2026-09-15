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

function init() {
  const link = document.getElementById("ax-settings-link");
  if (link) link.addEventListener("click", openSettings);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
