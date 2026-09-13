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

Since spec 007 the op reports itself over Dagster Pipes: after the (stubbed) launch
it reads the run report back via ``factory._extract_report``. With no real container
there is nothing to read, so the stub also patches ``factory._extract_report`` to
return the canned report a test drops on ``stub_launch.report`` (an ``ok`` report by
default, so existing success tests keep passing). Set ``stub_launch.report = None``
to exercise the orchestrator's missing-report fallback authoring. The real Pipes
round-trip is covered end-to-end by the quickstart (T022), not in-process.
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

    Since US3 the op launches via ``subprocess.Popen`` and drains stdout line by line,
    so this stubs ``factory.subprocess.Popen`` with a fake process whose stdout/stderr
    are ``self.stdout`` / ``self.stderr`` split into lines. ``factory.subprocess.run``
    stays stubbed too, for the timeout ``docker kill``. Tests set
    ``returncode`` / ``stdout`` / ``stderr`` / ``timeout`` before materializing and read
    ``calls`` afterwards; ``cmd`` returns the launched ``docker run`` argv.
    """

    class _FakeProc:
        """A minimal stand-in for a text-mode ``Popen`` process."""

        def __init__(self, stub, cmd):
            self._stub = stub
            self._cmd = cmd
            self.returncode = None
            # line iterators (keepends), exactly as text-mode Popen pipes yield
            self.stdout = iter(stub.stdout.splitlines(keepends=True))
            self.stderr = iter(stub.stderr.splitlines(keepends=True))

        def wait(self, timeout=None):
            # a timed wait raises once, driving the op's kill + fallback authoring;
            # the op's follow-up wait() (no timeout) then returns the code.
            if self._stub.timeout and timeout is not None:
                raise subprocess.TimeoutExpired(self._cmd, timeout)
            self.returncode = self._stub.returncode
            return self.returncode

    #: a valid, schema-shaped ``ok`` report returned in place of the container's
    #: Pipes report; a test may overwrite it (including with ``None`` to drop it).
    DEFAULT_REPORT = {
        "status": "ok",
        "tokens_in": 100,
        "tokens_out": 20,
        "turns": 2,
        "cost_usd": 0.0123,
        "files_written": 1,
        "transcript_path": None,  # the orchestrator fills this
        "error": None,
        "notes": "done; see /output.",
    }

    def __init__(self):
        self.calls: list[list[str]] = []
        self.returncode = 0
        self.stdout = ""
        self.stderr = ""
        self.report = dict(self.DEFAULT_REPORT)
        #: when True, the launch's ``wait(timeout=...)`` raises TimeoutExpired, exercising
        #: the op's timeout kill + fallback authoring. The follow-up ``docker kill`` (via
        #: the ``subprocess.run`` stub) still returns normally so the op can clean up.
        self.timeout = False
        #: Per-check outcomes for the check-container ``docker run``s (spec 008), in declared
        #: order: a list of dicts ``{"returncode": int, "stdout": str, "stderr": str}``. Missing
        #: entries (or missing keys) fall back to exit 0 / empty output, so a check passes by
        #: default. ``check_calls`` records each check-container argv in launch order.
        self.check_outcomes: list[dict] = []
        self.check_calls: list[list[str]] = []

    def popen(self, cmd, *args, **kwargs):
        # stand in for subprocess.Popen: record the launch, return a fake process
        self.calls.append(list(cmd))
        return LaunchStub._FakeProc(self, list(cmd))

    def __call__(self, cmd, *args, **kwargs):
        # stand in for subprocess.run. Two callers reach it: the producer's timeout
        # ``docker kill`` (``docker kill <name>``) and each check container (``docker run …``).
        self.calls.append(list(cmd))
        if list(cmd[:2]) == ["docker", "run"]:
            i = len(self.check_calls)
            self.check_calls.append(list(cmd))
            spec = self.check_outcomes[i] if i < len(self.check_outcomes) else {}
            return subprocess.CompletedProcess(
                cmd, spec.get("returncode", 0),
                stdout=spec.get("stdout", ""), stderr=spec.get("stderr", ""),
            )
        # a `docker kill` (or any other run) — succeed quietly.
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def extract_report(self, session, is_asset):
        """Stand in for ``factory._extract_report``: hand back the canned report
        (a fresh copy so the op may set ``transcript_path`` without mutating it)."""
        return None if self.report is None else dict(self.report)

    @property
    def cmd(self) -> list[str]:
        """The argv of the most recent container launch (the ``docker run``), ignoring
        any follow-up ``docker kill``."""
        for c in reversed(self.calls):
            if c[:2] == ["docker", "run"]:
                return c
        return self.calls[-1]

    @property
    def producer_cmd(self) -> list[str]:
        """The producer's launch argv — the FIRST ``docker run`` (the producer is Popen'd
        before any check container). Use this on a check-bearing materialize, where ``cmd``
        would otherwise return the last check container."""
        for c in self.calls:
            if c[:2] == ["docker", "run"]:
                return c
        return self.calls[0] if self.calls else []


@pytest.fixture
def stub_launch(monkeypatch, tmp_path):
    """Replace ``factory.subprocess.Popen`` (and ``.run``, for the timeout kill) so ops
    run without launching a container.

    Yields a :class:`LaunchStub`; also points ``factory.AGENT_LOG_ROOT`` at a temp
    directory so the op's transcript write succeeds under test.
    """
    import factory

    stub = LaunchStub()
    monkeypatch.setattr(factory.subprocess, "Popen", stub.popen)
    monkeypatch.setattr(factory.subprocess, "run", stub)  # only the timeout docker kill
    monkeypatch.setattr(factory, "_extract_report", stub.extract_report)
    monkeypatch.setattr(factory, "AGENT_LOG_ROOT", str(tmp_path / "agent-logs"))
    # PIPES_ROOT points at /data/dagster in production; redirect it into the temp dir so the
    # op's mkdtemp succeeds under test without writing to /data.
    monkeypatch.setattr(factory, "PIPES_ROOT", str(tmp_path / "pipes"))
    return stub
