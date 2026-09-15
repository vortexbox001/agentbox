"""The stack wiring keeps all three roots relocatable (spec 010 US3 / FR-013).

`docker-compose.yml` must thread `AGENTBOX_CONFIG` the same way it threads `AGENTBOX_DATA`
and `DAGSTER_HOME`: as a `${VAR}`-substituted, host==container mount — never a fixed
container path. Regression guard for the gap where `AGENTBOX_CONFIG` was hardcoded to
`/opt/agentbox/config` and the config-root mount was sourced from `AGENTBOX_HOST_REPO`, so
setting `AGENTBOX_CONFIG` in `.env` silently did nothing and the config root could not be
relocated in the compose stack (while `.env.example`/README advertised that it could).
"""
import os

import yaml

COMPOSE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml"))


def _text() -> str:
    with open(COMPOSE, encoding="utf-8") as f:
        return f.read()


def _services() -> dict:
    return yaml.safe_load(_text())["services"]


def _string_volumes(svc: dict) -> list[str]:
    return [v for v in svc.get("volumes", []) if isinstance(v, str)]


def _split_volume(v: str) -> list[str]:
    """Split a short-syntax volume on top-level ':' only — never on the ':' inside a
    ``${VAR:-default}`` substitution (brace depth > 0)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in v:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == ":" and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def test_no_hardcoded_container_config_path():
    # The old wiring pinned the config root to /opt/agentbox/config inside the container.
    assert "/opt/agentbox/config" not in _text(), (
        "config root is pinned to a fixed container path; thread it from ${AGENTBOX_CONFIG} "
        "so the root is relocatable like AGENTBOX_DATA/DAGSTER_HOME (US3/FR-013)"
    )


def test_all_three_roots_are_threaded():
    text = _text()
    for var in ("AGENTBOX_CONFIG", "AGENTBOX_DATA", "DAGSTER_HOME"):
        assert "${" + var in text, f"{var} is not threaded as a ${{}} substitution in compose"


def test_config_root_mounts_are_host_equals_container():
    # Every config-root mount (the ones whose *target* is the config root, not the single
    # rendered-file mount at /app/config.yaml) must be host==container so the orchestrator's
    # Docker-outside-of-Docker host_path() resolves prompt bind sources correctly when relocated.
    seen = 0
    for name, svc in _services().items():
        for v in _string_volumes(svc):
            src, tgt = _split_volume(v)[0], _split_volume(v)[1]
            if "AGENTBOX_CONFIG" in tgt:  # a config-root mount, not the /app/config.yaml file mount
                seen += 1
                assert src == tgt, f"{name}: config-root mount must be host==container, got {v!r}"
    assert seen, "no service mounts the config root via ${AGENTBOX_CONFIG}"
