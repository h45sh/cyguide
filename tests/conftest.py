"""Pytest configuration and global canonical fixtures for CyGuide."""

from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import pytest

# Ensure Hypothesis persists its database and caches strictly inside tests/.hypothesis
try:
    import hypothesis.configuration

    hypothesis.configuration.set_hypothesis_home_dir(Path(__file__).parent / ".hypothesis")
except ImportError:
    pass

from cyguide.engine.execution_session import CommandRunner
from cyguide.engine.explainer import ExplainerBackend
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost


@pytest.fixture(autouse=True)
def isolate_cyguide_data_dir(tmp_path, monkeypatch):
    """Automatically isolate all tests to an isolated temporary CYGUIDE_DATA_DIR.

    This ensures test runs never alter or pollute the user's real ~/.cyguide directory.
    """
    test_data_dir = str(tmp_path / ".cyguide_test")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", test_data_dir)
    return test_data_dir


@pytest.fixture
async def in_memory_store() -> AsyncIterator[GraphStore]:
    """Provide an initialized in-memory GraphStore with automatic closing."""
    store = GraphStore(":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


class FastMockExplainer(ExplainerBackend):
    """A deterministic mock explainer that streams tokens without hitting Ollama or network."""

    def __init__(self, response: str = "Mock explanation: scan analyzed."):
        self.response = response

    async def explain(self, prompt: str) -> AsyncIterator[str]:
        words = self.response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    async def explain_scan(
        self,
        question: str,
        scan_output: str = None,
        tool_name: str = None,
        findings_summary: str = None,
    ) -> AsyncIterator[str]:
        yield f"Analysis for {tool_name or 'tool'}: {self.response}"


@pytest.fixture
def mock_explainer() -> FastMockExplainer:
    """Fixture providing an instant mock explainer."""
    return FastMockExplainer()


class FakeCommandRunner(CommandRunner):
    """In-memory command runner simulating execution without real subprocesses."""

    def __init__(self, stdout_lines: List[str] = None):
        self.stdout_lines = stdout_lines or ["Starting scan...", "Host is up (0.001s latency)."]
        self.killed = False

    async def run(
        self,
        cmd: List[str],
        env: Dict[str, str],
        cwd: str,
        on_chunk: Any,
        is_shell: bool = False,
    ) -> int:
        for line in self.stdout_lines:
            await on_chunk(line + "\n")
        return 0

    async def kill(self) -> None:
        self.killed = True


@pytest.fixture
def fake_command_runner() -> FakeCommandRunner:
    """Fixture providing a fast in-memory command runner."""
    return FakeCommandRunner()


@pytest.fixture
def sample_host() -> NetworkHost:
    """Standard NetworkHost finding fixture."""
    return NetworkHost.create(ip="10.20.30.40")
