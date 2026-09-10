"""Shared pytest fixtures for the orchestrator (factory/definitions) test suite.

The orchestrator modules (``factory``, ``definitions``) are the Dagster code
location: inside the container they are imported by bare name (``from factory
import ...``), so the code-location directory — ``orchestrator/`` — is put on
``sys.path`` here rather than the repo root, matching how Dagster loads them.

The ``stub_launch`` fixture monkeypatches the single container-launch call in
``factory.py`` (``subprocess.run``) so ``make_run_op`` / ``build_asset`` and, via
them, ``definitions`` can be materialized in-process without ``docker run``. It
also redirects the transcript root at ``factory.AGENT_LOG_ROOT`` into a temp dir
so an op body can run end-to-end without writing to ``/data``.
"""
import subprocess
import sys
from pathlib import Path

import pytest

# orchestrator/tests/conftest.py -> orchestrator/ (the Dagster code location).
ORCHESTRATOR_DIR = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_DIR) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_DIR))


class LaunchStub:
    """Controller for the stubbed container launch.

    Tests set ``returncode`` / ``stdout`` / ``stderr`` before materializing to
    shape the fake result, and read ``calls`` afterwards to assert on the exact
    ``docker run`` argv the op *would* have launched (the last one via ``cmd``).
    """

    def __init__(self):
        self.calls: list[list[str]] = []
        self.returncode = 0
        self.stdout = ""
        self.stderr = ""

    def __call__(self, cmd, *args, **kwargs):
        # record the launch and return a canned result instead of spawning docker
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(
            cmd, self.returncode, stdout=self.stdout, stderr=self.stderr
        )

    @property
    def cmd(self) -> list[str]:
        """The argv of the most recent launch (convenience for single-launch tests)."""
        return self.calls[-1]


@pytest.fixture
def stub_launch(monkeypatch, tmp_path):
    """Replace ``factory.subprocess.run`` so ops run without launching a container.

    Yields a :class:`LaunchStub`; also points ``factory.AGENT_LOG_ROOT`` at a temp
    directory so the op's transcript write succeeds under test.
    """
    import factory

    stub = LaunchStub()
    monkeypatch.setattr(factory.subprocess, "run", stub)
    monkeypatch.setattr(factory, "AGENT_LOG_ROOT", str(tmp_path / "agent-logs"))
    return stub
