"""Read and write agent definition files (agents/*.yaml).

The read side parses each file, classifies parse errors, runs schema migrations,
and separates schema-managed keys from unmanaged ones. The write side regenerates
the whole file from the schema via the emitter (contracts/agent-yaml.md): a
commented, sectioned, deterministic YAML document that ``yaml.safe_load`` turns
back into exactly the mapping the orchestrator expects.
"""
from __future__ import annotations

import glob
import logging
import os
import re
import tempfile

import yaml

import config
import schema
from schema import FIELDS, FIELDS_BY_ID, SECTIONS, HARNESS_BY_ID, ALWAYS_WRITTEN, SchemaTooNew

_log = logging.getLogger("agentbox.ui.agents_store")


class StorageError(Exception):
    """A filesystem operation failed (permission, read-only mount, missing dir)."""

    def __init__(self, operation: str, path: str, os_error: OSError):
        self.operation = operation  # "read" | "write" | "delete"
        self.path = path
        self.os_error = os_error
        super().__init__(f"cannot {operation} {path}: {os_error}")


_SCHEMA_HEADER_RE = re.compile(r"^#\s*agentbox-schema:\s*(\d+)\s*$", re.MULTILINE)
_MISSING = object()


def _agents_dir() -> str:
    return config.AGENTS_DIR


def _templates_dir() -> str:
    """Product-owned examples tree the create form's starters are read from (FR-008, R7).

    Templates live under the read-only product examples tree (``config.TEMPLATES_DIR``), not
    in the instance agents dir, so they are never listed as real agents nor copied into an
    operator's config repo as fake ones.
    """
    return config.TEMPLATES_DIR


def _path(stem: str, base_dir: str | None = None) -> str:
    return os.path.join(base_dir or _agents_dir(), f"{stem}.yaml")


def _safe_stem(stem: str) -> bool:
    """Reject path traversal and separators in a filename stem (FR-010a).

    The agent stem is the sole component of ``agents/<stem>.yaml``; a stem that
    carries a separator or ``..`` could escape the mount. Every store entry point
    checks this so traversal is refused consistently, not only at one endpoint.
    """
    return bool(stem) and not ("/" in stem or "\\" in stem or ".." in stem)


def dagster_job_path(job: str) -> str:
    """Path of a job under the Dagster webserver, relative to its base URL."""
    return f"/locations/{config.DAGSTER_LOCATION}/jobs/{job}"


def dagster_asset_path(key: str) -> str:
    """Path of an asset's catalog page under the Dagster webserver, relative to its base URL.

    ``key`` is the agent's `produces.asset` value; its ``/``-joined segments map
    directly onto the webserver's ``/assets/<segment>/...`` route.
    """
    return f"/assets/{key}"


def _dagster(name: str) -> tuple[str, str]:
    job = "agent_" + str(name).replace("-", "_")
    return job, config.DAGSTER_URL + dagster_job_path(job)


def agent_exists(stem: str) -> bool:
    """Whether ``agents/<stem>.yaml`` already exists (create uniqueness check)."""
    return _safe_stem(stem) and os.path.isfile(_path(stem))


def read_agent(stem: str, base_dir: str | None = None) -> dict:
    """Read one agent file into a rich definition dict.

    ``base_dir`` overrides the directory read from (default: the instance agents dir);
    ``read_template`` passes the product examples tree so a template pre-fill reads the
    same shape an edit would, without the template living in the instance dir.

    The returned dict always has: ``stem``, ``file``, ``agent`` (the definition,
    or None on parse error), ``parse_error``, ``raw`` (file text when unparsable),
    ``name_mismatch``, ``editable``, ``is_template``, ``schema_version``,
    ``dagster_job``, ``dagster_kind``, ``dagster_path``, ``dagster_url``, and
    ``name`` (best-effort identity). ``dagster_kind``/``dagster_path``/``dagster_url``
    point at the agent's asset page when it declares an asset (asset wins for a
    both-kind agent), and at the job ``agent_<stem>`` otherwise — including when
    the file cannot be parsed and the nature is unknown.
    """
    if not _safe_stem(stem):
        # Traversal or a separator in the stem: no such addressable agent (404).
        raise FileNotFoundError(stem)
    path = _path(stem, base_dir)
    is_template = stem.startswith("_")
    result = {
        "stem": stem,
        "name": stem,
        "file": f"{stem}.yaml",
        "agent": None,
        "parse_error": None,
        "raw": None,
        "name_mismatch": False,
        "editable": True,
        "is_template": is_template,
        "schema_version": None,
    }
    result["dagster_job"], result["dagster_url"] = _dagster(stem)
    result["dagster_kind"] = "job"
    result["dagster_path"] = dagster_job_path(result["dagster_job"])

    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise
    except OSError as e:
        raise StorageError("read", f"agents/{stem}.yaml", e)

    m = _SCHEMA_HEADER_RE.search(text)
    file_version = int(m.group(1)) if m else 0
    result["schema_version"] = file_version

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as e:
        result["parse_error"] = f"not valid YAML: {e}"
        result["raw"] = text
        return result

    if loaded is None or not isinstance(loaded, dict):
        result["parse_error"] = "file is empty or not a mapping"
        result["raw"] = text
        return result

    if "name" not in loaded or "harness" not in loaded:
        missing = [k for k in ("name", "harness") if k not in loaded]
        result["parse_error"] = f"missing required key(s): {', '.join(missing)}"
        result["raw"] = text
        return result

    if "schedule" in loaded:
        # A stray legacy `schedule` key left the agent schema (spec 005) and the migration drops
        # it; name the file so the operator knows it was ignored. Triggering now lives in the
        # agent's own `triggers:` block (spec 006).
        _log.warning(
            "agents/%s.yaml carries a `schedule` key — dropped on read (triggering now lives in "
            "the agent's `triggers:` block); it is removed from the file on the next save from the UI",
            stem,
        )

    try:
        loaded = schema.apply_migrations(loaded, file_version)
    except SchemaTooNew as e:
        result["parse_error"] = str(e)
        result["editable"] = False
        result["raw"] = text
        return result
    except Exception as e:
        # A migration function raised on this file: surface it as a parse error and
        # leave the file untouched (read never writes). It can still be deleted.
        result["parse_error"] = f"schema migration failed: {e}"
        result["raw"] = text
        return result

    # Lift a nested `produces:` block into the flat asset/partition managed fields so the
    # form shows them and they round-trip — never routed to "Unmanaged" (contract §3). An
    # asset-less produces surfaces as a present-but-empty `asset` so validate flags the
    # empty declaration; a produces that is not a mapping is treated the same way.
    produces = loaded.pop("produces", _MISSING)
    if produces is not _MISSING:
        block = produces if isinstance(produces, dict) else {}
        loaded["asset"] = block.get("asset", "")
        if "partition" in block:
            loaded["partition"] = block["partition"]
        if "checks" in block:
            loaded["checks"] = block["checks"]
        if "depends_on" in block:
            loaded["depends_on"] = block["depends_on"]

    # Lift the nested `triggers:` block into flat asset_schedule/job_schedule managed fields the
    # same way `produces` is lifted — never routed to "Unmanaged" (contract agent-model §2). An
    # absent block, or one that is not a mapping, yields both fields unset.
    triggers = loaded.pop("triggers", _MISSING)
    if triggers is not _MISSING:
        block = triggers if isinstance(triggers, dict) else {}
        if "asset_schedule" in block:
            loaded["asset_schedule"] = block["asset_schedule"]
        if "job_schedule" in block:
            loaded["job_schedule"] = block["job_schedule"]
        if "on_upstream" in block:
            loaded["on_upstream"] = block["on_upstream"]
        if "on_missing" in block:
            loaded["on_missing"] = block["on_missing"]

    # Separate schema-managed keys from unmanaged ones.
    managed: dict = {}
    unmanaged: dict = {}
    for k, v in loaded.items():
        if k in FIELDS_BY_ID:
            managed[k] = v
        else:
            unmanaged[k] = v
    if unmanaged:
        managed["unmanaged"] = unmanaged

    stored_name = loaded.get("name")
    result["name"] = stored_name if stored_name is not None else stem
    result["name_mismatch"] = stored_name != stem
    result["agent"] = managed

    # An agent that declares an asset lives on Dagster's asset page, not the job page
    # (asset wins for a both-kind agent — its job exists only to materialize the asset).
    asset = managed.get("asset")
    if isinstance(asset, str) and asset.strip():
        result["dagster_kind"] = "asset"
        result["dagster_path"] = dagster_asset_path(asset.strip())
        result["dagster_url"] = config.DAGSTER_URL + result["dagster_path"]
    return result


def read_template(stem: str) -> dict:
    """Read one product-owned starter from the examples tree (FR-008, R7).

    Same rich shape as ``read_agent`` (so the create form's pre-fill matches an edit),
    but read from ``config.TEMPLATES_DIR`` rather than the instance agents dir.
    """
    return read_agent(stem, base_dir=_templates_dir())


def list_templates() -> list[dict]:
    """Product-owned starters offered by the create form's picker (FR-008, R7).

    Sourced from the examples tree (``config.TEMPLATES_DIR``), not the instance agents dir;
    each row carries just ``file`` and ``harness``. Only ``_``-prefixed files are picker
    templates — the examples tree also ships non-template sample agents (e.g.
    ``hello-example.yaml``) a fresh install copies as real starters, which are not offered
    as templates. A missing examples tree yields no templates rather than an error (a box may
    run without the product examples mounted).
    """
    try:
        paths = sorted(glob.glob(os.path.join(_templates_dir(), "_*.yaml")))
    except OSError:
        return []
    templates: list[dict] = []
    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        info = read_template(stem)
        harness = info["agent"].get("harness") if info["agent"] else None
        templates.append({"file": info["file"], "harness": harness})
    return templates


def asset_graph(exclude: str | None = None) -> dict[str, list[str]]:
    """The ``{asset_key: [depends_on...]}`` graph over every asset-declaring instance agent.

    Source for the form's best-effort author-time cross-check (spec 013 §3): existence + cycle
    checks against the known agent set. ``exclude`` omits one stem (the agent being saved, so its
    stored edges do not shadow the proposed ones). A missing/unreadable file is skipped, not fatal.
    """
    graph: dict[str, list[str]] = {}
    try:
        paths = sorted(glob.glob(os.path.join(_agents_dir(), "*.yaml")))
    except OSError:
        return graph
    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        if exclude is not None and stem == exclude:
            continue
        try:
            info = read_agent(stem)
        except (FileNotFoundError, OSError):
            continue
        agent = info.get("agent") or {}
        asset = agent.get("asset")
        if isinstance(asset, str) and asset.strip():
            deps = agent.get("depends_on")
            graph[asset.strip()] = (
                [d for d in deps if isinstance(d, str)] if isinstance(deps, list) else []
            )
    return graph


def _list_view_fields(stem: str, agent: dict) -> dict:
    """Derive the tabbed-list row's kind/crons/checks from a parsed definition.

    The canonical cron ``type`` (``job_schedule`` / ``asset_schedule``) drives the pill icon
    and, via the factory's registration naming, the ``dagster_name`` the activity read and the
    toggle address (contract dagster-activity §0): ``sched_<stem>`` for a job schedule,
    ``autocond_<stem>`` for an asset schedule, with ``-`` → ``_`` so it matches
    ``orchestrator/factory.py``. Missing data is unknown, not zero: no schedule → empty list.
    """
    dagster_stem = str(stem).replace("-", "_")
    asset_val = agent.get("asset")
    is_asset = isinstance(asset_val, str) and asset_val.strip() != ""
    is_job = agent.get("job") is True

    crons: list[dict] = []
    asset_sched = agent.get("asset_schedule")
    if isinstance(asset_sched, str) and asset_sched.strip():
        crons.append({"type": "asset_schedule", "expr": asset_sched.strip(),
                      "dagster_name": f"autocond_{dagster_stem}"})
    # The two asset-kind event triggers (spec 013, FR-020) show as pills on the same paused
    # autocond_<stem> sensor as asset_schedule; they carry a fixed label (no cron expr).
    if agent.get("on_upstream") is True:
        crons.append({"type": "on_upstream", "expr": None, "label": "on upstream",
                      "dagster_name": f"autocond_{dagster_stem}"})
    if agent.get("on_missing") is True:
        crons.append({"type": "on_missing", "expr": None, "label": "on missing",
                      "dagster_name": f"autocond_{dagster_stem}"})
    job_sched = agent.get("job_schedule")
    if isinstance(job_sched, str) and job_sched.strip():
        crons.append({"type": "job_schedule", "expr": job_sched.strip(),
                      "dagster_name": f"sched_{dagster_stem}"})

    declared = agent.get("checks")
    checks = (
        [{"name": c["name"]} for c in declared if isinstance(c, dict) and c.get("name")]
        if isinstance(declared, list) else []
    )
    return {"is_asset": is_asset, "is_job": is_job, "crons": crons, "checks": checks}


def list_agents() -> dict:
    """List agent files, split into ``agents`` and picker ``templates``.

    ``agents`` are the instance agents dir's files; ``templates`` are the product-owned
    starters from the examples tree (``list_templates``). Genuine instance agents never
    start with ``_`` (templates moved to the examples tree — R7), so the ``is_template``
    check here is now only a defensive guard: it keeps any stray ``_``-prefixed file (e.g.
    a template a fresh-install copied into ``config/agents/``) out of the agent list rather
    than surfacing it as a fake agent. Each agent row carries the list-page fields from
    contracts/http-api.md; each template row carries just ``file`` and ``harness``.
    """
    agents: list[dict] = []
    try:
        paths = sorted(glob.glob(os.path.join(_agents_dir(), "*.yaml")))
    except OSError as e:
        raise StorageError("read", "agents/", e)

    for path in paths:
        stem = os.path.splitext(os.path.basename(path))[0]
        info = read_agent(stem)
        if info["is_template"]:
            continue  # defensive: never list a stray _-prefixed file as an agent
        agent = info["agent"] or {}
        row = {
            "name": info["name"],
            "file": info["file"],
            "enabled": agent.get("enabled") if info["agent"] else None,
            "harness": agent.get("harness") if info["agent"] else None,
            "model": agent.get("model") if info["agent"] else None,
            "dagster_job": info["dagster_job"],
            "dagster_path": info["dagster_path"],
            "dagster_url": info["dagster_url"],
            "parse_error": info["parse_error"],
            "name_mismatch": info["name_mismatch"],
            "editable": info["editable"],
        }
        # Kind / crons / checks for the tabbed list (contract agents-list-view §A). All
        # derive from the parsed definition, so a parse-error row (agent == {}) is neither
        # asset nor job, with no crons or checks — it still renders, just without a Kind.
        row.update(_list_view_fields(stem, agent if info["agent"] else {}))
        agents.append(row)
    return {"agents": agents, "templates": list_templates()}


# --- Emitter --------------------------------------------------------------
_HEADER_GENERATED = "# Generated by the agentbox UI — edits made here are replaced on the next save from the UI."


def _emit_scalar(value) -> str:
    """Serialise a single scalar the way it should appear after ``key:``.

    Uses PyYAML flow style so quoting is always valid, then strips the trailing
    document-end marker PyYAML adds for a bare scalar.
    """
    text = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True, width=10**9)
    lines = text.splitlines()
    if lines and lines[-1] == "...":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _value_for(agent: dict, fid: str, harness: str):
    """The value to emit for a field, filling always-written defaults when missing."""
    if fid in agent:
        return agent[fid]
    if fid == "network":
        return HARNESS_BY_ID[harness]["default_network"]
    if fid == "enabled":
        return True
    return _MISSING


def _field_lines(agent: dict, f, harness: str) -> list[str]:
    """The emitted line(s) for one applicable field (real, commented, or list/map)."""
    help_text = schema.field_help(f.id, harness)
    raw = _value_for(agent, f.id, harness)
    unset = raw is _MISSING or schema._is_unset(f, raw)

    if unset and f.id not in ALWAYS_WRITTEN:
        return [f"#{f.id}:  # {help_text}"]

    if unset and f.id in ALWAYS_WRITTEN:
        # substitute a concrete default so the line is real
        raw = {"network": HARNESS_BY_ID[harness]["default_network"],
               "enabled": True}.get(f.id, "")

    if f.type == "list":
        lines = [f"{f.id}:  # {help_text}"]
        for item in raw:
            lines.append(f"  - {_emit_scalar(item)}")
        return lines
    if f.type == "map":
        lines = [f"{f.id}:  # {help_text}"]
        for k, v in raw.items():
            lines.append(f"  {k}: {_emit_scalar(v)}")
        return lines
    return [f"{f.id}: {_emit_scalar(raw)}  # {help_text}"]


# The order check fields are emitted in each `- ` mapping under `produces.checks` (contract §5).
_CHECK_FIELD_ORDER = ["name", "command", "image", "blocking", "timeout_seconds", "network"]


def _check_item_lines(check: dict) -> list[str]:
    """One check emitted as a `- ` sequence item under `produces.checks:`.

    Only the fields the check actually sets are written, in a canonical order; the first
    field carries the `- ` list marker (4-space indent), the rest align under it (6 spaces).
    """
    lines: list[str] = []
    for fid in _CHECK_FIELD_ORDER:
        if fid not in check:
            continue
        prefix = "    - " if not lines else "      "
        lines.append(f"{prefix}{fid}: {_emit_scalar(check[fid])}")
    return lines


def _produces_block_lines(agent: dict, harness: str) -> list[str]:
    """The `produces:` block lines: a real nested block when `asset` is set, else the
    whole block commented-out (opt-in, matching the templates — contract §3/FR-016).

    ``asset`` and ``partition`` are schema fields but children of a `produces` block, so
    they are emitted here as a nested mapping rather than two flat top-level keys. When the
    asset carries ``checks`` (spec 008), they follow as a nested sequence-of-mappings under a
    ``checks:`` header comment; with no checks nothing is emitted for them (contract §5).
    """
    asset_help = schema.field_help("asset", harness)
    part_help = schema.field_help("partition", harness)
    part_default = FIELDS_BY_ID["partition"].default  # "none"
    asset_val = agent.get("asset")
    has_asset = not (asset_val is None or (isinstance(asset_val, str) and asset_val.strip() == ""))
    header = schema.PRODUCES_BLOCK_HELP
    if has_asset:
        part_val = agent.get("partition")
        if part_val is None or part_val == "":
            part_val = part_default
        lines = [
            f"produces:  # {header}",
            f"  asset: {_emit_scalar(asset_val)}  # {asset_help}",
            f"  partition: {_emit_scalar(part_val)}  # {part_help}",
        ]
        # The declared upstream asset keys (spec 013), emitted as a nested sequence beside
        # asset/partition/checks; written only when non-empty (contract agent-model §4).
        depends_on = agent.get("depends_on")
        if isinstance(depends_on, list) and depends_on:
            lines.append(f"  depends_on:  # {schema.field_help('depends_on', harness)}")
            for key in depends_on:
                lines.append(f"    - {_emit_scalar(key)}")
        checks = agent.get("checks")
        if isinstance(checks, list) and checks:
            lines.append(f"  checks:  # {schema.CHECKS_BLOCK_HELP}")
            for check in checks:
                if isinstance(check, dict):
                    lines.extend(_check_item_lines(check))
        return lines
    return [
        f"#produces:  # {header}",
        f"#  asset:  # {asset_help}",
        f"#  partition: {part_default}  # {part_help}",
    ]


def _has_value(agent: dict, fid: str) -> bool:
    """Whether ``agent[fid]`` is a real (non-unset) value."""
    v = agent.get(fid)
    return not (v is None or (isinstance(v, str) and v.strip() == ""))


def _trigger_set(agent: dict, fid: str) -> bool:
    """Whether a trigger field carries a real value to emit: a non-empty cron, or a True bool.

    ``on_upstream``/``on_missing`` are bools defaulting to false; only a ``True`` value is written
    (like the other opt-in fields, they are absent when off). Cron fields keep the string rule.
    """
    if FIELDS_BY_ID[fid].type == "bool":
        return agent.get(fid) is True
    return _has_value(agent, fid)


def _triggers_block_lines(agent: dict, harness: str) -> list[str]:
    """The `triggers:` block lines (contract agent-model §2/§5).

    Re-nests the flat ``asset_schedule``/``on_upstream``/``on_missing``/``job_schedule`` fields
    into a ``triggers:`` block. A trigger whose kind is off (an asset-kind trigger on a non-asset
    agent, ``job_schedule`` on an agent with no job) is omitted entirely. When at least one
    applicable trigger is set the block is real (an applicable-but-unset trigger appears as a
    commented child); when none is set the whole block is emitted commented-out so an author can
    opt in by uncommenting — mirroring ``_produces_block_lines``.
    """
    header = schema.TRIGGERS_BLOCK_HELP
    is_asset = _has_value(agent, "asset")
    is_job = agent.get("job") is True
    applicable = []
    if is_asset:  # the asset-kind triggers (spec 006 asset_schedule + spec 013 on_upstream/on_missing)
        applicable += ["asset_schedule", "on_upstream", "on_missing"]
    if is_job:
        applicable.append("job_schedule")
    if not applicable:  # neither kind (an invalid agent the emitter still renders defensively)
        applicable = ["asset_schedule", "on_upstream", "on_missing", "job_schedule"]

    any_set = any(_trigger_set(agent, fid) for fid in applicable)
    if any_set:
        lines = [f"triggers:  # {header}"]
        for fid in applicable:
            help_text = schema.field_help(fid, harness)
            if _trigger_set(agent, fid):
                lines.append(f"  {fid}: {_emit_scalar(agent[fid])}  # {help_text}")
            else:
                lines.append(f"#  {fid}:  # {help_text}")
        return lines
    return [f"#triggers:  # {header}"] + [
        f"#  {fid}:  # {schema.field_help(fid, harness)}" for fid in applicable
    ]


def _job_line(agent: dict, harness: str) -> list[str]:
    """The `job:` flag line: real when the agent has a job, commented placeholder otherwise
    (contract agent-model §1/§5) — the Job group's opt-in flag, kept visible like the
    produces/triggers blocks so an author can enable it by uncommenting."""
    help_text = schema.field_help("job", harness)
    if agent.get("job") is True:
        return [f"job: true  # {help_text}"]
    return [f"#job:  # {help_text}"]


def emit_yaml(agent: dict) -> str:
    """Render an agent definition to its full YAML file text (contract agent-yaml.md).

    ``agent`` is a flat mapping of schema fields plus an optional ``unmanaged``
    sub-mapping (or unmanaged keys left at the top level). Output is deterministic:
    the same definition always produces byte-identical text.

    A caller may also pass a definition straight from a file, where ``produces`` is
    still a nested block rather than the flat ``asset``/``partition`` fields the reader
    lifts it into; emit lifts it the same way so the block is never dropped.
    """
    harness = agent.get("harness")
    if harness not in HARNESS_BY_ID:
        raise ValueError(f"unknown harness: {harness!r}")

    # A caller may pass a definition straight from a file, where `produces`/`triggers` are still
    # nested blocks rather than the flat fields the reader lifts them into; lift them the same
    # way here so a block is never dropped.
    if agent.get("produces", _MISSING) is not _MISSING or agent.get("triggers", _MISSING) is not _MISSING:
        agent = dict(agent)
    produces = agent.get("produces", _MISSING)
    if produces is not _MISSING:
        block = agent.pop("produces") if isinstance(produces, dict) else {}
        agent.setdefault("asset", block.get("asset", ""))
        if "partition" in block:
            agent.setdefault("partition", block["partition"])
        if "checks" in block:
            agent.setdefault("checks", block["checks"])
        if "depends_on" in block:
            agent.setdefault("depends_on", block["depends_on"])
    triggers = agent.get("triggers", _MISSING)
    if triggers is not _MISSING:
        block = agent.pop("triggers") if isinstance(triggers, dict) else {}
        if "asset_schedule" in block:
            agent.setdefault("asset_schedule", block["asset_schedule"])
        if "job_schedule" in block:
            agent.setdefault("job_schedule", block["job_schedule"])
        if "on_upstream" in block:
            agent.setdefault("on_upstream", block["on_upstream"])
        if "on_missing" in block:
            agent.setdefault("on_missing", block["on_missing"])

    desc = HARNESS_BY_ID[harness]["description"]
    lines = [f"# {desc}", _HEADER_GENERATED, f"# agentbox-schema: {schema.SCHEMA_VERSION}"]

    applicable = set(schema.applicable_fields(harness))
    for section in SECTIONS:
        # The Produces section is a nested block that is always emitted (commented-out when
        # no asset is set): unlike other optional sections it stays visible so an author can
        # opt in by uncommenting (contract §3/§7).
        if section["id"] == "produces":
            lines.append("")
            lines.append(f"# --- {section['label']} ---")
            lines.extend(_produces_block_lines(agent, harness))
            continue
        # The Triggers block and the Job flag are nested/opt-in sections kept always-visible
        # (like Produces) so an author can enable them by uncommenting (contract §2/§5).
        if section["id"] == "triggers":
            lines.append("")
            lines.append(f"# --- {section['label']} ---")
            lines.extend(_triggers_block_lines(agent, harness))
            continue
        if section["id"] == "run_as_job":
            lines.append("")
            lines.append(f"# --- {section['label']} ---")
            lines.extend(_job_line(agent, harness))
            continue
        sec_fields = [f for f in FIELDS if f.section == section["id"] and f.id in applicable]
        rendered: list[str] = []
        for f in sec_fields:
            raw = _value_for(agent, f.id, harness)
            has_value = not (raw is _MISSING or schema._is_unset(f, raw))
            if has_value or f.id in ALWAYS_WRITTEN:
                rendered.extend(_field_lines(agent, f, harness))
            else:
                rendered.append(f"#{f.id}:  # {schema.field_help(f.id, harness)}")
        # A section appears only if it holds at least one real (uncommented) line.
        if any(not ln.startswith("#") for ln in rendered):
            lines.append("")
            lines.append(f"# --- {section['label']} ---")
            lines.extend(rendered)

    # Unmanaged keys, emitted verbatim so the UI never drops what it does not know. A stray
    # nested `produces` key is never unmanaged — its fields are emitted as the block above.
    unmanaged = dict(agent.get("unmanaged") or {})
    for k, v in agent.items():
        if k not in FIELDS_BY_ID and k not in ("unmanaged", "produces", "triggers"):
            unmanaged[k] = v
    if unmanaged:
        lines.append("")
        lines.append("# --- Unmanaged (not edited by the UI) ---")
        dumped = yaml.safe_dump(unmanaged, default_flow_style=False, allow_unicode=True, width=10**9)
        lines.extend(dumped.rstrip("\n").splitlines())

    return "\n".join(lines) + "\n"


def write_agent(stem: str, agent: dict) -> str:
    """Write an agent definition atomically. Returns the file path.

    ``name`` is forced to the filename stem (the identity, FR-010). The write is
    a temp file in the same directory then ``os.replace``; UTF-8, LF endings, one
    trailing newline.
    """
    if not _safe_stem(stem):
        raise ValueError(f"unsafe agent name: {stem!r}")
    agent = dict(agent)
    agent["name"] = stem
    text = emit_yaml(agent)
    directory = _agents_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{stem}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, _path(stem))
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    except OSError as e:
        raise StorageError("write", f"agents/{stem}.yaml", e)
    return _path(stem)


def delete_agent(stem: str) -> str:
    """Delete an agent file. Raises FileNotFoundError if absent. Touches nothing else."""
    if not _safe_stem(stem):
        raise FileNotFoundError(stem)
    path = _path(stem)
    try:
        os.remove(path)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise StorageError("delete", f"agents/{stem}.yaml", e)
    return f"{stem}.yaml"
