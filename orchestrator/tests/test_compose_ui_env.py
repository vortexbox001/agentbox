"""The UI service receives its browser-facing Dagster URL without loading .env (spec 010 follow-up).

Two distinct Dagster URLs (ui/config.py): ``DAGSTER_URL`` is the internal, container-to-container
address the UI calls server-side (reload/status); ``DAGSTER_PUBLIC_URL`` is the browser-facing base
for the links the UI renders. The UI must receive ``DAGSTER_PUBLIC_URL`` (and ``DAGSTER_LOCATION``)
threaded from the host env — never via ``env_file: .env``, which would hand the config-editing UI
every API-key secret in ``.env``. Regression guard for the gap where a custom public Dagster URL
set in ``.env`` never reached the UI container at all.
"""
import os

import yaml

COMPOSE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml"))


def _ui() -> dict:
    with open(COMPOSE, encoding="utf-8") as f:
        return yaml.safe_load(f)["services"]["ui"]


def _env(svc: dict) -> dict:
    """Service environment as a dict, accepting both compose forms (mapping or ``K=V`` list)."""
    env = svc.get("environment", {})
    if isinstance(env, list):
        out = {}
        for item in env:
            k, _, v = item.partition("=")
            out[k] = v
        return out
    return env


def test_ui_receives_public_dagster_url():
    env = _env(_ui())
    assert "DAGSTER_PUBLIC_URL" in env, "UI service does not receive DAGSTER_PUBLIC_URL"
    assert "${DAGSTER_PUBLIC_URL" in str(env["DAGSTER_PUBLIC_URL"]), (
        "DAGSTER_PUBLIC_URL must be threaded from the host env so it can be set in .env"
    )


def test_ui_also_receives_dagster_location():
    env = _env(_ui())
    assert "${DAGSTER_LOCATION" in str(env.get("DAGSTER_LOCATION", "")), (
        "UI job-link paths need DAGSTER_LOCATION threaded from the host env"
    )


def test_ui_internal_url_stays_the_service_address():
    # The browser URL is a separate var; DAGSTER_URL must remain the internal service address.
    assert _env(_ui()).get("DAGSTER_URL") == "http://dagster-webserver:3000"


def test_ui_does_not_load_env_file_secrets():
    # The UI is a config editor; pulling the whole .env via env_file would hand it every API key.
    assert "env_file" not in _ui(), (
        "UI service must not use env_file: .env (keeps API-key secrets out of the UI); "
        "thread the specific non-secret vars it needs into environment: instead"
    )
