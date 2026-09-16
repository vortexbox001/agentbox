"""Tests for orchestrator/governors.py — the settings.yaml governors reader (spec 013 US5).

``load_governors`` returns the file's values, falling back per-key to ``DEFAULT_GOVERNORS`` when the
file, the ``governors`` block, or a single key is absent or invalid. Twin of ui/settings_store; the
defaults are pinned across packages by test_paths_parity.
"""
import textwrap

import governors


def _write(tmp_path, body):
    p = tmp_path / "settings.yaml"
    p.write_text(textwrap.dedent(body))
    return str(p)


def test_defaults_are_12_and_5():
    assert governors.DEFAULT_GOVERNORS == {"max_runs_per_hour": 12, "max_chain_depth": 5}


def test_reads_values_from_file(tmp_path):
    path = _write(tmp_path, """\
        governors:
          max_runs_per_hour: 3
          max_chain_depth: 2
    """)
    assert governors.load_governors(path) == {"max_runs_per_hour": 3, "max_chain_depth": 2}


def test_missing_file_falls_back_to_defaults(tmp_path):
    assert governors.load_governors(str(tmp_path / "nope.yaml")) == governors.DEFAULT_GOVERNORS


def test_absent_block_falls_back(tmp_path):
    path = _write(tmp_path, "retention:\n  mode: keep_forever\n")
    assert governors.load_governors(path) == governors.DEFAULT_GOVERNORS


def test_per_key_fallback_when_partial_or_invalid(tmp_path):
    path = _write(tmp_path, """\
        governors:
          max_runs_per_hour: 7
          max_chain_depth: 0
    """)
    # max_chain_depth 0 is invalid → default 5; max_runs_per_hour 7 kept
    assert governors.load_governors(path) == {"max_runs_per_hour": 7, "max_chain_depth": 5}


def test_non_int_and_bool_values_fall_back(tmp_path):
    path = _write(tmp_path, """\
        governors:
          max_runs_per_hour: "lots"
          max_chain_depth: true
    """)
    assert governors.load_governors(path) == governors.DEFAULT_GOVERNORS


def test_malformed_yaml_falls_back(tmp_path):
    path = _write(tmp_path, "governors: [unclosed\n")
    assert governors.load_governors(path) == governors.DEFAULT_GOVERNORS
