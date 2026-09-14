"""Test the one-off scripts/migrate-automation-to-triggers.py over a fixture repo (US2).

Verifies: an asset-mode agent's 005 cron lands on ``triggers.asset_schedule``; a job-mode
agent's cron lands on ``triggers.job_schedule`` (and sets ``job: true``); every touched file is
re-stamped schema 4; ``automation/`` is removed; a second run is a no-op; a named agent with no
file is skipped, not fatal (contract orchestrator-model §7).
"""
import importlib.util
import os
import textwrap

import pytest
import yaml

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "migrate-automation-to-triggers.py",
)


def _load_script(repo_root):
    spec = importlib.util.spec_from_file_location("migrate_automation_to_triggers", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = str(repo_root)
    mod.AGENTS_DIR = str(repo_root / "agents")
    mod.AUTOMATION_DIR = str(repo_root / "automation")
    mod.MIGRATED = str(repo_root / "automation" / "migrated.yaml")
    return mod


ASSET_AGENT = """\
# agentbox-schema: 3
name: list-commits-pi-kimi
enabled: true
harness: pi
model: kimi
prompt_file: repo-librarian.md
output_dir: /data/outputs/list-commits
network: agentnet
produces:
  asset: repo-review/list-commits
  partition: daily
"""

JOB_AGENT = """\
# agentbox-schema: 3
name: categorize-commits
enabled: false
harness: pi
model: kimi
prompt_file: repo-librarian.md
output_dir: /data/outputs/categorize-commits
network: agentnet
"""

MIGRATED = """\
categorize-commits:
  cron: 30 2 * * *
list-commits-pi-kimi:
  cron: 20 17 * * *
ghost-agent:
  cron: 0 0 * * *
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "automation").mkdir()
    (tmp_path / "agents" / "list-commits-pi-kimi.yaml").write_text(textwrap.dedent(ASSET_AGENT))
    (tmp_path / "agents" / "categorize-commits.yaml").write_text(textwrap.dedent(JOB_AGENT))
    (tmp_path / "automation" / "migrated.yaml").write_text(textwrap.dedent(MIGRATED))
    return tmp_path


def test_carry_over_writes_per_kind_and_removes_automation(repo, capsys):
    mod = _load_script(repo)
    assert mod.main() == 0

    # Asset-mode agent: cron on triggers.asset_schedule, current schema, no job flag.
    asset = yaml.safe_load((repo / "agents" / "list-commits-pi-kimi.yaml").read_text())
    assert asset["triggers"] == {"asset_schedule": "20 17 * * *"}
    assert "job" not in asset
    assert "# agentbox-schema: 6" in (repo / "agents" / "list-commits-pi-kimi.yaml").read_text()

    # Job-mode agent: cron on triggers.job_schedule + job: true, current schema.
    job = yaml.safe_load((repo / "agents" / "categorize-commits.yaml").read_text())
    assert job["triggers"] == {"job_schedule": "30 2 * * *"}
    assert job["job"] is True
    assert "# agentbox-schema: 6" in (repo / "agents" / "categorize-commits.yaml").read_text()

    # automation/ is gone; the unknown agent was reported and skipped.
    assert not (repo / "automation").exists()
    assert "ghost-agent" in capsys.readouterr().err


def test_migration_is_idempotent(repo):
    mod = _load_script(repo)
    mod.main()
    snapshot = {p.name: p.read_text() for p in (repo / "agents").glob("*.yaml")}

    mod2 = _load_script(repo)
    assert mod2.main() == 0  # automation/ already gone → nothing to do
    after = {p.name: p.read_text() for p in (repo / "agents").glob("*.yaml")}
    assert after == snapshot  # second run changed nothing
    assert not (repo / "automation").exists()
