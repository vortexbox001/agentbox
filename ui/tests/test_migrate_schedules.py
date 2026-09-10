"""Test the one-off scripts/migrate-schedules.py over a fixture repo (US2).

Verifies: every agent file's `schedule:` line is stripped and its stamp bumped to 3;
non-template agents' crons land in automation/migrated.yaml; templates and manual-only
agents contribute no entry; a second run changes nothing (SC-001/SC-002).
"""
import importlib.util
import os
import textwrap

import pytest
import yaml

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "migrate-schedules.py",
)


def _load_script(repo_root):
    spec = importlib.util.spec_from_file_location("migrate_schedules", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Point the module at the fixture repo instead of the real one.
    mod.REPO_ROOT = str(repo_root)
    mod.AGENTS_DIR = str(repo_root / "agents")
    mod.AUTOMATION_DIR = str(repo_root / "automation")
    mod.MIGRATED = str(repo_root / "automation" / "migrated.yaml")
    return mod


AGENT_WITH_CRON = """\
# agentbox-schema: 2
name: repo-librarian-agentbox
enabled: true
harness: api
model: cheap
prompt_file: x.md
output_dir: /data/outputs/repo-librarian/agentbox
schedule: "30 2 * * *"          # eg "0 7 * * *"
network: agentnet
"""

AGENT_MANUAL = """\
# agentbox-schema: 2
name: repo-librarian-haiku
enabled: true
harness: api
model: cheap
prompt_file: x.md
output_dir: /data/outputs/repo-librarian/haiku
schedule: ""                    # manual-only
network: agentnet
"""

TEMPLATE = """\
# agentbox-schema: 2
name: my-agent
enabled: false
harness: api
model: cheap
prompt_file: x.md
output_dir: /data/outputs/my-agent
schedule: "0 7 * * *"           # cron expression, or "" for manual-only runs
network: agentnet
"""

# A hand-written file with NO schema stamp — the migration must ADD one (Option B).
NO_STAMP = """\
# A hand-written agent with no schema stamp.
name: hand-written
enabled: true
harness: api
model: cheap
prompt_file: x.md
output_dir: /data/outputs/hand-written
schedule: "15 3 * * *"
network: agentnet
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "automation").mkdir()
    (tmp_path / "agents" / "repo-librarian-agentbox.yaml").write_text(textwrap.dedent(AGENT_WITH_CRON))
    (tmp_path / "agents" / "repo-librarian-haiku.yaml").write_text(textwrap.dedent(AGENT_MANUAL))
    (tmp_path / "agents" / "_template-api.yaml").write_text(textwrap.dedent(TEMPLATE))
    (tmp_path / "agents" / "hand-written.yaml").write_text(textwrap.dedent(NO_STAMP))
    return tmp_path


def test_migration_strips_and_writes_entries(repo):
    mod = _load_script(repo)
    assert mod.main() == 0

    # Every agent file: no `schedule` key, stamp bumped to 3.
    for p in (repo / "agents").glob("*.yaml"):
        text = p.read_text()
        assert "schedule:" not in text, p.name
        assert "# agentbox-schema: 3" in text, p.name

    # A stampless hand-written file gets a schema-3 stamp ADDED (Option B).
    assert (repo / "agents" / "hand-written.yaml").read_text().startswith("# agentbox-schema: 3")

    # migrated.yaml: every non-template, non-empty-schedule agent has a cron entry.
    entries = yaml.safe_load((repo / "automation" / "migrated.yaml").read_text())
    assert entries == {
        "repo-librarian-agentbox": {"cron": "30 2 * * *"},
        "hand-written": {"cron": "15 3 * * *"},
    }


def test_migration_is_idempotent(repo):
    mod = _load_script(repo)
    mod.main()
    snapshot = {p.name: p.read_text() for p in (repo / "agents").glob("*.yaml")}
    snapshot["migrated"] = (repo / "automation" / "migrated.yaml").read_text()

    mod2 = _load_script(repo)
    mod2.main()
    after = {p.name: p.read_text() for p in (repo / "agents").glob("*.yaml")}
    after["migrated"] = (repo / "automation" / "migrated.yaml").read_text()

    assert after == snapshot  # second run changed nothing


def test_template_and_manual_produce_no_entry(repo):
    mod = _load_script(repo)
    mod.main()
    entries = yaml.safe_load((repo / "automation" / "migrated.yaml").read_text())
    assert "my-agent" not in entries          # template excluded (FR-012)
    assert "repo-librarian-haiku" not in entries  # manual-only -> on-demand, no entry
