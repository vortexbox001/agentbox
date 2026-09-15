"""Browser-facing Dagster base URL composition (bug: dagster-link-base-url).

``public_dagster_url`` must yield a URL a browser can actually open: a real scheme and
the host-published Dagster port (DAGSTER_HOST_PORT), whether the operator sets
DAGSTER_PUBLIC_URL to a bare host, a host with an explicit port, or leaves it blank.
"""
from types import SimpleNamespace

import pytest

import config
import main


def _req(url: str):
    """A stand-in Request exposing only the ``.url`` attributes public_dagster_url reads."""
    from urllib.parse import urlparse

    p = urlparse(url)
    return SimpleNamespace(url=SimpleNamespace(hostname=p.hostname, scheme=p.scheme))


# --- explicit DAGSTER_PUBLIC_URL ---------------------------------------------

def test_bare_host_gets_host_port_appended(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "http://10.0.0.100")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("http://10.0.0.100:8000/")) == "http://10.0.0.100:3000"


def test_explicit_port_in_public_url_is_preserved(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "https://dagster.example.com:9999")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("http://x/")) == "https://dagster.example.com:9999"


def test_non_default_host_port_is_honored(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "http://10.0.0.100")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3001")
    assert main.public_dagster_url(_req("http://x/")) == "http://10.0.0.100:3001"


def test_doubled_scheme_typo_is_normalized(monkeypatch):
    # The exact malformed value that triggered the bug report.
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "http://http://10.0.0.100")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("http://x/")) == "http://10.0.0.100:3000"


def test_missing_scheme_defaults_to_http(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "10.0.0.100")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("http://x/")) == "http://10.0.0.100:3000"


def test_trailing_slash_is_stripped(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "http://10.0.0.100/")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("http://x/")) == "http://10.0.0.100:3000"


# --- derive-from-request fallback (blank DAGSTER_PUBLIC_URL) ------------------

def test_derive_uses_host_port_not_internal_port(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3001")
    # Internal DAGSTER_URL still points at container port 3000; the link must not use it.
    monkeypatch.setattr(config, "DAGSTER_URL", "http://dagster-webserver:3000")
    assert main.public_dagster_url(_req("http://10.0.0.100:8000/")) == "http://10.0.0.100:3001"


def test_derive_keeps_request_scheme_and_host(monkeypatch):
    monkeypatch.setattr(config, "DAGSTER_PUBLIC_URL", "")
    monkeypatch.setattr(config, "DAGSTER_HOST_PORT", "3000")
    assert main.public_dagster_url(_req("https://box.local:8000/")) == "https://box.local:3000"
