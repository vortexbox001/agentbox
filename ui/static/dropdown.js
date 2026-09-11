// Custom dropdown: a progressive enhancement over a native <select>.
//
// enhanceSelect(select) keeps the <select> in the DOM as the value store and
// event source (visually hidden) and layers a keyboard-operable trigger plus a
// listbox panel over it, following the Archon "Custom Dropdown (open)" reference.
// Choosing an option sets select.value and dispatches a bubbling `change`, so
// everything already wired to the select (harness switch, template pre-fill,
// prompt-create reveal, validation, save collection) keeps working untouched.
// Contract: specs/002-design-system-compliance/contracts/components.md §1.
//
// Accessibility follows the WAI-ARIA select-only combobox pattern: the trigger is
// a button with role="combobox", aria-haspopup="listbox", aria-expanded and
// aria-activedescendant; the panel is role="listbox" of role="option" items.
// All colours live in app.css classes, not here.

const TYPEAHEAD_RESET_MS = 500;
const MIN_PANEL_PX = 96;
let uid = 0;
let openDropdown = null;   // at most one panel is open at a time

function nextId(prefix) { uid += 1; return `${prefix}-${uid}`; }

// The element that names the select: its <label for>, or for a wrapping label
// (the create form's template picker) the label's own caption span, so the
// accessible name is the caption rather than the whole field's text.
function labelFor(select) {
  if (!select.id) return null;
  const label = document.querySelector(`label[for="${CSS.escape(select.id)}"]`);
  if (!label) return null;
  if (label.contains(select)) return label.querySelector(":scope > span");
  return label;
}

function chevron() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 12 12");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ax-dropdown-chevron");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M3 5l3 3 3-3");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

// Enhance one <select>. Idempotent: an already-enhanced select is re-synced (its
// trigger label and options refreshed from the select) and its API returned.
export function enhanceSelect(select) {
  if (!select || select.tagName !== "SELECT") return null;
  if (select.axDropdown) { select.axDropdown.sync(); return select.axDropdown; }

  const wrap = document.createElement("div");
  wrap.className = "ax-dropdown";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "ax-dropdown-trigger";
  trigger.id = select.id ? `${select.id}-trigger` : nextId("ax-dropdown");
  trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");

  const valueEl = document.createElement("span");
  valueEl.className = "ax-dropdown-value";
  valueEl.id = `${trigger.id}-value`;

  const panel = document.createElement("ul");
  panel.className = "ax-dropdown-panel";
  panel.id = `${trigger.id}-listbox`;
  panel.setAttribute("role", "listbox");
  panel.tabIndex = -1;
  panel.hidden = true;

  trigger.setAttribute("aria-controls", panel.id);
  trigger.append(valueEl, chevron());

  // Invisible in-flow copy of every option label. It gives the wrapper its
  // intrinsic width — as wide as the largest value — so the trigger neither
  // stretches to the container nor jumps when the selection changes.
  const sizer = document.createElement("div");
  sizer.className = "ax-dropdown-sizer";
  sizer.setAttribute("aria-hidden", "true");

  const label = labelFor(select);
  if (label) {
    if (!label.id) label.id = `${trigger.id}-label`;
    trigger.setAttribute("aria-labelledby", `${label.id} ${valueEl.id}`);
  } else {
    trigger.setAttribute("aria-labelledby", valueEl.id);
  }

  select.parentNode.insertBefore(wrap, select);
  wrap.append(trigger, panel, sizer, select);
  select.classList.add("ax-dropdown-native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  let isOpen = false;
  let active = -1;          // keyboard-highlighted option while open
  let taBuffer = "";
  let taLast = 0;
  let syncQueued = false;

  const options = () => Array.from(select.options);
  const firstEnabled = () => options().findIndex((o) => !o.disabled);
  const lastEnabled = () => { const o = options(); for (let i = o.length - 1; i >= 0; i--) if (!o[i].disabled) return i; return -1; };

  // Move `count` enabled options from `from` in direction `dir`, clamped at the ends.
  function step(from, dir, count = 1) {
    const opts = options();
    let i = from, moved = 0, last = from;
    while (moved < count) {
      i += dir;
      if (i < 0 || i >= opts.length) break;
      if (!opts[i].disabled) { last = i; moved++; }
    }
    return last < 0 ? firstEnabled() : last;
  }

  function setActive(i, scroll) {
    const prev = panel.querySelector(".is-active");
    if (prev) prev.classList.remove("is-active");
    active = i;
    const li = i >= 0 ? panel.children[i] : null;
    if (li) {
      li.classList.add("is-active");
      trigger.setAttribute("aria-activedescendant", li.id);
      if (scroll) li.scrollIntoView({ block: "nearest" });
    } else {
      trigger.removeAttribute("aria-activedescendant");
    }
  }

  // Rebuild the panel and trigger label from the backing select. Runs on
  // enhancement, after every change, and whenever the select's options or its
  // aria-invalid/disabled attributes change (harness switch, prompt refresh,
  // validation errors), so the custom control always mirrors the select.
  function sync() {
    syncQueued = false;
    const opts = options();
    sizer.replaceChildren(...opts.map((opt) => {
      const line = document.createElement("span");
      line.textContent = opt.text;
      return line;
    }));
    panel.replaceChildren();
    opts.forEach((opt, i) => {
      const li = document.createElement("li");
      li.className = "ax-dropdown-option";
      li.id = `${panel.id}-opt-${i}`;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", opt.selected ? "true" : "false");
      if (opt.disabled) li.setAttribute("aria-disabled", "true");
      li.textContent = opt.text;
      li.addEventListener("mousedown", (e) => e.preventDefault());      // keep focus on the trigger
      li.addEventListener("click", (e) => { e.preventDefault(); choose(i); });
      li.addEventListener("mousemove", () => { if (active !== i && !opt.disabled) setActive(i, false); });
      panel.appendChild(li);
    });
    const current = opts[select.selectedIndex];
    valueEl.textContent = current ? current.text : "";
    const invalid = select.getAttribute("aria-invalid") === "true";
    wrap.classList.toggle("is-invalid", invalid);
    if (invalid) trigger.setAttribute("aria-invalid", "true"); else trigger.removeAttribute("aria-invalid");
    trigger.disabled = select.disabled;
    wrap.classList.toggle("is-disabled", select.disabled);
    if (isOpen) {
      if (select.disabled || !opts.length) close();
      else setActive(select.selectedIndex >= 0 ? select.selectedIndex : firstEnabled(), true);
    }
  }
  function queueSync() { if (!syncQueued) { syncQueued = true; queueMicrotask(sync); } }

  // The nearest scrolling ancestor (the .ax-content region) clipped to the viewport.
  function bounds() {
    let top = 0, bottom = window.innerHeight;
    for (let el = wrap.parentElement; el; el = el.parentElement) {
      const oy = getComputedStyle(el).overflowY;
      if (oy === "auto" || oy === "scroll") {
        const r = el.getBoundingClientRect();
        top = Math.max(top, r.top);
        bottom = Math.min(bottom, r.bottom);
        break;
      }
    }
    return { top, bottom };
  }

  // Open downward by default; flip upward when the panel would not fit below
  // within the scroll region and there is more room above; cap the height to
  // the available space so long lists scroll inside the panel instead of clipping.
  function place() {
    if (!isOpen) return;
    panel.classList.remove("is-up");
    panel.style.maxHeight = "";
    const r = trigger.getBoundingClientRect();
    const b = bounds();
    const gap = Math.max(0, panel.getBoundingClientRect().top - r.bottom);
    const below = b.bottom - r.bottom - gap;
    const above = r.top - b.top - gap;
    const want = panel.offsetHeight;   // already capped by the CSS max-height
    if (want > below && above > below) {
      panel.classList.add("is-up");
      if (want > above) panel.style.maxHeight = `${Math.max(above, MIN_PANEL_PX)}px`;
    } else if (want > below) {
      panel.style.maxHeight = `${Math.max(below, MIN_PANEL_PX)}px`;
    }
  }

  function onDocPointerDown(e) {
    if (!wrap.isConnected || !wrap.contains(e.target)) close();
  }
  function onScroll(e) { if (e.target !== panel) place(); }

  function open() {
    if (isOpen || trigger.disabled) return;
    sync();
    if (!select.options.length) return;
    if (openDropdown && openDropdown !== api) openDropdown.close();
    isOpen = true;
    openDropdown = api;
    panel.hidden = false;
    wrap.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
    const sel = select.selectedIndex;
    setActive(sel >= 0 && !select.options[sel].disabled ? sel : firstEnabled(), true);
    place();
    document.addEventListener("pointerdown", onDocPointerDown, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
  }

  // Close without changing the value.
  function close() {
    if (!isOpen) return;
    isOpen = false;
    if (openDropdown === api) openDropdown = null;
    panel.hidden = true;
    panel.classList.remove("is-up");
    panel.style.maxHeight = "";
    wrap.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    setActive(-1, false);
    document.removeEventListener("pointerdown", onDocPointerDown, true);
    window.removeEventListener("resize", place);
    window.removeEventListener("scroll", onScroll, true);
  }

  // Commit option `i`: close first (a change handler may re-render the form),
  // then drive the backing select exactly as a native pick would.
  function choose(i) {
    const opt = select.options[i];
    if (!opt || opt.disabled) return;
    const changed = select.selectedIndex !== i;
    close();
    if (changed) {
      select.selectedIndex = i;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    sync();
    if (trigger.isConnected) trigger.focus();
  }

  // Printable keys jump to the next option whose label starts with the typed
  // prefix; repeating one character cycles through its matches (native behaviour).
  function typeahead(key) {
    const now = Date.now();
    if (now - taLast > TYPEAHEAD_RESET_MS) taBuffer = "";
    taLast = now;
    taBuffer += key.toLowerCase();
    const opts = options();
    if (!opts.length) return -1;
    const repeated = taBuffer.length > 1 && taBuffer.split("").every((c) => c === taBuffer[0]);
    const needle = repeated ? taBuffer[0] : taBuffer;
    const from = isOpen ? active : select.selectedIndex;
    const start = (repeated || taBuffer.length === 1) ? from + 1 : from;
    for (let n = 0; n < opts.length; n++) {
      const i = (((start + n) % opts.length) + opts.length) % opts.length;
      if (!opts[i].disabled && opts[i].text.trim().toLowerCase().startsWith(needle)) return i;
    }
    return -1;
  }

  function onKeyDown(e) {
    if (trigger.disabled) return;
    const key = e.key;
    const plain = key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
    if (!isOpen) {
      if (key === "ArrowDown" || key === "ArrowUp" || key === "Enter" || key === " ") {
        e.preventDefault();
        open();
      } else if (plain) {
        const i = typeahead(key);
        if (i >= 0) { e.preventDefault(); choose(i); }
      }
      return;
    }
    switch (key) {
      case "ArrowDown": e.preventDefault(); setActive(step(active, 1), true); break;
      case "ArrowUp": e.preventDefault(); setActive(step(active, -1), true); break;
      case "PageDown": e.preventDefault(); setActive(step(active, 1, 10), true); break;
      case "PageUp": e.preventDefault(); setActive(step(active, -1, 10), true); break;
      case "Home": e.preventDefault(); setActive(firstEnabled(), true); break;
      case "End": e.preventDefault(); setActive(lastEnabled(), true); break;
      case "Enter":
      case " ": e.preventDefault(); if (active >= 0) choose(active); else close(); break;
      case "Escape": e.preventDefault(); e.stopPropagation(); close(); break;
      case "Tab": close(); break;   // focus moves on naturally, value unchanged
      default:
        if (plain) { e.preventDefault(); const i = typeahead(key); if (i >= 0) setActive(i, true); }
    }
  }

  // Pointer clicks toggle; keyboard-originated clicks (detail 0) are already
  // handled in keydown, so they are ignored to avoid a double toggle.
  trigger.addEventListener("click", (e) => { if (e.detail === 0) return; if (isOpen) close(); else open(); });
  wrap.addEventListener("keydown", onKeyDown);
  // Leaving the control (Tab, click elsewhere) closes it without changing the value.
  wrap.addEventListener("focusout", (e) => { if (!wrap.contains(e.relatedTarget)) close(); });
  panel.addEventListener("focus", () => trigger.focus());   // e.g. after a scrollbar drag
  select.addEventListener("focus", () => trigger.focus());  // <label for> still targets the select
  select.addEventListener("change", queueSync);

  // Mirror option rebuilds (prompt refresh, template list) and attribute changes
  // (aria-invalid from validation, disabled) onto the custom control.
  new MutationObserver(queueSync).observe(select, {
    childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ["aria-invalid", "disabled", "selected", "value"],
  });

  const api = { select, wrap, trigger, panel, open, close, sync, get isOpen() { return isOpen; } };
  select.axDropdown = api;
  sync();
  return api;
}

// Enhance every `select.ax-select` under `root` (idempotent per select).
export function enhanceSelects(root = document) {
  root.querySelectorAll("select.ax-select").forEach((s) => enhanceSelect(s));
}
