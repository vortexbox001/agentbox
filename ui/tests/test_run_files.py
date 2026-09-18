"""Files + Report tab tests (spec 012, T050). Path-safety of the file API is asserted here."""
import json

import pytest

from test_runs import write_run


@pytest.fixture
def run_with_outputs(tmp_runs, tmp_path):
    """A run whose context points at an output dir holding one of its artifacts (by session id)."""
    out = tmp_path / "outputs" / "hello"
    out.mkdir(parents=True)
    sid = "sess-1234"
    (out / f"2026-09-15_10-00_report_{sid}.md").write_text("# Upgrade report\nAll good.")
    (out / f"2026-09-15_10-00_data_{sid}.bin").write_bytes(b"\x00\x01binary")
    (out / "unrelated_other-session.md").write_text("not this run")
    write_run(
        tmp_runs, "hello", "2026-09-15", "run-out",
        report={"status": "ok", "files_written": 2, "notes": "Wrote the **report**.", "error": None,
                "tokens_in": 10, "tokens_out": 5, "turns": 1, "cost_usd": 0.001},
        context={"harness": {"harness": "claude-code"}, "model": {"model": "m"},
                 "run": {"session_id": sid, "output_dir": str(out)}},
    )
    return sid


def test_files_tab_lists_run_artifacts(settings, run_with_outputs, client):
    html = client.get("/runs/run-out").text
    assert "ax-file-row" in html
    assert f"2026-09-15_10-00_report_{run_with_outputs}.md" in html
    # a different run's output is not listed (matched by session id)
    assert "unrelated_other-session.md" not in html


def test_file_api_previews_text(settings, run_with_outputs, client):
    name = f"2026-09-15_10-00_report_{run_with_outputs}.md"
    r = client.get(f"/api/runs/run-out/files/{name}")
    assert r.status_code == 200
    assert "Upgrade report" in r.text


def test_file_api_download(settings, run_with_outputs, client):
    name = f"2026-09-15_10-00_report_{run_with_outputs}.md"
    r = client.get(f"/api/runs/run-out/files/{name}?download=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")


def test_file_api_rejects_traversal(settings, run_with_outputs, client):
    # a traversal / unrelated file is refused (path-safe, FR-019a)
    assert client.get("/api/runs/run-out/files/..%2f..%2fetc%2fpasswd").status_code == 404
    assert client.get("/api/runs/run-out/files/unrelated_other-session.md").status_code == 404


def test_report_tab_renders_fields_and_notes(settings, run_with_outputs, client):
    html = client.get("/runs/run-out").text
    # spec 017 US3: the final-message notes now render in the Summary section as the markdown
    # subset (bold → <strong>), no longer as the rail's ax-report-notes block (FR-006/US3-AC4).
    assert "ax-report-notes" not in html
    assert "ax-summary" in html
    assert "<strong>report</strong>" in html   # **report** rendered, not raw markup
    assert "Files written" in html             # Usage still carries the numeric fields
