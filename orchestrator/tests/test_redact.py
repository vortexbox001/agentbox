"""Redaction tests (spec 012, T009 — contracts/redaction.md).

Three parts:
  1. per-kind coverage + idempotence of ``orchestrator/redact.py``;
  2. a shared-fixture PARITY test pinning ``redact.secret_kind_for`` against
     ``ui/secret_scan.is_secret_like`` (the two run in separate containers, no shared import);
  3. an end-to-end capture test that writes a fixture run directory seeded with a fake secret,
     ``grep -r``'s the whole directory, and asserts no cleartext hit while the value survives
     only as ``[REDACTED:<kind>]`` (FR-016 / SC-004).
"""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

import redact

# orchestrator/tests/ -> orchestrator/ -> repo root -> ui/secret_scan.py
SECRET_SCAN_PATH = Path(__file__).resolve().parents[2] / "ui" / "secret_scan.py"


def _load_secret_scan():
    spec = importlib.util.spec_from_file_location("ui_secret_scan_parity", SECRET_SCAN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- 1. per-kind coverage + idempotence --------------------------------------

@pytest.mark.parametrize("value,kind", [
    ("sk-ant-FAKEKEY0001abcXYZ", "api_key"),
    ("sk-FAKEOPENAIKEY0001xyz", "api_key"),
    ("ghp_FAKEGITHUBTOKEN0001xy", "token"),
    ("github_pat_FAKE0001abcXYZ0", "token"),
    ("xoxb-FAKE-SLACK-000111222", "token"),
    ("AKIAFAKEACCESSKEYID01", "credential"),
    ("AIzaFAKEGOOGLEKEY0001xyz", "api_key"),
])
def test_prefix_kinds_are_redacted(value, kind):
    out = redact.redact(f"the key is {value} ok")
    assert value not in out
    assert f"[REDACTED:{kind}]" in out


def test_github_project_token_shape_is_masked(monkeypatch):
    """Defence in depth for the board token (spec 016 US6, FR-017): a GITHUB_PROJECT_TOKEN-shaped
    value is masked by redaction wherever it might appear, and the NAME rule masks the pair too."""
    for val in ("github_pat_11ABCDE0000fakevalue1234567890", "ghp_FAKEprojecttoken0001xyz"):
        assert "[REDACTED:token]" in redact.redact(f"tried {val} on the board")
    # a NAME=value pair keyed by the token's variable name is masked via the *TOKEN* name rule
    assert redact.redact("GITHUB_PROJECT_TOKEN=github_pat_secretvalue00") == \
        "GITHUB_PROJECT_TOKEN=[REDACTED:token]"
    # and the env-pair classifier reports the kind for the pair (parity with is_secret_like)
    assert redact.secret_kind_for("GITHUB_PROJECT_TOKEN", "github_pat_x") == "token"


def test_private_key_block_redacted_whole():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEabc\ndefLINE2\n-----END RSA PRIVATE KEY-----"
    out = redact.redact(f"key:\n{pem}\ndone")
    assert "MIIEabc" not in out
    assert "[REDACTED:private_key]" in out
    assert out.startswith("key:") and out.endswith("done")


def test_name_value_uses_the_name_kind():
    assert redact.redact("PASSWORD=hunterlongvalue2") == "PASSWORD=[REDACTED:password]"
    assert redact.redact("DB_SECRET: swordfishlongvalue3") == "DB_SECRET: [REDACTED:secret]"


def test_bare_high_entropy_is_NOT_redacted():
    # Decision (spec 012): no blanket high-entropy pass over free text. A high-entropy blob with
    # no recognizable prefix / NAME=value shape is left intact (it is almost always an opaque id,
    # not a secret — e.g. claude-code message/request/tool_use ids and thinking signatures).
    val = "dGhpc19pc19hX3ZlcnlfbG9uZ19pZDEyMzQ1Njc4OTA="
    assert redact.redact(f"blob {val} end") == f"blob {val} end"


def test_ordinary_prose_is_untouched():
    text = "The task-force reviewed the orchestrator and wrote a summary to /output."
    assert redact.redact(text) == text


def test_compact_json_structure_survives():
    # claude-code stream-json is space-free compact JSON packed with opaque ids/signatures. None
    # of it is a secret, so the whole line must survive untouched (the over-redaction the dropped
    # high-entropy pass caused). A prefixed secret embedded in it is still caught.
    line = ('{"type":"assistant","message":{"id":"msg_01AbCdEfGhIjKlMnOpQrStUv",'
            '"content":[{"type":"thinking","signature":"AQ4pT2xkc2lnbmF0dXJlYmxvYg=="}]}}')
    assert redact.redact(line) == line  # opaque ids/signatures are not secrets → untouched
    embedded = '{"type":"result","token":"sk-ant-FAKEKEY0001abcXYZ","ok":true}'
    out = redact.redact(embedded)
    assert "sk-ant-FAKEKEY0001abcXYZ" not in out
    assert out.startswith('{"type":"result","token":"[REDACTED:api_key]"')
    assert out.endswith('"ok":true}')


def test_claude_ids_preserved():
    # the concrete false positives that motivated dropping the pass
    for tok in ("msg_01WxYz9AbCdEfGhIjKlMnOpQ", "toolu_01AbCdEfGhIjKlMnOpQrSt",
                "req_011CabcDEF1234567890xyz", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"):
        assert redact.redact(f'"id":"{tok}"') == f'"id":"{tok}"'


def test_idempotent():
    text = "api key sk-ant-FAKEKEY0001abcXYZ and PASSWORD=hunterlongvalue2 here"
    once = redact.redact(text)
    twice = redact.redact(once)
    assert once == twice
    assert "sk-ant-FAKEKEY0001abcXYZ" not in once
    assert "[REDACTED:api_key]" in once and "[REDACTED:password]" in once


def test_redact_obj_recurses_every_string():
    obj = {"prompt": "use sk-ant-FAKEKEY0001abcXYZ", "nested": {"tool_result": "PASSWORD=longsecretval9"},
           "list": ["ghp_FAKEGITHUBTOKEN0001xy", 5, None]}
    out = redact.redact_obj(obj)
    flat = json.dumps(out)
    assert "sk-ant-FAKEKEY0001abcXYZ" not in flat
    assert "ghp_FAKEGITHUBTOKEN0001xy" not in flat
    assert "longsecretval9" not in flat
    assert out["list"][1] == 5 and out["list"][2] is None  # non-strings untouched


# --- 2. shared-fixture parity with ui/secret_scan ----------------------------

PARITY_PAIRS = [
    ("OPENAI_API_KEY", "sk-ant-FAKEKEY0001abcXYZ"),
    ("GITHUB_TOKEN", "ghp_FAKEGITHUBTOKEN0001xy"),
    ("DB_PASSWORD", "swordfish"),
    ("SOME_SECRET", "x"),
    ("PLAIN_VALUE", "hello"),
    ("MODEL", "claude-sonnet-5"),
    ("PASSTHRU", "${HOST_VAR}"),
    ("RANDOM_BLOB", "Zx9$Kp2!Lq7#Mv4@Nb8&aa"),
    ("AWS_KEY", "AKIAFAKEACCESSKEYID01"),
    ("NOTES", "a short note"),
]


@pytest.mark.parametrize("name,value", PARITY_PAIRS)
def test_parity_flagging_agrees_with_secret_scan(name, value):
    ss = _load_secret_scan()
    flagged = ss.is_secret_like(name, value)
    kind = redact.secret_kind_for(name, value)
    assert flagged == (kind is not None), (
        f"disagreement on {name}={value!r}: secret_scan={flagged} redact_kind={kind}"
    )


def test_parity_high_entropy_rule_matches():
    ss = _load_secret_scan()
    for v in ("Zx9$Kp2!Lq7#Mv4@Nb8&aa", "short", "alllowercaselettersonlyxx", "abc"):
        assert ss._high_entropy(v) == redact._high_entropy(v), v


# --- 3. end-to-end capture directory grep guarantee (SC-004) -----------------

def test_capture_directory_has_no_cleartext_secret(tmp_path, monkeypatch):
    """Seed a run directory through run_capture with a fake secret in every captured file,
    then grep the whole directory: the value must survive only as ``[REDACTED:...]`` (SC-004)."""
    import paths
    import run_capture

    monkeypatch.setattr(paths, "RUNS_ROOT", str(tmp_path / "runs"))
    fake = "sk-ant-FAKEKEY0001abcXYZ"

    rd = run_capture.RunCapture(agent="hello", date="2026-09-15", run_id="run-1")
    rd.create()
    # context with a secret in the prompt + an instruction file
    context = {
        "prompt": {"prompt_text": f"use {fake} to authenticate", "append_system_prompt": None},
        "model": {"model": "smart"},
        "harness": {"harness": "pi", "image_ref": "agentbox/agent-pi:latest", "image_digest": "sha256:x"},
        "tools": {},
        "instruction_files": [{"path": "/workspace/AGENTS.md", "contents": f"key: {fake}"}],
        "runtime": {"env_names": ["OPENAI_API_KEY"], "mounts": [], "network": "agentnet", "working_dir": "/workspace"},
        "file_trees": {"workspace": [], "output": []},
        "completeness": {"complete": True, "undisclosed": [], "statement": "complete"},
    }
    rd.write_context(context)
    # transcript lines carrying the secret
    rd.write_transcript_lines([
        json.dumps({"type": "assistant", "text": f"I will use {fake}"}) + "\n",
        json.dumps({"type": "result", "text": "done"}) + "\n",
    ])
    # events staged then moved+redacted
    staging = tmp_path / "staging"
    staging.mkdir()
    events_src = staging / "events.jsonl"
    events_src.write_text(json.dumps({"kind": "tool_result", "ts": "t", "turn": 1,
                                      "result": f"secret={fake}"}) + "\n")
    rd.ingest_events(str(events_src))
    rd.write_report({"status": "ok", "notes": None, "transcript_path": None})

    # grep the whole run directory for the raw secret — must find nothing.
    proc = subprocess.run(["grep", "-r", fake, rd.dir], capture_output=True, text=True)
    assert proc.returncode != 0, f"cleartext secret found:\n{proc.stdout}"
    # and it survives as a redaction marker in the events/context
    ctx = (Path(rd.dir) / "context.json").read_text()
    assert "[REDACTED:api_key]" in ctx
