"""Settings store + page tests (spec 012, T065)."""
import pytest

from test_runs import write_run


def test_read_retention_default_when_absent(settings):
    import settings_store
    assert settings_store.read_retention() == {"mode": "keep_forever", "days": None}


def test_write_retention_preserves_unknown_keys(settings, tmp_settings_file):
    import settings_store
    tmp_settings_file.write_text("schema_version: 1\nfuture_section:\n  a: 1\n")
    settings_store.write_retention("prune_after_days", 14)
    import yaml
    doc = yaml.safe_load(tmp_settings_file.read_text())
    assert doc["retention"] == {"mode": "prune_after_days", "days": 14}
    # unknown keys survive the write (contracts/settings.md)
    assert doc["schema_version"] == 1
    assert doc["future_section"] == {"a": 1}
    assert settings_store.read_retention() == {"mode": "prune_after_days", "days": 14}


def test_validate_retention_rejects_bad_policy(settings):
    import settings_store
    with pytest.raises(settings_store.RetentionError):
        settings_store.write_retention("nonsense", None)
    with pytest.raises(settings_store.RetentionError):
        settings_store.write_retention("prune_after_days", 0)
    with pytest.raises(settings_store.RetentionError):
        settings_store.write_retention("prune_after_days", None)


def test_keep_forever_drops_days(settings):
    import settings_store
    settings_store.write_retention("prune_after_days", 5)
    settings_store.write_retention("keep_forever", None)
    assert settings_store.read_retention() == {"mode": "keep_forever", "days": None}


def test_settings_page_renders(settings, client):
    html = client.get("/settings").text
    assert "Run retention" in html
    assert "ax-retention-form" in html
    assert "prune_after_days" in html


def test_api_retention_persists(settings, client, tmp_settings_file):
    r = client.post("/api/settings/retention", json={"mode": "prune_after_days", "days": 30})
    assert r.status_code == 200
    assert r.json()["retention"] == {"mode": "prune_after_days", "days": 30}
    import settings_store
    assert settings_store.read_retention()["days"] == 30


def test_api_retention_rejects_invalid(settings, client):
    r = client.post("/api/settings/retention", json={"mode": "prune_after_days"})
    assert r.status_code == 400


# ── Governors (spec 013 US5, contract ui-settings-and-form §5) ──
def test_read_governors_default_when_absent(settings):
    import settings_store
    assert settings_store.read_governors() == {"max_runs_per_hour": 12, "max_chain_depth": 5}


def test_validate_governors_rejects_non_int_non_positive_over_cap(settings):
    import settings_store
    with pytest.raises(settings_store.GovernorError):
        settings_store.validate_governors("lots", 5)
    with pytest.raises(settings_store.GovernorError):
        settings_store.validate_governors(0, 5)
    with pytest.raises(settings_store.GovernorError):
        settings_store.validate_governors(True, 5)          # bool is not a valid int
    with pytest.raises(settings_store.GovernorError):
        settings_store.validate_governors(12, 100000)        # over the sane cap


def test_write_governors_preserves_retention_and_unknown_keys(settings, tmp_settings_file):
    import settings_store
    import yaml
    settings_store.write_retention("prune_after_days", 14)
    tmp_settings_file.write_text(tmp_settings_file.read_text() + "future_section:\n  a: 1\n")
    settings_store.write_governors(3, 2)
    doc = yaml.safe_load(tmp_settings_file.read_text())
    assert doc["governors"] == {"max_runs_per_hour": 3, "max_chain_depth": 2}
    assert doc["retention"] == {"mode": "prune_after_days", "days": 14}
    assert doc["future_section"] == {"a": 1}
    assert settings_store.read_governors() == {"max_runs_per_hour": 3, "max_chain_depth": 2}


def test_api_governors_round_trips(settings, client, tmp_settings_file):
    r = client.post("/api/settings/governors", json={"max_runs_per_hour": 6, "max_chain_depth": 4})
    assert r.status_code == 200
    assert r.json()["governors"] == {"max_runs_per_hour": 6, "max_chain_depth": 4}
    import settings_store
    assert settings_store.read_governors() == {"max_runs_per_hour": 6, "max_chain_depth": 4}


def test_api_governors_rejects_invalid(settings, client):
    assert client.post("/api/settings/governors",
                       json={"max_runs_per_hour": 0, "max_chain_depth": 5}).status_code == 400
    assert client.post("/api/settings/governors",
                       json={"max_runs_per_hour": 12, "max_chain_depth": "deep"}).status_code == 400


def test_settings_page_renders_governors_card(settings, client):
    html = client.get("/settings").text
    assert "Run governors" in html
    assert "ax-governors-card" in html and "ax-governors-form" in html


def test_pruned_run_renders_note(settings, tmp_runs, client):
    # a run whose events/transcript were pruned still opens with a "conversation pruned" note (SC-006)
    write_run(tmp_runs, "hello", "2026-09-15", "pruned-run",
              report={"status": "ok"}, context={"harness": {"harness": "api"}})  # no events/transcript
    html = client.get("/runs/pruned-run").text
    assert "Conversation pruned" in html
