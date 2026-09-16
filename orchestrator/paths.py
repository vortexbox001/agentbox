"""The orchestrator's single root-resolution point (FR-002, SC-009).

Every path the orchestrator/daemon touches derives from the three root env vars read
*once* here at import — no other orchestrator module reads a state/config root env var or
carries a literal ``/data`` / ``/opt/agentbox`` path. The UI mirrors this module in
``ui/config.py`` (the two processes run in separate containers with no shared import);
a shared-fixture parity test pins the duplicated constants in agreement.

Roots (contracts/path-resolution.md §1):

  * ``AGENTBOX_CONFIG`` — instance-configuration root (default ``<product>/config``)
  * ``AGENTBOX_DATA``   — instance-state root       (default ``/data/agentbox``)
  * ``DAGSTER_HOME``    — Dagster-storage root      (default ``/data/dagster``)

Access these as module attributes (``paths.RUNS_ROOT``) rather than importing the names
directly, so tests can monkeypatch / reload them.
"""
import os
from pathlib import Path

# --- Product tree ------------------------------------------------------------
# The repo checkout, read-only in every service. In the orchestrator container the repo is
# mounted at /opt/agentbox; on a dev host this is the real checkout. Derived from this file's
# location (orchestrator/paths.py -> orchestrator/ -> product root) so it is right in both.
PRODUCT_ROOT = str(Path(__file__).resolve().parent.parent)

# Host path of the product checkout, for Docker-outside-of-Docker `-v` sources: agent
# containers are launched by the HOST daemon, which resolves bind-mount sources against the
# host filesystem, so a source under the container's product mount must be rewritten to its
# host equivalent (see `host_path`). Defaults to PRODUCT_ROOT (correct on a dev host).
HOST_REPO = os.environ.get("AGENTBOX_HOST_REPO") or PRODUCT_ROOT

# --- The three roots (read once at import) -----------------------------------
CONFIG_ROOT = os.environ.get("AGENTBOX_CONFIG") or os.path.join(PRODUCT_ROOT, "config")
DATA_ROOT = os.environ.get("AGENTBOX_DATA") or "/data/agentbox"
DAGSTER_ROOT = os.environ.get("DAGSTER_HOME") or "/data/dagster"

# --- Instance-configuration subpaths (under CONFIG_ROOT) ---------------------
AGENTS_DIR = os.path.join(CONFIG_ROOT, "agents")
AGENTS_GLOB = os.path.join(AGENTS_DIR, "*.yaml")
PROMPTS_DIR = os.path.join(CONFIG_ROOT, "prompts")
# Instance settings file (spec 012): retention policy the nightly prune job reads. Mirrored by
# ui/config.SETTINGS_FILE (the UI writes it, the orchestrator reads it), pinned by the parity test.
SETTINGS_FILE = os.path.join(CONFIG_ROOT, "settings.yaml")

# --- Instance-state subpaths (under DATA_ROOT — FR-010/FR-011) ---------------
# Per-run records incl. the transcripts the Dagster home used to hold (moved out, FR-010/R3).
RUNS_ROOT = os.path.join(DATA_ROOT, "runs")
# Ephemeral per-run staging the harness images write events.jsonl + context-harness.json to
# (spec 012, T010a). It MUST live under DATA_ROOT (a host==container bind mount), never the
# container-private /tmp: agent containers launch Docker-outside-of-Docker, so the host daemon
# resolves the `-v` source against the host filesystem (same pitfall as PIPES_ROOT). Cleaned per
# run; it is not /output and grants no network or credential reach (Constitution I).
STAGING_ROOT = os.path.join(DATA_ROOT, "staging")
OUTPUTS_ROOT = os.path.join(DATA_ROOT, "outputs")
WORKSPACES_ROOT = os.path.join(DATA_ROOT, "workspaces")
CREDENTIALS_ROOT = os.path.join(DATA_ROOT, "credentials")  # owner-only (700), FR-011
KEYS_ROOT = os.path.join(DATA_ROOT, "keys")                # owner-only (700), FR-011

# --- Dagster-storage subpaths (under DAGSTER_ROOT) ---------------------------
# The transient Dagster Pipes messages dir is the ONLY agentbox-owned thing that stays under
# the Dagster home: agent containers are launched Docker-outside-of-Docker, so the pipes dir
# MUST sit on a host==container bind mount, which the Dagster home is (FR-010/FR-012, R4).
PIPES_ROOT = os.path.join(DAGSTER_ROOT, "pipes")


# --- Run-directory layout (spec 012, contracts/run-directory.md) -------------
# A run is a DIRECTORY, runs/<agent>/<YYYY-MM-DD>/<run-id>/, holding exactly four files. The
# orchestrator writes them (context first, at launch); the viewer reads them (any may be absent
# — partial write, pruning, or a legacy transcript-only run). The four filenames are constants so
# the orchestrator (writer) and ui/runs_store (reader) never disagree — the two run in separate
# containers with no shared import, so the reader duplicates these names (pinned by the same
# parity discipline as the roots above).
RUN_TRANSCRIPT = "transcript.jsonl"   # native harness stream, redacted     (pruned by retention)
RUN_EVENTS = "events.jsonl"           # normalized events, redacted         (pruned by retention)
RUN_CONTEXT = "context.json"          # frozen launch snapshot, redacted    (ALWAYS kept)
RUN_REPORT = "report.json"            # spec-007 run report                 (ALWAYS kept)


def run_dir(agent: str, date: str, run_id: str) -> str:
    """The per-run directory ``runs/<agent>/<YYYY-MM-DD>/<run-id>/`` (spec 012 FR-001)."""
    return os.path.join(RUNS_ROOT, agent, date, run_id)


def run_file(agent: str, date: str, run_id: str, filename: str) -> str:
    """A path to one file inside a run directory (pass one of the ``RUN_*`` constants)."""
    return os.path.join(run_dir(agent, date, run_id), filename)


def legacy_transcript(agent: str, date: str, run_id: str) -> str:
    """The pre-spec-012 flat transcript path ``runs/<agent>/<date>/<run-id>.jsonl``.

    Kept for backward compatibility: a flat ``.jsonl`` still on disk is surfaced by the viewer
    as a transcript-only run (no events/context/report), rendered with the "conversation only"
    degradation. No bulk migration — old flat runs age out under retention (R1).
    """
    return os.path.join(RUNS_ROOT, agent, date, f"{run_id}.jsonl")


def default_output_dir(name: str) -> str:
    """The documented default ``output_dir`` for an agent — ``$AGENTBOX_DATA/outputs/<name>``."""
    return os.path.join(OUTPUTS_ROOT, name)


def default_workspace(name: str) -> str:
    """The default ``workspace`` for an agent — ``$AGENTBOX_DATA/workspaces/<name>``."""
    return os.path.join(WORKSPACES_ROOT, name)


def host_path(container_path: str) -> str:
    """Rewrite a container-visible path under the product tree to its host equivalent.

    Agent containers are launched Docker-outside-of-Docker: the host daemon resolves
    ``docker run -v`` sources against the HOST filesystem, so a bind source under the
    orchestrator container's product mount (``PRODUCT_ROOT``, e.g. ``/opt/agentbox``) must be
    rewritten to ``HOST_REPO`` before it reaches ``docker run``. Paths under the data and
    Dagster roots are bind-mounted host==container, so they pass through unchanged.
    """
    p = os.path.abspath(container_path)
    if p == PRODUCT_ROOT:
        return HOST_REPO
    if p.startswith(PRODUCT_ROOT + os.sep):
        return HOST_REPO + p[len(PRODUCT_ROOT):]
    return p


# Host-path forms used when composing `docker run -v` sources (contract §2). Config content
# (e.g. prompt files) may live under the product tree by default, so its bind sources need the
# host rewrite; data/dagster roots are host==container and rewrite to themselves.
CONFIG_ROOT_HOST = host_path(CONFIG_ROOT)
PROMPTS_DIR_HOST = host_path(PROMPTS_DIR)
DATA_ROOT_HOST = host_path(DATA_ROOT)
DAGSTER_ROOT_HOST = host_path(DAGSTER_ROOT)
