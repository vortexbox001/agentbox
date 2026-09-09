"""Secret-like env value detection (FR-020 / research R7).

A plain (non-``${NAME}``) environment value is flagged when its name looks like a
secret's or its value looks like a credential. The server returns 409 for flagged
keys unless the user confirms they are not secrets; the heuristic leans strict
because a false positive costs one confirmation while a false negative leaks.
This module (agentbox: secret_scan) is mirrored by ``agent-form.js`` for instant client-side feedback.
"""
from __future__ import annotations

import re

# ${NAME} passthrough: forwards a host variable by name, never exposing a value.
_PASSTHROUGH_RE = re.compile(r"^\$\{\w+\}$")

# Name substrings that mark a variable as holding a secret.
_NAME_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_KEY|CREDENTIAL|AUTH)",
    re.IGNORECASE,
)

# Value prefixes of well-known credential formats.
_VALUE_PREFIXES = (
    "sk-ant-", "sk-", "ghp_", "github_pat_", "gho_",
    "xoxa-", "xoxb-", "xoxp-", "AKIA", "AIza", "-----BEGIN",
)


def is_passthrough(value) -> bool:
    """True when the value is a ``${NAME}`` reference (never flagged)."""
    return isinstance(value, str) and bool(_PASSTHROUGH_RE.match(value))


def _high_entropy(value: str) -> bool:
    """>= 20 chars, no whitespace, at least three of {lower, upper, digit, symbol}."""
    if len(value) < 20 or any(c.isspace() for c in value):
        return False
    classes = 0
    classes += any(c.islower() for c in value)
    classes += any(c.isupper() for c in value)
    classes += any(c.isdigit() for c in value)
    classes += any((not c.isalnum()) and (not c.isspace()) for c in value)
    return classes >= 3


def is_secret_like(name: str, value) -> bool:
    """Whether a name/value pair should be flagged for secret confirmation."""
    if is_passthrough(value):
        return False
    if _NAME_RE.search(str(name)):
        return True
    if not isinstance(value, str):
        return False
    if value.startswith(_VALUE_PREFIXES):
        return True
    return _high_entropy(value)


def flagged_keys(env: dict) -> list[str]:
    """The env keys whose plain values look secret-like, in the map's order."""
    if not isinstance(env, dict):
        return []
    return [k for k, v in env.items() if is_secret_like(k, v)]
