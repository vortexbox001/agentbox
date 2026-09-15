// Agentbox app-shell behaviour, shared by every page.
// - resolves + persists the Light/Dark/System theme (theme-and-shell contract) and
//   the collapsed/expanded sidebar state, re-stamping <html> with no full reload
// - marks the active nav item
// - a toast API (transient) and a status API (persistent until the next action)
// - flashStatus(): stash a status in sessionStorage so it shows after a navigation,
//   with its Retry action intact
// - registerDirtyForm(): warn before leaving a form with unsaved changes, both for
//   in-app link clicks (a modal) and browser navigation (beforeunload)
// - a one-shot Dagster reachability fetch on page load for the sidebar block

const FLASH_KEY = "agentbox.flashStatus";
const THEME_KEY = "agentbox.theme";       // preference ∈ {light, dark, system}
const SIDEBAR_KEY = "agentbox.sidebar";   // "collapsed" | "expanded"

// ── Theme (Light / Dark / System) ───────────────────────
// The pre-paint script in base.html already stamped <html> before first paint;
// these keep it in sync when the sidebar control or the OS setting changes.
function readTheme() {
  try { return localStorage.getItem(THEME_KEY) || "system"; } catch (e) { return "system"; }
}

function resolveTheme(pref) {
  if (pref === "dark" || pref === "light") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function stampTheme(pref) {
  const root = document.documentElement;
  if (resolveTheme(pref) === "dark") root.setAttribute("data-theme", "dark");
  else root.removeAttribute("data-theme");
}

function initTheme() {
  // The theme control now lives in the settings modal (settings.js, US3); the sidebar
  // no longer carries a radiogroup (FR-003). All that stays here is following the OS
  // live while preference = system, with no reload flash (FR-009): the pre-paint script
  // stamped <html> on load; re-stamp when the OS setting flips.
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => { if (readTheme() === "system") stampTheme("system"); };
  if (mq.addEventListener) mq.addEventListener("change", onChange);
  else if (mq.addListener) mq.addListener(onChange);   // older Safari
}

// ── Sidebar collapse (persisted across navigation/reload) ──
function initSidebar() {
  const toggle = document.getElementById("ax-collapse-toggle");
  if (!toggle) return;
  const apply = (collapsed) => {
    const root = document.documentElement;
    if (collapsed) root.setAttribute("data-sidebar", "collapsed");
    else root.removeAttribute("data-sidebar");
    toggle.setAttribute("aria-pressed", collapsed ? "true" : "false");
    // Collapsed the label is hidden, so the foot link's accessible name flips to
    // "Show navigation"; expanded it reads "Hide navigation" (contract §B, FR-004).
    toggle.setAttribute("aria-label", collapsed ? "Show navigation" : "Hide navigation");
  };
  let collapsed = false;
  try { collapsed = localStorage.getItem(SIDEBAR_KEY) === "collapsed"; } catch (e) { /* default expanded */ }
  apply(collapsed);
  toggle.addEventListener("click", () => {
    collapsed = !collapsed;
    try { localStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded"); } catch (e) { /* not persisted */ }
    apply(collapsed);
  });
}

// ── Toasts (transient) ──────────────────────────────────
export function toast(message, { tone = "info", timeout = 4000 } = {}) {
  const region = document.getElementById("ax-toast-region");
  if (!region) return;
  const el = document.createElement("div");
  el.className = `ax-toast ax-toast--${tone === "error" ? "error" : tone === "ok" ? "ok" : "info"}`;
  const msg = document.createElement("span");
  msg.textContent = message;
  const close = document.createElement("button");
  close.className = "ax-toast-close";
  close.setAttribute("aria-label", "Dismiss");
  close.textContent = "×";
  const dismiss = () => el.remove();
  close.addEventListener("click", dismiss);
  el.append(msg, close);
  region.appendChild(el);
  if (timeout) setTimeout(dismiss, timeout);
  return dismiss;
}

// ── Status banner (persistent until the next action) ────
// status = { message, ok?: bool, retry?: bool }
export function showStatus(status) {
  const region = document.getElementById("ax-status-region");
  if (!region || !status) return;
  region.replaceChildren();
  const tone = status.ok === true ? "ok" : status.ok === false ? "error" : "info";
  const el = document.createElement("div");
  el.className = `ax-status ax-status--${tone}`;
  const msg = document.createElement("span");
  msg.className = "ax-status-msg";
  msg.textContent = status.message || "";
  el.appendChild(msg);
  if (status.retry) {
    const retry = document.createElement("button");
    retry.className = "ax-btn ax-btn--ghost";
    retry.textContent = "Retry";
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      const result = await reloadDagster();
      showStatus({ message: result.message, ok: result.ok, retry: !result.ok });
    });
    el.appendChild(retry);
  }
  const close = document.createElement("button");
  close.className = "ax-status-close";
  close.setAttribute("aria-label", "Dismiss");
  close.textContent = "×";
  close.addEventListener("click", () => region.replaceChildren());
  el.appendChild(close);
  region.appendChild(el);
}

export function clearStatus() {
  const region = document.getElementById("ax-status-region");
  if (region) region.replaceChildren();
}

// Stash a status to display on the *next* page load (after a save/delete navigation).
export function flashStatus(status) {
  try {
    sessionStorage.setItem(FLASH_KEY, JSON.stringify(status));
  } catch (e) {
    /* sessionStorage may be unavailable; the status is simply not carried across. */
  }
}

function consumeFlash() {
  let raw = null;
  try {
    raw = sessionStorage.getItem(FLASH_KEY);
    if (raw) sessionStorage.removeItem(FLASH_KEY);
  } catch (e) {
    return;
  }
  if (raw) {
    try { showStatus(JSON.parse(raw)); } catch (e) { /* ignore malformed */ }
  }
}

// ── Confirm modal ───────────────────────────────────────
export function confirmModal({ title, body, confirmLabel = "Confirm", danger = false } = {}) {
  return new Promise((resolve) => {
    const root = document.getElementById("ax-modal-root");
    if (!root) { resolve(window.confirm(body || title || "Are you sure?")); return; }
    root.replaceChildren();
    const modal = document.createElement("div");
    modal.className = "ax-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    const h = document.createElement("h2");
    h.textContent = title || "Please confirm";
    const p = document.createElement("p");
    p.textContent = body || "";
    const actions = document.createElement("div");
    actions.className = "ax-modal-actions";
    const cancel = document.createElement("button");
    cancel.className = "ax-btn ax-btn--ghost";
    cancel.textContent = "Cancel";
    const ok = document.createElement("button");
    ok.className = `ax-btn ${danger ? "ax-btn--danger" : "ax-btn--primary"}`;
    ok.textContent = confirmLabel;
    const finish = (value) => { root.hidden = true; root.replaceChildren(); resolve(value); };
    cancel.addEventListener("click", () => finish(false));
    ok.addEventListener("click", () => finish(true));
    root.addEventListener("click", (e) => { if (e.target === root) finish(false); }, { once: true });
    actions.append(cancel, ok);
    modal.append(h, p, actions);
    root.appendChild(modal);
    root.hidden = false;
    ok.focus();
  });
}

// ── Dirty-form guard ────────────────────────────────────
// isDirty is a function returning whether the form has unsaved changes.
export function registerDirtyForm(isDirty) {
  const beforeUnload = (e) => {
    if (isDirty()) { e.preventDefault(); e.returnValue = ""; }
  };
  window.addEventListener("beforeunload", beforeUnload);

  // Intercept in-app link clicks so the warning is an in-app modal, not only the
  // browser's generic beforeunload prompt.
  document.addEventListener("click", async (e) => {
    const link = e.target.closest && e.target.closest("a[href]");
    if (!link || !isDirty()) return;
    const url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;      // external: let beforeunload handle it
    if (link.target === "_blank") return;
    if (link.hasAttribute("data-allow-dirty")) return;
    e.preventDefault();
    const go = await confirmModal({
      title: "Discard unsaved changes?",
      body: "This form has changes that have not been saved. Leave the page and discard them?",
      confirmLabel: "Discard changes",
      danger: true,
    });
    if (go) { window.removeEventListener("beforeunload", beforeUnload); window.location.href = link.href; }
  }, true);

  return () => window.removeEventListener("beforeunload", beforeUnload);
}

// ── Dagster ─────────────────────────────────────────────
export async function reloadDagster() {
  try {
    const resp = await fetch("/api/dagster/reload", { method: "POST" });
    return await resp.json();
  } catch (e) {
    return { ok: false, message: "Could not reach the agentbox server" };
  }
}

async function refreshDagsterStatus() {
  const dot = document.getElementById("ax-dagster-dot");
  const label = document.getElementById("ax-dagster-status");
  if (!dot && !label) return;
  try {
    const resp = await fetch("/api/dagster/status");
    const data = await resp.json();
    if (dot) dot.dataset.state = data.reachable ? "ok" : "down";
    if (label) label.textContent = data.reachable ? "reachable" : "unreachable";
  } catch (e) {
    if (dot) dot.dataset.state = "down";
    if (label) label.textContent = "unreachable";
  }
}

// ── Nav active state ────────────────────────────────────
function markActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll("[data-nav]").forEach((el) => {
    const base = el.getAttribute("data-nav");
    if (path === base || path.startsWith(base + "/")) el.classList.add("is-active");
  });
}

// ── Boot ────────────────────────────────────────────────
function boot() {
  initTheme();
  initSidebar();
  markActiveNav();
  consumeFlash();
  refreshDagsterStatus();   // page load only, per R13
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

// Expose the API on window too, for inline handlers in later story pages.
window.agentbox = { toast, showStatus, clearStatus, flashStatus, confirmModal, registerDirtyForm, reloadDagster };
