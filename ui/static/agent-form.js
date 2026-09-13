// Schema-driven create/edit form for an agent.
//
// Reads GET /api/schema (the single source of truth) and renders the fields that
// apply to the selected harness, in section order, each with its explanation. It
// collects the values into the POST /api/agents body, maps validation errors back
// to inline messages, mirrors the server's secret heuristic for instant feedback,
// offers an on-demand YAML preview, supports "Start from template", and guards
// against leaving with unsaved changes. Phase 5 reuses this module for editing.

import { toast, flashStatus, registerDirtyForm } from "/static/shell.js";
import { enhanceSelect, enhanceSelects } from "/static/dropdown.js";

const form = document.getElementById("ax-agent-form");
const sectionsMount = document.getElementById("ax-form-sections");
const leadMount = document.getElementById("ax-form-lead-fields");
const reloadCheckbox = document.getElementById("ax-reload-checkbox");
const templateSelect = document.getElementById("ax-template-select");
const previewBtn = document.getElementById("ax-preview-btn");

let SCHEMA = null;            // GET /api/schema payload
let currentHarness = null;    // id of the harness whose fields are shown
let values = {};              // fid -> raw value (sparse; defaults fill the gaps)
let confirmNotSecret = [];    // env keys the user confirmed are not secrets
let saved = false;            // set just before a post-save navigation
let snapshot = "";            // serialise() at load, for dirty detection
let mode = "create";          // "create" | "edit"
let stem = "";                // edit target (filename stem); "" in create mode
let unmanaged = null;         // keys the UI does not manage, carried through on edit
let nameMismatch = false;     // stored name key differs from the filename
let prompts = [];             // GET /api/prompts rows: {filename, size, modified}
let creatingPrompt = false;   // "Create new prompt…" is selected in the prompt field
const newPrompt = { filename: "", content: "" };   // the inline prompt being authored
let rebuildPromptOptions = null;  // repopulate the current prompt select after a refresh
let userChangedNetwork = false;   // the user touched the network control on this page
let assetCardOn = false;          // "make agent an asset" checkbox state (spec 006)
const modelMemory = {};           // harness id -> the model chosen while on that harness
const effortMemory = {};          // harness id -> the effort chosen while on that harness

// Sections the form renders as the two nature cards (Asset / Job), not generic cards.
const CARD_SECTIONS = new Set(["produces", "triggers", "run_as_job"]);

// Full claude model id, optional [1m] context suffix (mirrors schema._CLAUDE_ID_RE).
const CLAUDE_ID_RE = /^claude-[a-z0-9.-]+(\[1m\])?$/;

// Tool-name suggestions for the list editors (help text names the same sets).
const LIST_SUGGESTIONS = {
  "allowed_tools:claude-code": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch"],
  "allowed_tools:pi": ["read", "write", "edit", "bash", "grep", "find", "ls"],
  "disallowed_tools:claude-code": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch"],
};

// ── Client mirror of secret_scan.py (instant feedback; server is authoritative) ──
const PASSTHROUGH_RE = /^\$\{\w+\}$/;
const SECRET_NAME_RE = /(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_KEY|CREDENTIAL|AUTH)/i;
const VALUE_PREFIXES = ["sk-ant-", "sk-", "ghp_", "github_pat_", "gho_", "xoxa-", "xoxb-", "xoxp-", "AKIA", "AIza", "-----BEGIN"];

function isPassthrough(v) { return typeof v === "string" && PASSTHROUGH_RE.test(v); }

function highEntropy(v) {
  if (v.length < 20 || /\s/.test(v)) return false;
  let classes = 0;
  if (/[a-z]/.test(v)) classes++;
  if (/[A-Z]/.test(v)) classes++;
  if (/[0-9]/.test(v)) classes++;
  if (/[^a-zA-Z0-9\s]/.test(v)) classes++;
  return classes >= 3;
}

function isSecretLike(name, value) {
  if (isPassthrough(value)) return false;
  if (SECRET_NAME_RE.test(String(name))) return true;
  if (typeof value !== "string") return false;
  if (VALUE_PREFIXES.some((p) => value.startsWith(p))) return true;
  return highEntropy(value);
}

// ── Schema helpers ──────────────────────────────────────
const fieldById = (id) => SCHEMA.fields.find((f) => f.id === id);
const harnessById = (id) => SCHEMA.harnesses.find((h) => h.id === id);

function defaultFor(fid) {
  if (fid === "harness") return currentHarness;
  if (fid === "network") return harnessById(currentHarness).default_network;
  const f = fieldById(fid);
  return f && f.default !== undefined ? f.default : null;
}

function getValue(fid) {
  return fid in values ? values[fid] : defaultFor(fid);
}

function isEmptyValue(f, v) {
  if (v === null || v === undefined) return true;
  if (f.type === "list" || f.type === "checks") return !Array.isArray(v) || v.length === 0;
  if (f.type === "map") return !v || Object.keys(v).length === 0;
  if (typeof v === "string" && v === "") return true;
  return false;
}

// The three networks a check may opt into (mirrors schema.CHECK_NETWORKS); blank ⇒ no network.
const CHECK_NETWORKS = ["agentnet-isolated", "agentnet", "bridge"];

function coerce(f, v) {
  if (f.type === "int") { const n = parseInt(v, 10); return Number.isNaN(n) ? v : n; }
  if (f.type === "number") { const n = parseFloat(v); return Number.isNaN(n) ? v : n; }
  return v;
}

// The ordered field ids that apply to a harness (schema is the source of order).
function harnessFieldIds(harness) {
  return harnessById(harness).fields;
}

// ── Collect the form into a POST body agent ─────────────
function collect() {
  const agent = { harness: currentHarness };
  const ids = new Set(harnessFieldIds(currentHarness));
  for (const f of SCHEMA.fields) {
    if (!ids.has(f.id) || f.id === "harness") continue;
    let v = getValue(f.id);
    if (f.type === "bool") { agent[f.id] = !!v; continue; }
    if (isEmptyValue(f, v)) continue;   // omit unset optionals; server treats as unset
    agent[f.id] = coerce(f, v);
  }
  // Nature gating (spec 006): when the Asset card is off, no produces block or asset schedule
  // is written; when the Job is off, no job schedule. The `job` bool is always sent (it is the
  // Job card's own state); the Asset card sends `asset` (possibly empty) so the server can flag
  // an empty declaration.
  if (assetCardOn) {
    if (!("asset" in agent)) agent.asset = "";
  } else {
    delete agent.asset;
    delete agent.partition;
    delete agent.asset_schedule;
    delete agent.checks;   // checks are children of the asset; drop them with the produces block
  }
  if (agent.job !== true) delete agent.job_schedule;
  // Carry the file's unmanaged keys through edit saves and the preview untouched.
  if (mode === "edit" && unmanaged && Object.keys(unmanaged).length) {
    agent.unmanaged = unmanaged;
  }
  return agent;
}

function serialise() { return JSON.stringify(collect()); }
function isDirty() { return !saved && serialise() !== snapshot; }

// ── Field rendering ─────────────────────────────────────
function labelText(f) { return f.required ? `${f.label} *` : f.label; }

// Fields whose control is intrinsically wide span the whole ax-grid-form row
// (spec 002 US3): the env map, the tool lists, the append-system-prompt text,
// and the prompt picker (its "Create new prompt…" panel needs the width).
const WIDE_FIELD_IDS = new Set(["append_system_prompt", "prompt_file"]);
function isWideField(f) {
  return f.type === "list" || f.type === "map" || WIDE_FIELD_IDS.has(f.id);
}

function setControlValue(fid, v) { values[fid] = v; }

function makeField(f) {
  const wrap = document.createElement("div");
  wrap.className = isWideField(f) ? "ax-field ax-field--wide" : "ax-field";
  wrap.dataset.field = f.id;

  const controlId = `f-${f.id}`;
  let control;

  if (f.id === "harness") {
    control = renderHarnessSelect(controlId);
  } else if (f.id === "model") {
    control = renderModel(controlId, f);
  } else if (f.id === "effort") {
    control = renderEnumSelect(controlId, f, harnessById(currentHarness).effort_choices, true);
  } else if (f.choice_source === "prompts") {
    control = renderPromptField(controlId, f);
  } else if (f.type === "enum") {
    control = renderEnumSelect(controlId, f, f.choices || [], !f.required);
  } else if (f.type === "bool") {
    return renderToggleField(f, controlId);   // toggle owns its own label layout
  } else if (f.type === "int" || f.type === "number") {
    control = renderNumber(controlId, f);
  } else if (f.type === "list") {
    control = renderList(controlId, f);
  } else if (f.type === "map") {
    control = renderMap(controlId, f);
  } else {
    control = renderText(controlId, f);       // string, path, cron
  }

  const label = document.createElement("label");
  label.setAttribute("for", controlId);
  label.textContent = labelText(f);
  wrap.append(label, control);

  if (f.id === "harness") {
    const meta = document.createElement("p");
    meta.className = "ax-harness-meta";
    meta.id = "ax-harness-meta";
    wrap.appendChild(meta);
  }

  const help = document.createElement("span");
  help.className = "ax-help";
  help.textContent = f.help;
  wrap.appendChild(help);

  if (f.id === "model") {
    const note = document.createElement("span");
    note.className = "ax-help ax-model-note";
    note.textContent = modelNote(currentHarness);
    wrap.appendChild(note);
  }

  const err = document.createElement("span");
  err.className = "ax-field-error";
  err.hidden = true;
  wrap.appendChild(err);

  return wrap;
}

// ── Network mismatch warning (FR-024; non-blocking) ─────
// Mirrors schema.network_mismatch_warning so the operator sees it before saving;
// the server returns the authoritative warning in the save response too.
function networkMismatchMessage(harness, network) {
  if (!harness || !network) return null;
  if ((harness === "claude-code" || harness === "codex") && network !== "bridge") {
    return `${harness} needs network: bridge to reach its provider; ${network} has no internet access`;
  }
  if (harness === "api" && network === "bridge") {
    return "api only needs LiteLLM; bridge grants unnecessary internet access";
  }
  return null;
}

function updateNetworkWarning() {
  const wrap = sectionsMount.querySelector('[data-field="network"]');
  if (!wrap) return;
  let warn = wrap.querySelector(".ax-network-warn");
  const msg = networkMismatchMessage(currentHarness, getValue("network"));
  if (!msg) { if (warn) warn.hidden = true; return; }
  if (!warn) {
    warn = document.createElement("span");
    warn.className = "ax-secret-warn ax-network-warn";
    wrap.appendChild(warn);
  }
  warn.textContent = msg;
  warn.hidden = false;
}

function renderHarnessSelect(id) {
  const sel = document.createElement("select");
  sel.className = "ax-select";
  sel.id = id;
  for (const h of SCHEMA.harnesses) {
    const opt = document.createElement("option");
    opt.value = h.id;
    opt.textContent = h.label;
    if (h.id === currentHarness) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => switchHarness(sel.value));
  return sel;
}

function updateHarnessMeta() {
  const meta = document.getElementById("ax-harness-meta");
  if (!meta) return;
  const h = harnessById(currentHarness);
  meta.textContent = `${h.description} · image ${h.image}`;
}

function renderEnumSelect(id, f, choices, allowBlank) {
  const sel = document.createElement("select");
  sel.className = "ax-select";
  sel.id = id;
  if (allowBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = f.id === "prompt_file" ? "Select a prompt…" : "—";
    sel.appendChild(blank);
  }
  const cur = getValue(f.id);
  for (const c of choices) {
    const opt = document.createElement("option");
    opt.value = String(c);
    opt.textContent = String(c);
    if (String(c) === String(cur)) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => {
    const v = sel.value;
    setControlValue(f.id, f.type === "bool" ? v === "true" : v === "" ? null : v);
    if (f.id === "network") { userChangedNetwork = true; updateNetworkWarning(); }
  });
  return sel;
}

// ── Prompt selector (US4) ───────────────────────────────
const NEW_PROMPT_SENTINEL = "__ax_new_prompt__";

function promptRows() {
  // Prefer the rich GET /api/prompts rows; fall back to the schema's filename list
  // (no size/modified) if that fetch has not landed or failed.
  if (prompts && prompts.length) return prompts;
  return (SCHEMA.prompts || []).map((fn) => ({ filename: fn, size: null, modified: null }));
}

function formatBytes(n) {
  if (n == null) return null;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function promptOptionLabel(p) {
  const bits = [];
  const size = formatBytes(p.size);
  if (size) bits.push(size);
  if (p.modified) bits.push(String(p.modified).slice(0, 10));
  return bits.length ? `${p.filename} — ${bits.join(" · ")}` : p.filename;
}

function normalisePromptName(fn) {
  const t = String(fn || "").trim();
  if (!t) return "";
  return t.endsWith(".md") ? t : `${t}.md`;
}

// A select over every prompt file (filename plus size/modified) with a trailing
// "Create new prompt…" option that reveals filename + content inputs. The chosen
// value flows into agent.prompt_file; an authored prompt rides along as new_prompt.
function renderPromptField(id, f) {
  const box = document.createElement("div");
  box.className = "ax-prompt-field";

  const sel = document.createElement("select");
  sel.className = "ax-select";
  sel.id = id;

  const panel = document.createElement("div");
  panel.className = "ax-new-prompt";
  panel.hidden = true;

  const fnLabel = document.createElement("label");
  fnLabel.className = "ax-new-prompt-label";
  fnLabel.textContent = "New prompt filename";
  const fnInput = document.createElement("input");
  fnInput.type = "text";
  fnInput.className = "ax-input";
  fnInput.placeholder = "my-agent.md";
  fnInput.value = newPrompt.filename || "";

  const bodyLabel = document.createElement("label");
  bodyLabel.className = "ax-new-prompt-label";
  bodyLabel.textContent = "Prompt content";
  const bodyArea = document.createElement("textarea");
  bodyArea.className = "ax-textarea";
  bodyArea.rows = 8;
  bodyArea.placeholder = "What the agent should do…";
  bodyArea.value = newPrompt.content || "";

  panel.append(fnLabel, fnInput, bodyLabel, bodyArea);

  const populate = () => {
    sel.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Select a prompt…";
    sel.appendChild(blank);
    for (const p of promptRows()) {
      const opt = document.createElement("option");
      opt.value = p.filename;
      opt.textContent = promptOptionLabel(p);
      sel.appendChild(opt);
    }
    const newOpt = document.createElement("option");
    newOpt.value = NEW_PROMPT_SENTINEL;
    newOpt.textContent = "Create new prompt…";
    sel.appendChild(newOpt);

    if (creatingPrompt) {
      sel.value = NEW_PROMPT_SENTINEL;
      panel.hidden = false;
    } else {
      const cur = getValue(f.id);
      sel.value = cur == null ? "" : String(cur);
      panel.hidden = true;
    }
  };
  rebuildPromptOptions = populate;   // one prompt field at a time; refresh rebuilds it
  populate();

  sel.addEventListener("change", () => {
    if (sel.value === NEW_PROMPT_SENTINEL) {
      creatingPrompt = true;
      panel.hidden = false;
      setControlValue(f.id, normalisePromptName(fnInput.value) || null);
    } else {
      creatingPrompt = false;
      panel.hidden = true;
      setControlValue(f.id, sel.value === "" ? null : sel.value);
    }
  });

  fnInput.addEventListener("input", () => {
    newPrompt.filename = fnInput.value;
    if (creatingPrompt) setControlValue(f.id, normalisePromptName(fnInput.value) || null);
  });
  bodyArea.addEventListener("input", () => { newPrompt.content = bodyArea.value; });

  box.append(sel, panel);
  return box;
}

// Re-read GET /api/prompts and rebuild the selector in place (no page reload). When
// a filename is given, adopt it as the selection and leave create-new mode.
async function refreshPrompts(selectFilename) {
  try {
    const data = await (await fetch("/api/prompts")).json();
    if (Array.isArray(data.prompts)) prompts = data.prompts;
  } catch (e) { /* keep the prompts already listed */ }
  if (selectFilename) {
    creatingPrompt = false;
    newPrompt.filename = "";
    newPrompt.content = "";
    setControlValue("prompt_file", selectFilename);
  }
  if (rebuildPromptOptions) rebuildPromptOptions();
}

// The model control varies by harness (research R4):
//   claude-code → alias select + "Custom model id…" revealing a claude-…[1m]? text input
//   pi          → LiteLLM alias select + "provider/model…" revealing a text input
//   api         → strict alias select, no custom entry
//   codex       → suggestion select + "Custom model id…" revealing a free text input
function renderModel(id, f) {
  const h = harnessById(currentHarness);
  const rule = h.model_rule || {};
  const custom = rule.custom || "none";
  if (custom === "none") return renderEnumSelect(id, f, rule.choices || [], !!rule.blank_ok);
  // custom === "any" (codex): the suggestions are the choices; the custom entry takes any id.
  if (custom === "any") return renderModelSelectWithCustom(id, f, { ...rule, choices: h.model_suggestions || [] });
  return renderModelSelectWithCustom(id, f, rule);
}

// Alias select with a trailing custom option that reveals a validated text input.
function renderModelSelectWithCustom(id, f, rule) {
  const CUSTOM = "__ax_custom_model__";
  const choices = rule.choices || [];
  const providerModel = rule.custom === "provider-model";
  const anyModel = rule.custom === "any";
  const box = document.createElement("div");

  const sel = document.createElement("select");
  sel.className = "ax-select";
  sel.id = id;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "ax-input ax-model-custom";
  input.hidden = true;
  input.placeholder = anyModel ? "model id"
    : providerModel ? "provider/model" : "claude-… (append [1m] for 1M context)";

  if (rule.blank_ok) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "— (harness default)";
    sel.appendChild(blank);
  }
  for (const c of choices) {
    const o = document.createElement("option");
    o.value = String(c);
    o.textContent = String(c);
    sel.appendChild(o);
  }
  const customOpt = document.createElement("option");
  customOpt.value = CUSTOM;
  customOpt.textContent = providerModel ? "provider/model…" : "Custom model id…";
  sel.appendChild(customOpt);

  const cur = getValue(f.id);
  const isCustom = cur != null && cur !== "" && !choices.includes(String(cur));
  if (isCustom) { sel.value = CUSTOM; input.value = String(cur); input.hidden = false; }
  else { sel.value = cur == null ? "" : String(cur); input.hidden = true; }

  const validateCustom = () => {
    if (input.hidden) { setFieldError(f.id, null); return; }
    const v = input.value.trim();
    if (!v || anyModel) { setFieldError(f.id, null); return; }   // codex: any id is fine
    if (!providerModel && !CLAUDE_ID_RE.test(v)) {
      setFieldError(f.id, "must be a claude-… id, optionally with [1m]");
    } else if (providerModel && !v.includes("/")) {
      setFieldError(f.id, "a custom model must be provider/model");
    } else {
      setFieldError(f.id, null);
    }
  };

  sel.addEventListener("change", () => {
    if (sel.value === CUSTOM) {
      input.hidden = false;
      setControlValue(f.id, input.value.trim() || null);
      input.focus();
      validateCustom();
    } else {
      input.hidden = true;
      setControlValue(f.id, sel.value === "" ? null : sel.value);
      setFieldError(f.id, null);
    }
  });
  input.addEventListener("input", () => {
    setControlValue(f.id, input.value.trim() || null);
    validateCustom();
  });

  box.append(sel, input);
  return box;
}

// A one-line note under the model control explaining which forms the harness
// accepts, so the absent forms read as intentional rather than missing.
function modelNote(harness) {
  switch (harness) {
    case "claude-code":
      return "Pick an alias, or “Custom model id…” for a full claude-… id (append [1m] for 1M context). Blank uses the CLI default.";
    case "pi":
      return "Pick a LiteLLM alias, or “provider/model…” to target a model directly. Claude aliases and full ids do not apply to pi.";
    case "api":
      return "Only LiteLLM aliases are accepted; the API runner has no custom model id or provider/model form.";
    case "codex":
      return "Pick a suggested id, or “Custom model id…” for any Codex model id. LiteLLM aliases and claude-… ids do not apply to codex.";
    default:
      return "";
  }
}

function renderNumber(id, f) {
  const input = document.createElement("input");
  input.type = "number";
  input.className = "ax-input";
  input.id = id;
  if (f.min !== undefined) input.min = f.min;
  if (f.max !== undefined) input.max = f.max;
  input.step = f.type === "int" ? "1" : "any";
  const v = getValue(f.id);
  input.value = v === null || v === undefined ? "" : v;
  input.addEventListener("input", () => {
    setControlValue(f.id, input.value === "" ? null : (f.type === "int" ? parseInt(input.value, 10) : parseFloat(input.value)));
  });
  return input;
}

function renderText(id, f) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "ax-input";
  input.id = id;
  if (f.pattern) input.pattern = f.pattern;
  if (f.id === "name") input.placeholder = "my-agent";
  if (f.id === "output_dir") input.placeholder = "/data/outputs/<name>";
  if (f.type === "cron") input.placeholder = "e.g. 0 7 * * * (blank = manual only)";
  input.value = getValue(f.id) || "";
  input.addEventListener("input", () => {
    setControlValue(f.id, input.value);
    if (f.type === "cron") checkCronShape(f.id, input.value);
  });
  return input;
}

// Client-side shape check only; the server validates with croniter.
function checkCronShape(fid, value) {
  const s = String(value).trim();
  if (!s) { setFieldError(fid, null); return; }
  if (s.startsWith("@")) { setFieldError(fid, "cron macros like @daily are not supported; use a 5-field expression"); return; }
  if (s.split(/\s+/).length !== 5) { setFieldError(fid, "cron must have exactly five fields (minute hour day month weekday)"); return; }
  setFieldError(fid, null);
}

function renderToggleField(f, id) {
  const wrap = document.createElement("div");
  wrap.className = "ax-field";
  wrap.dataset.field = f.id;
  const label = document.createElement("label");
  label.className = "ax-toggle";
  label.setAttribute("for", id);
  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = id;
  input.checked = !!getValue(f.id);
  const track = document.createElement("span");
  track.className = "ax-toggle-track";
  track.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.textContent = labelText(f);
  input.addEventListener("change", () => setControlValue(f.id, input.checked));
  label.append(input, track, text);
  const help = document.createElement("span");
  help.className = "ax-help";
  help.textContent = f.help;
  const err = document.createElement("span");
  err.className = "ax-field-error";
  err.hidden = true;
  wrap.append(label, help, err);
  return wrap;
}

// ── Chip (list) editor ──────────────────────────────────
function renderList(id, f) {
  const box = document.createElement("div");
  box.className = "ax-chips";
  box.id = id;
  const arr = Array.isArray(getValue(f.id)) ? getValue(f.id).slice() : [];

  const render = () => {
    box.replaceChildren();
    arr.forEach((item, i) => {
      const chip = document.createElement("span");
      chip.className = "ax-chip";
      const t = document.createElement("span");
      t.textContent = item;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "ax-chip-remove";
      rm.setAttribute("aria-label", `Remove ${item}`);
      rm.textContent = "×";
      rm.addEventListener("click", () => { arr.splice(i, 1); setControlValue(f.id, arr.slice()); render(); });
      chip.append(t, rm);
      box.appendChild(chip);
    });
    box.appendChild(input);
    input.focus({ preventScroll: true });
  };

  const input = document.createElement("input");
  input.type = "text";
  input.className = "ax-chip-input";
  input.placeholder = arr.length ? "" : "type a value, Enter to add";
  const sugg = LIST_SUGGESTIONS[`${f.id}:${currentHarness}`];
  if (sugg) {
    const listId = `${id}-list`;
    const dl = document.createElement("datalist");
    dl.id = listId;
    for (const s of sugg) { const o = document.createElement("option"); o.value = s; dl.appendChild(o); }
    input.setAttribute("list", listId);
    box.appendChild(dl);
  }
  const commit = () => {
    const val = input.value.trim().replace(/,$/, "").trim();
    if (val && !arr.includes(val)) { arr.push(val); setControlValue(f.id, arr.slice()); }
    input.value = "";
    render();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); commit(); }
    else if (e.key === "Backspace" && input.value === "" && arr.length) { arr.pop(); setControlValue(f.id, arr.slice()); render(); }
  });
  input.addEventListener("blur", () => { if (input.value.trim()) commit(); });

  render();
  return box;
}

// ── Key/value (map / env) editor ────────────────────────
function renderMap(id, f) {
  const box = document.createElement("div");
  box.className = "ax-kv";
  box.id = id;
  const obj = getValue(f.id);
  const rows = obj && typeof obj === "object" ? Object.entries(obj).map(([k, v]) => [k, String(v)]) : [];
  if (rows.length === 0) rows.push(["", ""]);

  const sync = () => {
    const out = {};
    for (const [k, v] of rows) { if (k.trim()) out[k.trim()] = v; }
    setControlValue(f.id, out);
  };

  const render = () => {
    box.replaceChildren();
    rows.forEach((row, i) => {
      const line = document.createElement("div");
      line.className = "ax-kv-row";
      const key = document.createElement("input");
      key.type = "text";
      key.className = "ax-input ax-kv-key";
      key.placeholder = "NAME";
      key.value = row[0];
      const val = document.createElement("input");
      val.type = "text";
      val.className = "ax-input ax-kv-val";
      val.placeholder = "value or ${HOST_VAR}";
      val.value = row[1];
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "ax-kv-remove ax-btn ax-btn--ghost";
      rm.setAttribute("aria-label", "Remove variable");
      rm.textContent = "×";
      const warn = document.createElement("span");
      warn.className = "ax-secret-warn";
      warn.hidden = true;

      const refreshWarn = () => {
        const secret = row[0].trim() && isSecretLike(row[0], row[1]);
        warn.hidden = !secret;
        if (secret) warn.textContent = "Looks like a secret. Use ${" + (row[0].trim() || "NAME") + "} to forward the host variable, or confirm on save.";
      };
      key.addEventListener("input", () => { row[0] = key.value; sync(); refreshWarn(); });
      val.addEventListener("input", () => { row[1] = val.value; sync(); refreshWarn(); });
      rm.addEventListener("click", () => { rows.splice(i, 1); if (rows.length === 0) rows.push(["", ""]); sync(); render(); });

      line.append(key, val, rm);
      box.appendChild(line);
      box.appendChild(warn);
      refreshWarn();
    });
    const add = document.createElement("button");
    add.type = "button";
    add.className = "ax-kv-add ax-btn ax-btn--ghost";
    add.textContent = "+ Add variable";
    add.addEventListener("click", () => { rows.push(["", ""]); render(); });
    box.appendChild(add);
  };

  render();
  return box;
}

// ── Checks editor (spec 008) ────────────────────────────
// A repeatable-object-rows control (modeled on renderMap) editing produces.checks: a list of
// {name, command, image?, blocking?, timeout_seconds?, network?}. It writes clean objects into
// values.checks — only fields the user actually set, blocking recorded only when unticked (default
// is true) — so a UI-authored check matches a hand-written one. Rendered inside the Asset card
// (buildAssetCard), so a job-only agent never sees it (FR-011).
function renderChecks() {
  const box = document.createElement("div");
  box.className = "ax-checks";
  const arr = Array.isArray(getValue("checks")) ? getValue("checks").map((c) => ({ ...c })) : [];

  const sync = () => {
    const out = [];
    for (const c of arr) {
      const name = (c.name || "").trim();
      const command = (c.command || "").trim();
      if (!name && !command) continue;   // drop a wholly-blank row
      const obj = {};
      if (name) obj.name = name;
      if (command) obj.command = command;
      if (c.image && String(c.image).trim()) obj.image = String(c.image).trim();
      if (c.blocking === false) obj.blocking = false;   // default true; record only a false
      if (c.timeout_seconds !== "" && c.timeout_seconds !== null && c.timeout_seconds !== undefined) {
        const n = parseInt(c.timeout_seconds, 10);
        if (!Number.isNaN(n)) obj.timeout_seconds = n;
      }
      if (c.network) obj.network = c.network;
      out.push(obj);
    }
    setControlValue("checks", out);
  };

  const render = () => {
    box.replaceChildren();
    arr.forEach((c, i) => {
      const row = document.createElement("div");
      row.className = "ax-check-row";

      const name = document.createElement("input");
      name.type = "text"; name.className = "ax-input ax-check-name";
      name.placeholder = "name (kebab)"; name.value = c.name || "";
      name.addEventListener("input", () => { c.name = name.value; sync(); });

      const cmd = document.createElement("input");
      cmd.type = "text"; cmd.className = "ax-input ax-check-command";
      cmd.placeholder = "command — run as sh -c"; cmd.value = c.command || "";
      cmd.addEventListener("input", () => { c.command = cmd.value; sync(); });

      const image = document.createElement("input");
      image.type = "text"; image.className = "ax-input ax-check-image";
      image.placeholder = "image (blank = harness image)"; image.value = c.image || "";
      image.addEventListener("input", () => { c.image = image.value; sync(); });

      const blockingLabel = document.createElement("label");
      blockingLabel.className = "ax-toggle ax-check-blocking";
      const blocking = document.createElement("input");
      blocking.type = "checkbox"; blocking.checked = c.blocking !== false;
      const track = document.createElement("span");
      track.className = "ax-toggle-track"; track.setAttribute("aria-hidden", "true");
      const btext = document.createElement("span"); btext.textContent = "blocking";
      blocking.addEventListener("change", () => { c.blocking = blocking.checked; sync(); });
      blockingLabel.append(blocking, track, btext);

      const timeout = document.createElement("input");
      timeout.type = "number"; timeout.className = "ax-input ax-check-timeout";
      timeout.min = 1; timeout.max = 86400; timeout.placeholder = "timeout s (300)";
      timeout.value = c.timeout_seconds === undefined || c.timeout_seconds === null ? "" : c.timeout_seconds;
      timeout.addEventListener("input", () => { c.timeout_seconds = timeout.value; sync(); });

      const net = document.createElement("select");
      net.className = "ax-select ax-check-network";
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "no network"; net.appendChild(blank);
      for (const n of CHECK_NETWORKS) {
        const o = document.createElement("option");
        o.value = n; o.textContent = n; if (c.network === n) o.selected = true;
        net.appendChild(o);
      }
      net.addEventListener("change", () => { c.network = net.value || undefined; sync(); });

      const rm = document.createElement("button");
      rm.type = "button"; rm.className = "ax-kv-remove ax-btn ax-btn--ghost";
      rm.setAttribute("aria-label", "Remove check"); rm.textContent = "×";
      rm.addEventListener("click", () => { arr.splice(i, 1); sync(); render(); });

      row.append(name, cmd, image, blockingLabel, timeout, net, rm);
      box.appendChild(row);
    });
    const add = document.createElement("button");
    add.type = "button"; add.className = "ax-kv-add ax-btn ax-btn--ghost";
    add.textContent = "+ Add check";
    add.addEventListener("click", () => { arr.push({ blocking: true }); render(); sync(); });
    box.appendChild(add);
    // enhance the per-row network <select>s (idempotent) so dynamically added rows match the
    // shared custom-dropdown path, not just the ones present at first form render.
    enhanceSelects(box);
  };

  render();
  return box;
}

// ── Nature cards (Asset / Job) ──────────────────────────
// Enable/disable every control inside a container and dim it when gated off.
function setCardEnabled(container, enabled) {
  container.classList.toggle("ax-gated-off", !enabled);
  container.querySelectorAll("input, select, textarea").forEach((el) => { el.disabled = !enabled; });
}

// A field wrap for one schema field id, only if it applies to the current harness.
function fieldWrapIfApplicable(fid) {
  const ids = new Set(harnessFieldIds(currentHarness));
  if (!ids.has(fid)) return null;
  const f = fieldById(fid);
  return f ? makeField(f) : null;
}

// The Asset card: a checkbox gating the produces fields (asset key, partition) plus the
// asset-schedule cron. Off ⇒ no produces block is written (contract ui-automation §1).
function buildAssetCard() {
  const card = document.createElement("section");
  card.className = "ax-card ax-form-section ax-nature-card";
  card.id = "ax-asset-card";
  const h = document.createElement("h2");
  h.textContent = "Asset";

  const toggle = document.createElement("label");
  toggle.className = "ax-toggle";
  toggle.setAttribute("for", "ax-asset-toggle");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "ax-asset-toggle";
  cb.checked = assetCardOn;
  const track = document.createElement("span");
  track.className = "ax-toggle-track";
  track.setAttribute("aria-hidden", "true");
  const cbText = document.createElement("span");
  cbText.textContent = "make agent an asset";
  toggle.append(cb, track, cbText);

  const grid = document.createElement("div");
  grid.className = "ax-grid-form";
  for (const fid of ["asset", "partition", "asset_schedule"]) {
    const w = fieldWrapIfApplicable(fid);
    if (w) grid.appendChild(w);
  }

  // The Checks editor (spec 008): a wide, full-row control inside the Asset card so it is present
  // only for an asset and gated off with the rest of the produces fields (FR-011).
  const checksField = fieldById("checks");
  if (checksField && harnessFieldIds(currentHarness).includes("checks")) {
    const wrap = document.createElement("div");
    wrap.className = "ax-field ax-field--wide";
    wrap.dataset.field = "checks";
    const cl = document.createElement("label");
    cl.textContent = "Checks";
    const help = document.createElement("span");
    help.className = "ax-help";
    help.textContent = checksField.help;
    const err = document.createElement("span");
    err.className = "ax-field-error";
    err.hidden = true;
    wrap.append(cl, renderChecks(), help, err);
    grid.appendChild(wrap);
  }

  card.append(h, toggle, grid);
  const gate = () => setCardEnabled(grid, assetCardOn);
  cb.addEventListener("change", () => { assetCardOn = cb.checked; gate(); updateNatureHint(); });
  gate();
  return card;
}

// The Job card: the `job` toggle ("create agent job") gating the job-schedule cron. On ⇒
// `job: true` is written; off ⇒ no job (contract ui-automation §1).
function buildJobCard() {
  const card = document.createElement("section");
  card.className = "ax-card ax-form-section ax-nature-card";
  card.id = "ax-job-card";
  const h = document.createElement("h2");
  h.textContent = "Job";

  const jobWrap = makeField(fieldById("job"));   // bool → the "create agent job" toggle
  const grid = document.createElement("div");
  grid.className = "ax-grid-form";
  const js = fieldWrapIfApplicable("job_schedule");
  if (js) grid.appendChild(js);

  card.append(h, jobWrap, grid);
  const gate = () => setCardEnabled(grid, getValue("job") === true);
  const jobInput = jobWrap.querySelector("input[type=checkbox]");
  if (jobInput) jobInput.addEventListener("change", () => { gate(); updateNatureHint(); });
  gate();
  return card;
}

// A client-side hint when the agent is neither an asset nor a job (the server is the
// authority — it rejects the save with the nature message; FR-005).
function updateNatureHint() {
  const hint = document.getElementById("ax-nature-hint");
  if (!hint) return;
  const neither = !assetCardOn && getValue("job") !== true;
  hint.hidden = !neither;
}

// ── Form assembly ───────────────────────────────────────
function renderForm(harness) {
  currentHarness = harness;
  const ids = new Set(harnessFieldIds(harness));
  if (leadMount) leadMount.replaceChildren();
  sectionsMount.replaceChildren();

  // One container per group (Runs, Job, Box), in order, each led by its heading.
  // All three always render — every harness has at least one card per group — so
  // the grid areas are always occupied (contracts/layout.md §1).
  const groupEls = new Map();
  for (const g of SCHEMA.groups) {
    const groupEl = document.createElement("section");
    groupEl.className = "ax-form-group";
    groupEl.dataset.group = g.id;
    const heading = document.createElement("h2");
    heading.className = "ax-form-section-heading";
    heading.textContent = g.label;
    groupEl.appendChild(heading);
    groupEls.set(g.id, groupEl);
  }

  for (const section of SCHEMA.sections) {
    // The produces/triggers/run_as_job sections are rendered as the Asset and Job cards below,
    // not as generic per-section cards (spec 006 US1).
    if (CARD_SECTIONS.has(section.id)) continue;
    const fields = SCHEMA.fields.filter((f) => f.section === section.id && ids.has(f.id));
    if (!fields.length) continue;
    if (section.group == null) {
      // Lead-strip section (identity): fields render straight into the lead mount,
      // not a card, so name (and the template picker) share one strip.
      if (leadMount) for (const f of fields) leadMount.appendChild(makeField(f));
      continue;
    }
    const card = document.createElement("section");
    card.className = "ax-card ax-form-section";
    const h = document.createElement("h2");
    h.textContent = section.label;
    card.appendChild(h);
    const grid = document.createElement("div");
    grid.className = "ax-grid-form";
    for (const f of fields) grid.appendChild(makeField(f));
    card.appendChild(grid);
    const groupEl = groupEls.get(section.group);
    if (groupEl) groupEl.appendChild(card);
  }

  // The two nature cards: Asset (Runs group) and Job (Job group). Each is gated by its own
  // checkbox; the server enforces the at-least-one rule, the client just hints (contract §1).
  const runsGroup = groupEls.get("runs");
  if (runsGroup && ids.has("asset")) runsGroup.appendChild(buildAssetCard());
  const jobGroup = groupEls.get("job");
  if (jobGroup && ids.has("job")) jobGroup.insertBefore(buildJobCard(), jobGroup.children[1] || null);

  for (const g of SCHEMA.groups) sectionsMount.appendChild(groupEls.get(g.id));

  // Enhance every select on the whole form — the lead strip's controls included,
  // not only the group cards (spec 002 US1). enhanceSelect is idempotent and its
  // MutationObserver re-syncs the template picker when its options load later.
  // A single at-least-one-of hint under the group cards (server remains the authority).
  let hint = document.getElementById("ax-nature-hint");
  if (!hint) {
    hint = document.createElement("p");
    hint.id = "ax-nature-hint";
    hint.className = "ax-secret-warn ax-nature-hint";
    hint.textContent = "An agent must be an asset, a job, or both — tick at least one card.";
  }
  sectionsMount.appendChild(hint);

  enhanceSelects(form);
  updateHarnessMeta();
  updateNetworkWarning();
  updateNatureHint();
}

// Whether a model string is acceptable for a harness (mirrors schema._validate_model,
// used only to decide whether to keep a value across a harness switch).
function modelValidFor(harness, model) {
  if (model == null || model === "") return true;   // blank is handled by the rule
  const rule = harnessById(harness).model_rule || {};
  if ((rule.choices || []).includes(String(model))) return true;
  if (rule.custom === "any") return true;
  if (rule.custom === "claude-id") return CLAUDE_ID_RE.test(String(model));
  if (rule.custom === "provider-model") return String(model).includes("/");
  return false;   // custom === "none": only listed aliases are valid
}

function effortValidFor(harness, effort) {
  if (effort == null || effort === "") return true;
  return (harnessById(harness).effort_choices || []).includes(String(effort));
}

// FR-007a: switching harness keeps a per-page memory of the model/effort chosen on
// each harness (fields hidden by the switch are already retained in `values`), resets
// model/effort that are invalid for the new harness, and moves network to the new
// harness default unless the user set it explicitly on this page.
function switchHarness(harness) {
  const prev = currentHarness;
  if (prev && prev !== harness) {
    modelMemory[prev] = getValue("model");
    effortMemory[prev] = getValue("effort");

    if (harness in modelMemory) values.model = modelMemory[harness];
    else if (!modelValidFor(harness, getValue("model"))) delete values.model;

    if (harness in effortMemory) values.effort = effortMemory[harness];
    else if (!effortValidFor(harness, getValue("effort"))) delete values.effort;

    if (!userChangedNetwork) values.network = harnessById(harness).default_network;
  }
  renderForm(harness);
  const trigger = document.getElementById("f-harness-trigger");
  if (trigger) trigger.focus();
}

// ── Field errors ────────────────────────────────────────
function setFieldError(fid, message) {
  // Query the whole form: the name field lives in the lead strip, not sectionsMount.
  const wrap = form.querySelector(`[data-field="${CSS.escape(fid)}"]`);
  if (!wrap) return false;
  const err = wrap.querySelector(".ax-field-error");
  const control = wrap.querySelector("input, select");
  if (message) {
    if (err) { err.textContent = message; err.hidden = false; }
    if (control) control.setAttribute("aria-invalid", "true");
  } else {
    if (err) { err.textContent = ""; err.hidden = true; }
    if (control) control.removeAttribute("aria-invalid");
  }
  return true;
}

function clearFieldErrors() {
  form.querySelectorAll(".ax-field-error").forEach((e) => { e.textContent = ""; e.hidden = true; });
  form.querySelectorAll('[aria-invalid="true"]').forEach((c) => c.removeAttribute("aria-invalid"));
}

function applyFieldErrors(fields) {
  const unmapped = [];
  for (const [fid, msg] of Object.entries(fields || {})) {
    if (!setFieldError(fid, msg)) unmapped.push(`${fid}: ${msg}`);
  }
  if (unmapped.length) toast(unmapped.join("; "), { tone: "error" });
}

// ── Modals (preview, secret confirmation) ───────────────
function openModal(build, { wide = false } = {}) {
  const root = document.getElementById("ax-modal-root");
  root.replaceChildren();
  const modal = document.createElement("div");
  modal.className = wide ? "ax-modal ax-modal--wide" : "ax-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  const close = () => { root.hidden = true; root.replaceChildren(); };
  build(modal, close);
  root.addEventListener("click", (e) => { if (e.target === root) close(); }, { once: true });
  root.appendChild(modal);
  root.hidden = false;
  return close;
}

function previewModal(text, warnings) {
  openModal((modal, close) => {
    const h = document.createElement("h2");
    h.textContent = "YAML preview";
    const pre = document.createElement("pre");
    pre.className = "ax-preview-code";
    pre.textContent = text;
    modal.append(h);
    if (warnings && warnings.length) {
      const w = document.createElement("p");
      w.className = "ax-secret-warn";
      w.textContent = warnings.join(" ");
      modal.appendChild(w);
    }
    modal.appendChild(pre);
    const actions = document.createElement("div");
    actions.className = "ax-modal-actions";
    const ok = document.createElement("button");
    ok.className = "ax-btn ax-btn--primary";
    ok.textContent = "Close";
    ok.addEventListener("click", close);
    actions.appendChild(ok);
    modal.appendChild(actions);
    ok.focus();
  }, { wide: true });
}

function errorsModal(fields) {
  openModal((modal, close) => {
    const h = document.createElement("h2");
    h.textContent = "Cannot preview yet";
    const p = document.createElement("p");
    p.textContent = "Fix these fields, then preview again:";
    const ul = document.createElement("ul");
    ul.className = "ax-error-list";
    for (const [fid, msg] of Object.entries(fields || {})) {
      const f = fieldById(fid);
      const li = document.createElement("li");
      li.textContent = `${f ? f.label : fid}: ${msg}`;
      ul.appendChild(li);
    }
    const actions = document.createElement("div");
    actions.className = "ax-modal-actions";
    const ok = document.createElement("button");
    ok.className = "ax-btn ax-btn--primary";
    ok.textContent = "Close";
    ok.addEventListener("click", close);
    actions.appendChild(ok);
    modal.append(h, p, ul, actions);
    ok.focus();
  });
}

function secretModal(flagged) {
  return new Promise((resolve) => {
    openModal((modal, close) => {
      const h = document.createElement("h2");
      h.textContent = "These values look like secrets";
      const p = document.createElement("p");
      p.textContent = "Storing a real secret in an agent file leaves it in the open. Forward it with ${NAME} instead, or confirm these are not secrets.";
      const ul = document.createElement("ul");
      ul.className = "ax-error-list";
      for (const k of flagged) { const li = document.createElement("li"); li.className = "ax-mono"; li.textContent = k; ul.appendChild(li); }
      const actions = document.createElement("div");
      actions.className = "ax-modal-actions";
      const cancel = document.createElement("button");
      cancel.className = "ax-btn ax-btn--ghost";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => { close(); resolve(false); });
      const ok = document.createElement("button");
      ok.className = "ax-btn ax-btn--danger";
      ok.textContent = "These are not secrets — save anyway";
      ok.addEventListener("click", () => { close(); resolve(true); });
      actions.append(cancel, ok);
      modal.append(h, p, ul, actions);
      cancel.focus();
    });
  });
}

// ── Preview ─────────────────────────────────────────────
async function doPreview() {
  clearFieldErrors();
  let resp;
  try {
    resp = await fetch("/api/agents/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent: collect() }),
    });
  } catch (e) { toast("Could not reach the agentbox server", { tone: "error" }); return; }
  const data = await resp.json().catch(() => ({}));
  if (resp.ok) { previewModal(data.yaml || "", data.warnings); return; }
  if (resp.status === 400) { applyFieldErrors(data.fields); errorsModal(data.fields); return; }
  toast(data.message || "Preview failed", { tone: "error" });
}

// ── Save ────────────────────────────────────────────────
async function submitPayload() {
  const payload = { agent: collect(), reload_dagster: !!reloadCheckbox.checked };
  if (confirmNotSecret.length) payload.confirm_not_secret = confirmNotSecret.slice();
  // An inline-authored prompt rides along; the server writes it before the agent.
  if (creatingPrompt) {
    payload.new_prompt = { filename: newPrompt.filename.trim(), content: newPrompt.content };
  }
  const url = mode === "edit" ? `/api/agents/${encodeURIComponent(stem)}` : "/api/agents";
  const method = mode === "edit" ? "PUT" : "POST";
  const okStatus = mode === "edit" ? 200 : 201;
  let resp;
  try {
    resp = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) { toast("Could not reach the agentbox server", { tone: "error" }); return; }
  const data = await resp.json().catch(() => ({}));

  if (resp.status === 404) { toast("This agent no longer exists.", { tone: "error" }); return; }
  if (resp.status === okStatus) { onSaved(data); return; }
  if (resp.status === 400) {
    const fields = { ...(data.fields || {}) };
    // A new_prompt validation error belongs to the prompt field the user is editing.
    if (fields.new_prompt) { setFieldError("prompt_file", fields.new_prompt); delete fields.new_prompt; }
    applyFieldErrors(fields);
    // A stale prompt_file (deleted on disk) → refresh the list so it can be re-picked.
    if (fields.prompt_file) refreshPrompts();
    toast("Some fields need fixing", { tone: "error" });
    return;
  }
  if (resp.status === 409 && data.error === "exists") {
    // The agent name collided. If a new prompt was written first, adopt it and
    // refresh the selector so the just-created file is not silently orphaned.
    if (creatingPrompt && newPrompt.filename.trim()) {
      await refreshPrompts(normalisePromptName(newPrompt.filename));
    }
    setFieldError("name", data.message || "an agent with this name already exists");
    toast(data.message || "Name already exists", { tone: "error" });
    return;
  }
  if (resp.status === 409 && data.error === "secret_confirmation_required") {
    const confirmed = await secretModal(data.flagged || []);
    if (confirmed) { confirmNotSecret = Array.from(new Set(confirmNotSecret.concat(data.flagged || []))); await submitPayload(); }
    return;
  }
  if (resp.status === 409 && data.error === "prompt_exists") {
    setFieldError("prompt_file", data.message || "that prompt already exists");
    await refreshPrompts();
    toast(data.message || "That prompt already exists", { tone: "error" });
    return;
  }
  if (resp.status === 507) { toast(data.message || "Storage error", { tone: "error" }); return; }
  toast(data.message || `Save failed (${resp.status})`, { tone: "error" });
}

function onSaved(data) {
  saved = true;   // stop the dirty guard before we navigate
  const name = (data.file || "").replace(/\.yaml$/, "");
  const parts = [`Agent “${name}” saved.`];
  if (data.warnings && data.warnings.length) parts.push(data.warnings.join(" "));
  const reload = data.reload || {};
  let status;
  if (reload.requested && reload.ok) {
    parts.push("Dagster workspace reloaded.");
    status = { message: parts.join(" "), ok: true };
  } else if (reload.requested && !reload.ok) {
    parts.push(`Dagster reload failed: ${reload.message}`);
    status = { message: parts.join(" "), ok: false, retry: true };
  } else {
    status = { message: parts.join(" "), ok: true };
  }
  flashStatus(status);
  window.location.href = `/agents/${name}`;
}

// ── Delete ──────────────────────────────────────────────
// A confirmation modal that names the agent, states only agents/<stem>.yaml is
// removed (workspace and outputs remain), and carries its own "Reload Dagster"
// checkbox. Resolves to { reload } on confirm, or null on cancel.
function deleteModal(stem) {
  return new Promise((resolve) => {
    openModal((modal, close) => {
      const h = document.createElement("h2");
      h.textContent = `Delete agent “${stem}”?`;
      const p = document.createElement("p");
      p.textContent =
        `Only agents/${stem}.yaml is removed. This agent's workspace and output ` +
        `directories are left untouched.`;

      const label = document.createElement("label");
      label.className = "ax-toggle";
      label.setAttribute("for", "ax-delete-reload");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.id = "ax-delete-reload";
      cb.checked = true;
      const track = document.createElement("span");
      track.className = "ax-toggle-track";
      track.setAttribute("aria-hidden", "true");
      const txt = document.createElement("span");
      txt.textContent = "Reload Dagster after deleting";
      label.append(cb, track, txt);

      const actions = document.createElement("div");
      actions.className = "ax-modal-actions";
      const cancel = document.createElement("button");
      cancel.className = "ax-btn ax-btn--ghost";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => { close(); resolve(null); });
      const ok = document.createElement("button");
      ok.className = "ax-btn ax-btn--danger";
      ok.textContent = "Delete agent";
      ok.addEventListener("click", () => { close(); resolve({ reload: cb.checked }); });
      actions.append(cancel, ok);

      modal.append(h, p, label, actions);
      cancel.focus();
    });
  });
}

async function doDelete(stem, reloadWanted) {
  let resp;
  try {
    resp = await fetch(`/api/agents/${encodeURIComponent(stem)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reload_dagster: !!reloadWanted }),
    });
  } catch (e) {
    toast("Could not reach the agentbox server", { tone: "error" });
    return;
  }

  saved = true;   // whatever the outcome, we navigate away: stop the dirty guard

  if (resp.status === 404) {
    flashStatus({ message: `Agent “${stem}” no longer exists.`, ok: false });
    window.location.href = "/agents";
    return;
  }

  let data = {};
  try { data = await resp.json(); } catch (e) { /* leave empty */ }

  if (!resp.ok) {
    saved = false;   // no navigation; keep the guard as it was
    toast((data && data.message) || "Delete failed.", { tone: "error" });
    return;
  }

  const name = (data.deleted || `${stem}.yaml`).replace(/\.yaml$/, "");
  const reload = data.reload || {};
  const parts = [`Agent “${name}” deleted.`];
  let status;
  if (reload.requested && reload.ok) {
    parts.push("Dagster workspace reloaded.");
    status = { message: parts.join(" "), ok: true };
  } else if (reload.requested && !reload.ok) {
    parts.push(`Dagster reload failed: ${reload.message}`);
    status = { message: parts.join(" "), ok: false, retry: true };
  } else {
    status = { message: parts.join(" "), ok: true };
  }
  flashStatus(status);
  window.location.href = "/agents";
}

// Wire the Delete action. Runs even for an uneditable file (no form), so the
// button's own data-stem is the source of truth for which agent to remove.
function wireDelete() {
  const btn = document.getElementById("ax-delete-btn");
  if (!btn) return;
  const target = (btn.dataset.stem || (form && form.dataset.stem) || "").trim();
  btn.addEventListener("click", async () => {
    if (!target) return;
    const choice = await deleteModal(target);
    if (!choice) return;
    btn.disabled = true;
    await doDelete(target, choice.reload);
    btn.disabled = false;
  });
}

// ── Start from template ─────────────────────────────────
async function prefillFromTemplate(stem) {
  let resp;
  try { resp = await fetch(`/api/agents/${encodeURIComponent(stem)}`); }
  catch (e) { toast("Could not load the template", { tone: "error" }); return; }
  if (!resp.ok) { toast("Could not load the template", { tone: "error" }); return; }
  const data = await resp.json();
  const src = data.agent || {};
  values = {};
  for (const [k, v] of Object.entries(src)) { if (k !== "unmanaged") values[k] = v; }
  values.name = "";          // a template pre-fill is a starting point, not a copy
  values.enabled = false;    // start disabled until the operator reviews it
  assetCardOn = !!(values.asset && String(values.asset).trim());
  const harness = src.harness && harnessById(src.harness) ? src.harness : currentHarness;
  renderForm(harness);       // marks the form dirty vs. the blank snapshot
}

// ── Edit mode ───────────────────────────────────────────
// Lock the name field: the filename is the agent's identity and cannot change.
function lockName() {
  // name renders in the lead strip (group-less identity section), so search the form.
  const wrap = form.querySelector('[data-field="name"]');
  if (!wrap) return;
  const input = wrap.querySelector("input");
  if (input) {
    input.readOnly = true;
    input.setAttribute("aria-readonly", "true");
    input.classList.add("ax-input--readonly");
  }
  const help = wrap.querySelector(".ax-help");
  if (help) help.textContent = "The filename is the agent's identity. To rename, delete this agent and create a new one.";
  if (nameMismatch) {
    const warn = document.createElement("span");
    warn.className = "ax-secret-warn";
    warn.textContent = `The file's name key differs from its filename “${stem}”. Saving will set the name to “${stem}”.`;
    wrap.appendChild(warn);
  }
}

// Load the agent being edited and pre-fill every applicable field.
async function loadForEdit() {
  let resp;
  try { resp = await fetch(`/api/agents/${encodeURIComponent(stem)}`); }
  catch (e) { toast("Could not load this agent", { tone: "error" }); return; }
  if (!resp.ok) { toast("Could not load this agent", { tone: "error" }); return; }
  const data = await resp.json();
  nameMismatch = !!data.name_mismatch;
  const src = data.agent;
  if (!src) {
    // Unparsable file: keep the schema defaults already rendered (the server
    // shows the error banner and the raw contents alongside the form).
    lockName();
    snapshot = serialise();
    return;
  }
  values = {};
  unmanaged = null;
  for (const [k, v] of Object.entries(src)) {
    if (k === "unmanaged") { unmanaged = v; continue; }
    values[k] = v;
  }
  assetCardOn = !!(values.asset && String(values.asset).trim());
  const harness = src.harness && harnessById(src.harness) ? src.harness : currentHarness;
  renderForm(harness);
  lockName();
  snapshot = serialise();   // a freshly loaded edit form starts clean
}

// ── Boot ────────────────────────────────────────────────
async function populateTemplates() {
  if (!templateSelect) return;
  try {
    const data = await (await fetch("/api/agents")).json();
    for (const t of data.templates || []) {
      const stem = t.file.replace(/\.yaml$/, "");
      const opt = document.createElement("option");
      opt.value = stem;
      opt.textContent = `${stem}${t.harness ? ` (${t.harness})` : ""}`;
      templateSelect.appendChild(opt);
    }
  } catch (e) { /* no templates offered if the list cannot be read */ }
  enhanceSelect(templateSelect);
  templateSelect.addEventListener("change", () => {
    if (templateSelect.value) prefillFromTemplate(templateSelect.value);
  });
}

async function boot() {
  wireDelete();        // the Delete action works with or without an editable form
  if (!form) return;   // uneditable file: the page renders no form to drive
  mode = form.dataset.mode || "create";
  stem = (form.dataset.stem || "").trim();

  try {
    SCHEMA = await (await fetch("/api/schema")).json();
  } catch (e) {
    sectionsMount.replaceChildren();
    const card = document.createElement("div");
    card.className = "ax-card ax-empty";
    card.textContent = "Could not load the agent schema. Reload the page to try again.";
    sectionsMount.appendChild(card);
    return;
  }

  // The rich prompt list (filename + size + modified) backs the selector; the
  // schema's filename-only list is the fallback if this fetch fails.
  try {
    const pdata = await (await fetch("/api/prompts")).json();
    if (Array.isArray(pdata.prompts)) prompts = pdata.prompts;
  } catch (e) { /* fall back to SCHEMA.prompts */ }

  const defaultHarness = SCHEMA.harnesses[0].id;
  renderForm(defaultHarness);
  snapshot = serialise();     // blank baseline: a template pre-fill counts as dirty

  if (mode === "edit") {
    await loadForEdit();
  } else {
    await populateTemplates();
    const from = (form.dataset.from || "").trim();
    if (from) {
      if (templateSelect) { templateSelect.value = from; enhanceSelect(templateSelect); }
      await prefillFromTemplate(from);
    }
  }

  previewBtn && previewBtn.addEventListener("click", doPreview);
  form.addEventListener("submit", (e) => { e.preventDefault(); submitPayload(); });
  registerDirtyForm(isDirty);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
