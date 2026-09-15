// Custom dropdown — a progressive enhancement over a native <select>.
//
// enhanceSelect(select) keeps the <select> in the DOM as the value store and
// event source (visually hidden) and layers a keyboard-operable trigger plus a
// listbox panel over it. Choosing an option sets select.value and dispatches a
// bubbling `change`, so everything wired to the select keeps working untouched.
//
// Per-option enhancements read from the backing <option>:
//   data-icon="theme-dark"   → a leading <svg><use href="#theme-dark"></svg>.
//                              The referenced symbol must exist in the document.
//   data-note="EDT -4:00"    → a trailing secondary value, pinned right.
// Panel-level enhancement read from the <select>:
//   data-filter               → a sticky filter input at the top of the panel;
//   data-filter="Search…"       its value is the placeholder (default "Filter…").
//
// Accessibility follows the WAI-ARIA select-only combobox pattern. All colours
// live in app.css classes, not here.

const TYPEAHEAD_RESET_MS = 500;
const MIN_PANEL_PX = 120;
const SVG_NS = "http://www.w3.org/2000/svg";
let uid = 0;
let openDropdown = null; // at most one panel open at a time

function nextId(prefix) { uid += 1; return `${prefix}-${uid}`; }

function labelFor(select) {
  if (!select.id) return null;
  const label = document.querySelector(`label[for="${CSS.escape(select.id)}"]`);
  if (!label) return null;
  if (label.contains(select)) return label.querySelector(":scope > span");
  return label;
}

function chevron() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 12 12");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ax-dropdown-chevron");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", "M3 5l3 3 3-3");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.4");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

function iconUse(id, cls) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ax-icon");
  if (cls) svg.classList.add(cls);
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#" + id);
  svg.appendChild(use);
  return svg;
}

// Enhance one <select>. Idempotent: an already-enhanced select is re-synced.
export function enhanceSelect(select) {
  if (!select || select.tagName !== "SELECT") return null;
  if (select.axDropdown) { select.axDropdown.sync(); return select.axDropdown; }

  const hasFilter = select.hasAttribute("data-filter");
  const filterPlaceholder = select.getAttribute("data-filter") || "Filter\u2026";

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

  const panel = document.createElement("div");
  panel.className = "ax-dropdown-panel";
  panel.id = `${trigger.id}-listbox`;
  panel.hidden = true;

  // Filter row (optional) + the option list.
  let filterInput = null;
  if (hasFilter) {
    const fr = document.createElement("div");
    fr.className = "ax-dropdown-filter";
    fr.appendChild(iconUse("search"));
    filterInput = document.createElement("input");
    filterInput.type = "text";
    filterInput.placeholder = filterPlaceholder;
    filterInput.setAttribute("aria-label", filterPlaceholder);
    fr.appendChild(filterInput);
    panel.appendChild(fr);
  }
  const list = document.createElement("ul");
  list.className = "ax-dropdown-list";
  list.style.cssText = "list-style:none;margin:0;padding:0";
  list.setAttribute("role", "listbox");
  list.id = `${trigger.id}-list`;
  panel.appendChild(list);
  const emptyEl = document.createElement("div");
  emptyEl.className = "ax-dropdown-empty";
  emptyEl.textContent = "No matches";
  emptyEl.hidden = true;
  panel.appendChild(emptyEl);

  trigger.setAttribute("aria-controls", list.id);
  const leadWrap = document.createElement("span");
  leadWrap.className = "ax-dropdown-lead";
  leadWrap.style.display = "none";
  trigger.append(leadWrap, valueEl, chevron());

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
  let active = -1;
  let taBuffer = "";
  let taLast = 0;
  let syncQueued = false;
  let query = "";
  const hidden = new Set(); // option indexes filtered out

  const options = () => Array.from(select.options);
  const usable = (o, i) => o && !o.disabled && !hidden.has(i);
  const firstUsable = () => options().findIndex((o, i) => usable(o, i));
  const lastUsable = () => { const o = options(); for (let i = o.length - 1; i >= 0; i--) if (usable(o[i], i)) return i; return -1; };

  function step(from, dir, count = 1) {
    const opts = options();
    let i = from, moved = 0, last = -1;
    while (moved < count) {
      i += dir;
      if (i < 0 || i >= opts.length) break;
      if (usable(opts[i], i)) { last = i; moved++; }
    }
    return last < 0 ? (from >= 0 && usable(opts[from], from) ? from : firstUsable()) : last;
  }

  function liFor(i) { return list.querySelector(`[data-i="${i}"]`); }

  function setActive(i, scroll) {
    const prev = list.querySelector(".is-active");
    if (prev) prev.classList.remove("is-active");
    active = i;
    const li = i >= 0 ? liFor(i) : null;
    if (li) {
      li.classList.add("is-active");
      trigger.setAttribute("aria-activedescendant", li.id);
      if (scroll) li.scrollIntoView({ block: "nearest" });
    } else {
      trigger.removeAttribute("aria-activedescendant");
    }
  }

  function applyFilter() {
    const q = query.trim().toLowerCase();
    hidden.clear();
    let shown = 0;
    options().forEach((opt, i) => {
      const li = liFor(i);
      const match = !q || opt.text.toLowerCase().includes(q);
      if (match) { shown++; if (li) li.classList.remove("is-hidden"); }
      else { hidden.add(i); if (li) li.classList.add("is-hidden"); }
    });
    emptyEl.hidden = shown > 0;
  }

  function sync() {
    syncQueued = false;
    const opts = options();
    sizer.replaceChildren(...opts.map((opt) => {
      const line = document.createElement("span");
      // Reserve room for a leading icon + trailing note so the trigger never jumps.
      line.textContent = (opt.dataset.icon ? "\u25a0 " : "") + opt.text + (opt.dataset.note ? "   " + opt.dataset.note : "");
      return line;
    }));
    list.replaceChildren();
    opts.forEach((opt, i) => {
      const li = document.createElement("li");
      li.className = "ax-dropdown-option";
      li.id = `${list.id}-opt-${i}`;
      li.dataset.i = String(i);
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", opt.selected ? "true" : "false");
      if (opt.disabled) li.setAttribute("aria-disabled", "true");
      if (opt.dataset.icon) li.appendChild(iconUse(opt.dataset.icon));
      const lab = document.createElement("span");
      lab.className = "ax-dropdown-opt-label";
      lab.textContent = opt.text;
      li.appendChild(lab);
      if (opt.dataset.note) {
        const note = document.createElement("span");
        note.className = "ax-dropdown-opt-value";
        note.textContent = opt.dataset.note;
        li.appendChild(note);
      }
      li.addEventListener("mousedown", (e) => e.preventDefault());
      li.addEventListener("click", (e) => { e.preventDefault(); choose(i); });
      li.addEventListener("mousemove", () => { if (active !== i && usable(opt, i)) setActive(i, false); });
      list.appendChild(li);
    });
    const current = opts[select.selectedIndex];
    valueEl.textContent = current ? current.text : "";
    if (current && current.dataset.icon) {
      leadWrap.replaceChildren(iconUse(current.dataset.icon));
      leadWrap.style.display = "";
    } else {
      leadWrap.replaceChildren();
      leadWrap.style.display = "none";
    }
    const invalid = select.getAttribute("aria-invalid") === "true";
    wrap.classList.toggle("is-invalid", invalid);
    if (invalid) trigger.setAttribute("aria-invalid", "true"); else trigger.removeAttribute("aria-invalid");
    trigger.disabled = select.disabled;
    wrap.classList.toggle("is-disabled", select.disabled);
    if (hasFilter) applyFilter();
    if (isOpen) {
      if (select.disabled || !opts.length) close();
      else setActive(usable(current, select.selectedIndex) ? select.selectedIndex : firstUsable(), true);
    }
  }
  function queueSync() { if (!syncQueued) { syncQueued = true; queueMicrotask(sync); } }

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

  function place() {
    if (!isOpen) return;
    panel.classList.remove("is-up");
    panel.style.maxHeight = "";
    const r = trigger.getBoundingClientRect();
    const b = bounds();
    const gap = Math.max(0, panel.getBoundingClientRect().top - r.bottom);
    const below = b.bottom - r.bottom - gap;
    const above = r.top - b.top - gap;
    const want = panel.offsetHeight;
    if (want > below && above > below) {
      panel.classList.add("is-up");
      if (want > above) panel.style.maxHeight = `${Math.max(above, MIN_PANEL_PX)}px`;
    } else if (want > below) {
      panel.style.maxHeight = `${Math.max(below, MIN_PANEL_PX)}px`;
    }
  }

  function onDocPointerDown(e) { if (!wrap.isConnected || !wrap.contains(e.target)) close(); }
  function onScroll(e) { if (e.target !== panel && e.target !== list) place(); }

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
    if (hasFilter && filterInput) { query = ""; filterInput.value = ""; applyFilter(); }
    const sel = select.selectedIndex;
    setActive(usable(select.options[sel], sel) ? sel : firstUsable(), true);
    place();
    if (hasFilter && filterInput) filterInput.focus();
    document.addEventListener("pointerdown", onDocPointerDown, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
  }

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
      if (usable(opts[i], i) && opts[i].text.trim().toLowerCase().startsWith(needle)) return i;
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
      } else if (plain && !hasFilter) {
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
      case "Home": e.preventDefault(); setActive(firstUsable(), true); break;
      case "End": e.preventDefault(); setActive(lastUsable(), true); break;
      case "Enter": e.preventDefault(); if (active >= 0) choose(active); else close(); break;
      case " ": if (!hasFilter) { e.preventDefault(); if (active >= 0) choose(active); else close(); } break;
      case "Escape": e.preventDefault(); e.stopPropagation(); close(); break;
      case "Tab": close(); break;
      default:
        if (plain && !hasFilter) { e.preventDefault(); const i = typeahead(key); if (i >= 0) setActive(i, true); }
    }
  }

  trigger.addEventListener("click", (e) => { if (e.detail === 0) return; if (isOpen) close(); else open(); });
  wrap.addEventListener("keydown", onKeyDown);
  wrap.addEventListener("focusout", (e) => { if (!wrap.contains(e.relatedTarget)) close(); });
  select.addEventListener("focus", () => trigger.focus());
  select.addEventListener("change", queueSync);
  if (filterInput) {
    filterInput.addEventListener("input", () => { query = filterInput.value; applyFilter(); setActive(firstUsable(), true); });
  }

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
