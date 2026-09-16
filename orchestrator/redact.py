"""Shared secret redaction for the run directory (spec 012, contracts/redaction.md).

``redact(text) -> text`` replaces every secret-like token in ``text`` with
``[REDACTED:<kind>]`` and leaves everything else unchanged. It is idempotent (running it
twice is a no-op). The orchestrator runs it as the single pass over ``transcript.jsonl``,
``events.jsonl``, and ``context.json`` before they land in the run directory, so a search of
the whole directory finds no cleartext secret (FR-013..016 / SC-004).

Free-text redaction uses the RELIABLE detectors only: known credential value-prefixes
(``sk-ant-``, ``ghp_``, ``xox…``, ``AKIA``, …), ``NAME=secret`` pairs, and PEM private-key
blocks. There is deliberately **no** blanket high-entropy pass over free text — on a code-agent
transcript it was almost entirely false positives (claude-code's own message / request /
tool_use ids and "thinking" signatures are high-entropy but not secrets), and env values, the
primary secret vector, are never written to disk at all (FR-015). The high-entropy rule is kept
only for env-value classification (``secret_kind_for``), which stays pinned to
``ui/secret_scan.is_secret_like`` by the shared-fixture parity test (the UI still flags a
high-entropy env value at authoring time). The two modules run in separate containers with no
shared import, exactly as ``ASSET_KEY_RE`` and the ``paths.py``↔``config.py`` constants are.
"""
from __future__ import annotations

import re

# --- Detection primitives (mirrored from ui/secret_scan.py; parity-tested) ---

# ${NAME} passthrough: forwards a host variable by name, never a value → never a secret.
_PASSTHROUGH_RE = re.compile(r"^\$\{\w+\}$")

# Name substrings that mark a variable as holding a secret, mapped to the reported kind.
# Order matters: the first matching pattern wins (most specific first).
_NAME_KINDS = (
    (re.compile(r"PRIVATE_KEY", re.IGNORECASE), "private_key"),
    (re.compile(r"API_?KEY", re.IGNORECASE), "api_key"),
    (re.compile(r"PASSWORD|PASSWD", re.IGNORECASE), "password"),
    (re.compile(r"TOKEN|AUTH", re.IGNORECASE), "token"),
    (re.compile(r"CREDENTIAL", re.IGNORECASE), "credential"),
    (re.compile(r"SECRET", re.IGNORECASE), "secret"),
)
# The combined name test (matches ui/secret_scan._NAME_RE), used by the parity twin.
_NAME_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_KEY|CREDENTIAL|AUTH)", re.IGNORECASE
)

# Well-known credential value prefixes → kind. Longest/most-specific first so `sk-ant-`
# classifies as api_key before the generic `sk-`.
_PREFIX_KINDS = (
    ("sk-ant-", "api_key"),
    ("github_pat_", "token"),
    ("ghp_", "token"),
    ("gho_", "token"),
    ("xoxa-", "token"),
    ("xoxb-", "token"),
    ("xoxp-", "token"),
    ("sk-", "api_key"),
    ("AKIA", "credential"),
    ("AIza", "api_key"),
)
# The prefix tuple in ui/secret_scan order, for the parity twin's startswith test.
_VALUE_PREFIXES = (
    "sk-ant-", "sk-", "ghp_", "github_pat_", "gho_",
    "xoxa-", "xoxb-", "xoxp-", "AKIA", "AIza", "-----BEGIN",
)

# A PEM/private-key block, redacted whole (multi-line).
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.DOTALL
)
# A lone BEGIN header with no matching END (truncated capture) — still a private key.
_PRIVATE_KEY_HEADER = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

# NAME = value / NAME: value where NAME looks secret-like (redact the value with the name's kind).
# `pre` captures the name + separator + surrounding whitespace verbatim so it is re-emitted intact.
_NAME_VALUE = re.compile(
    r"(?P<pre>(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*)"
    r"(?P<q>[\"']?)(?P<val>[^\s\"']+)(?P=q)"
)

# A value-prefix run: a known prefix at a token boundary followed by a credential body.
_PREFIX_RUN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-ant-|github_pat_|ghp_|gho_|xoxa-|xoxb-|xoxp-|sk-|AKIA|AIza)"
    r"[A-Za-z0-9_\-./+=]{4,}"
)

_PLACEHOLDER = "[REDACTED:"


def is_passthrough(value: str) -> bool:
    """True when the value is a ``${NAME}`` reference (never a secret)."""
    return isinstance(value, str) and bool(_PASSTHROUGH_RE.match(value))


def _high_entropy(value: str) -> bool:
    """>= 20 chars, no whitespace, at least three of {lower, upper, digit, symbol}.

    Identical rule to ui/secret_scan._high_entropy (parity-tested)."""
    if len(value) < 20 or any(c.isspace() for c in value):
        return False
    classes = 0
    classes += any(c.islower() for c in value)
    classes += any(c.isupper() for c in value)
    classes += any(c.isdigit() for c in value)
    classes += any((not c.isalnum()) and (not c.isspace()) for c in value)
    return classes >= 3


def _name_kind(name: str) -> str:
    for pat, kind in _NAME_KINDS:
        if pat.search(name):
            return kind
    return "secret"


def _prefix_kind(value: str) -> str | None:
    for prefix, kind in _PREFIX_KINDS:
        if value.startswith(prefix):
            return kind
    return None


def secret_kind_for(name: str, value) -> str | None:
    """The kind a name/value env pair would be redacted as, or ``None`` if not secret-like.

    The env-pair twin of ``ui/secret_scan.is_secret_like`` — same decision, but returning the
    reported ``<kind>``. Pinned to ``secret_scan.is_secret_like`` by the parity test: this is
    non-None for exactly the pairs ``is_secret_like`` flags.
    """
    if is_passthrough(value):
        return None
    if _NAME_RE.search(str(name)):
        return _name_kind(str(name))
    if not isinstance(value, str):
        return None
    kind = _prefix_kind(value)
    if kind:
        return kind
    if value.startswith("-----BEGIN"):
        return "private_key"
    if _high_entropy(value):
        return "high_entropy"
    return None


def _placeholder(kind: str) -> str:
    return f"[REDACTED:{kind}]"


def _redact_prefix_run(m: re.Match) -> str:
    return _placeholder(_prefix_kind(m.group(0)) or "credential")


def _redact_name_value(m: re.Match) -> str:
    val = m.group("val")
    if _PLACEHOLDER in val:
        return m.group(0)  # already redacted — leave it (idempotence)
    if not _NAME_RE.search(m.group("name")):
        return m.group(0)  # ordinary key=value, not a secret name
    return f"{m.group('pre')}{m.group('q')}{_placeholder(_name_kind(m.group('name')))}{m.group('q')}"


def redact(text):
    """Replace every secret-like token in ``text`` with ``[REDACTED:<kind>]``. Idempotent.

    Non-str input is returned unchanged (so the caller can map it over mixed JSON values).
    """
    if not isinstance(text, str) or not text:
        return text
    # 1. Whole private-key blocks first (they contain newlines the token passes would mangle).
    text = _PRIVATE_KEY_BLOCK.sub(_placeholder("private_key"), text)
    text = _PRIVATE_KEY_HEADER.sub(_placeholder("private_key"), text)
    # 2. NAME=value / NAME: value with a secret-looking name → the name's kind.
    text = _NAME_VALUE.sub(_redact_name_value, text)
    # 3. Known value-prefix runs anywhere (embedded secrets, not only key=value).
    text = _PREFIX_RUN.sub(_redact_prefix_run, text)
    # NOTE: there is deliberately NO blanket high-entropy pass over free text. It was almost all
    # false positives on a code-agent transcript — claude-code's own message/request/tool_use ids
    # and "thinking" signatures are high-entropy but not secrets — and env values (the primary
    # secret vector) are never written to disk anyway (FR-015). Real credentials in prompts / tool
    # output carry a recognizable prefix or NAME=value shape, which the passes above catch.
    return text


def redact_obj(obj):
    """Recursively redact every string in a JSON-like structure (dict/list/str/scalar).

    Used for ``context.json`` and each event's fields (FR-014: tool results and every captured
    field, not only top-level messages). Dict keys are left unredacted (they are field names).
    """
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj
