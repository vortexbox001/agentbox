"""Tests for the secret-like detection heuristic (FR-020 / research R7)."""
import pytest

import secret_scan as sec


@pytest.mark.parametrize("name,value,flagged", [
    # FR-020 reference cases
    ("GITHUB_USER", "leeclemmer", False),
    ("MY_TOKEN", "abc123", True),                          # flagged by name
    ("REPO", "sk-live-a1B2c3D4e5F6g7H8i9J0", True),        # flagged by value prefix
    ("GITHUB_TOKEN", "${GITHUB_TOKEN}", False),            # passthrough never flagged
    # name-based
    ("API_KEY", "short", True),
    ("APIKEY", "short", True),
    ("DB_PASSWORD", "x", True),
    ("MY_SECRET", "x", True),
    ("SERVICE_CREDENTIAL", "x", True),
    ("AUTH_HEADER", "x", True),
    # value prefixes
    ("X", "ghp_0123456789abcdef", True),
    ("X", "github_pat_11ABCDEF", True),
    ("X", "xoxb-123-456-abc", True),
    ("X", "AKIAIOSFODNN7EXAMPLE", True),
    ("X", "AIzaSyD-abc123", True),
    ("X", "-----BEGIN PRIVATE KEY-----", True),
    # entropy: >=20 chars, no whitespace, >=3 classes
    ("X", "aB3$aB3$aB3$aB3$aB3$", True),
    ("X", "alllowercaseletters!!", False),                 # only 2 classes
    ("X", "short1A!", False),                              # too short
    ("X", "has space in it 1A!!!!", False),                # whitespace
    # passthrough forms never flagged even with secret-like name
    ("SECRET_TOKEN", "${SECRET_TOKEN}", False),
    # plain harmless value
    ("GITHUB_REPONAME", "agentbox", False),
])
def test_is_secret_like(name, value, flagged):
    assert sec.is_secret_like(name, value) is flagged


def test_is_passthrough():
    assert sec.is_passthrough("${FOO}")
    assert not sec.is_passthrough("$FOO")
    assert not sec.is_passthrough("literal")


def test_flagged_keys_preserves_order():
    env = {"GITHUB_USER": "leeclemmer", "GITHUB_TOKEN": "ghp_abcdefghij", "PLAIN": "x"}
    assert sec.flagged_keys(env) == ["GITHUB_TOKEN"]


def test_flagged_keys_non_dict():
    assert sec.flagged_keys(None) == []
