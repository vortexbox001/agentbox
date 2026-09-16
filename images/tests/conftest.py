"""Shared pytest fixtures for the per-harness report-parser tests (spec 007).

The parsers under test live in each harness image directory and import the shared
report helper as ``lib.agent_report``. Inside a container the image copies both
``lib/`` and the harness module next to each other; in the test tree we reproduce
that by putting ``images/`` on ``sys.path`` so ``import lib.agent_report`` and
``import agent_python.runner`` (etc.) resolve exactly as they do in the image.

Also provides ``assert_report_valid`` — a dependency-free conformance check of a
produced report against ``contracts/run-report.schema.json`` (T013/T021), so every
``test_<harness>_report.py`` validates the shape without pulling in ``jsonschema``.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# images/tests/conftest.py -> images/ (holds lib/ and the harness dirs).
IMAGES_DIR = Path(__file__).resolve().parents[1]
if str(IMAGES_DIR) not in sys.path:
    sys.path.insert(0, str(IMAGES_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def load_module():
    """Load a harness module by file path (its dir name has a hyphen, so it is not an
    importable package). The module's own ``from lib.agent_report import ...`` resolves
    via ``images/`` on ``sys.path`` — exactly as it does when run inside the image."""
    def _load(rel_path: str, modname: str):
        path = IMAGES_DIR / rel_path
        spec = importlib.util.spec_from_file_location(modname, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return _load


@pytest.fixture
def fixture_lines():
    """Read a recorded native-event fixture as a list of lines."""
    def _read(name: str):
        return (FIXTURES_DIR / name).read_text().splitlines()
    return _read

# contracts/run-report.schema.json for the feature.
SCHEMA_PATH = (
    IMAGES_DIR.parent
    / "specs" / "007-run-reports-via-pipes" / "contracts" / "run-report.schema.json"
)

_JSON_TYPES = {
    "integer": int,
    "number": (int, float),
    "string": str,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _check_type(value, spec: dict, field: str) -> None:
    """Assert ``value`` matches a JSON-schema ``type`` (possibly a list incl. 'null')."""
    types = spec.get("type")
    if types is None:
        return
    allowed = types if isinstance(types, list) else [types]
    if value is None:
        assert "null" in allowed, f"{field}: null not permitted (allowed: {allowed})"
        return
    py = tuple(_JSON_TYPES[t] for t in allowed if t != "null")
    # bool is an int subclass in Python; reject it where only integer/number is meant
    if py and isinstance(value, bool) and bool not in py:
        raise AssertionError(f"{field}: bool where {allowed} expected")
    assert isinstance(value, py), f"{field}: {type(value).__name__} not in {allowed}"
    if "minimum" in spec and value is not None:
        assert value >= spec["minimum"], f"{field}: {value} < minimum {spec['minimum']}"


def assert_report_valid(report: dict) -> None:
    """Validate ``report`` against run-report.schema.json (required keys, types,
    the status enum, ``additionalProperties: false``, and the status/error
    conditional). Raises ``AssertionError`` on any nonconformance."""
    schema = _load_schema()
    props = schema["properties"]
    # additionalProperties: false — no stray keys
    extra = set(report) - set(props)
    assert not extra, f"unexpected report keys: {sorted(extra)}"
    # every required key present
    missing = set(schema["required"]) - set(report)
    assert not missing, f"missing required report keys: {sorted(missing)}"
    # per-field type/enum/minimum
    for field, spec in props.items():
        if field not in report:
            continue
        value = report[field]
        if "enum" in spec:
            assert value in spec["enum"], f"{field}: {value!r} not in {spec['enum']}"
        _check_type(value, spec, field)
    # error non-null iff status != ok
    if report["status"] == "ok":
        assert report["error"] is None, "status ok must have null error"
    else:
        assert isinstance(report["error"], str), "non-ok status must have a string error"


@pytest.fixture
def report_validator():
    """Expose :func:`assert_report_valid` as a fixture for parser tests."""
    return assert_report_valid


# contracts/normalized-event.schema.json (spec 012) — for the per-harness to_events() tests.
EVENT_SCHEMA_PATH = (
    IMAGES_DIR.parent
    / "specs" / "012-run-transparency" / "contracts" / "normalized-event.schema.json"
)


def assert_event_valid(evt: dict) -> None:
    """Validate one normalized event against normalized-event.schema.json (required keys, the
    kind enum, per-kind conditionals, numeric null-not-bool). Dependency-free."""
    schema = json.load(open(EVENT_SCHEMA_PATH))
    for req in schema["required"]:
        assert req in evt, f"missing required key {req}"
    assert evt["kind"] in schema["properties"]["kind"]["enum"], evt["kind"]
    assert isinstance(evt["turn"], int) and evt["turn"] >= 0
    assert isinstance(evt["ts"], str) and evt["ts"]
    if evt["kind"] == "tool_call":
        assert "tool" in evt and isinstance(evt.get("args"), dict)
    if evt["kind"] in ("system", "user", "assistant", "final", "error"):
        assert isinstance(evt.get("text"), str)
    for k in ("tokens_in", "tokens_out"):
        if evt.get(k) is not None:
            assert isinstance(evt[k], int) and not isinstance(evt[k], bool)


@pytest.fixture
def event_validator():
    """Expose :func:`assert_event_valid` as a fixture for to_events() tests."""
    return assert_event_valid
