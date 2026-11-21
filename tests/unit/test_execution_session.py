from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.execution_session import (
    ExecutionChunk,
    ExecutionCompleted,
    ExecutionSession,
)
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest, ActionSource, JobStatusEnum


class FakeInMemoryRunner:
    """In-memory CommandRunner for hermetic testing without OS processes."""

    def __init__(self, output_chunks: Optional[List[str]] = None, fail_with: Optional[str] = None):
        self.output_chunks = output_chunks or ["Discovered host 10.0.0.1\n", "Port 80 OPEN\n"]
        self.fail_with = fail_with
        self.stopped_tasks: List[str] = []
        self.executed_calls: List[Dict[str, Any]] = []

    async def run(
        self,
        adapter: ToolAdapter,
        target: BaseFinding,
        params: Dict[str, Any],
        task_id: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        use_shell: bool = False,
        shell_path: Optional[str] = None,
        on_output: Optional[Callable[[str], Any]] = None,
        on_error_output: Optional[Callable[[str], Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[BaseFinding]:
        self.executed_calls.append(
            {
                "adapter": adapter,
                "target": target,
                "params": params,
                "task_id": task_id,
                "use_shell": use_shell,
            }
        )
        if self.fail_with:
            if on_error_output:
                await on_error_output(self.fail_with)
            raise RuntimeError(self.fail_with)

        for chunk in self.output_chunks:
            if on_output:
                await on_output(chunk)

        # Emit finding
        yield BaseFinding(
            schema_type="network.host",
            pik={"ip": "10.0.0.1"},
            data={"status": "up"},
            status="confirmed",
        )

    async def stop(self, task_id: str) -> None:
        self.stopped_tasks.append(task_id)


class RecordingSuspendContext:
    def __init__(self):
        self.suspended = False
        self.resumed = False

    from contextlib import contextmanager

    @contextmanager
    def suspend(self):
        self.suspended = True
        try:
            yield
        finally:
            self.resumed = True


@pytest.mark.asyncio
async def test_execution_session_dispatch_and_events():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner()
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)

    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="nmap",
        params={"raw_flags": "-p 80 10.0.0.1"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    chunks_received = []
    completed_called = False

    async def on_chunk(text: str):
        chunks_received.append(text)

    async def on_complete():
        nonlocal completed_called
        completed_called = True

    # Dispatch action
    job_id = await session.dispatch(
        action,
        on_chunk=on_chunk,
        on_complete=on_complete,
    )
    assert job_id == action.action_id

    # Wait for completion
    task = session.get_running_task(job_id)
    if task:
        await task

    assert completed_called is True
    assert len(chunks_received) == 2
    assert "Discovered host 10.0.0.1\n" in chunks_received

    # Verify history buffer
    history = session.get_output_history(job_id)
    assert len(history) == 2

    # Verify job status
    job = session.get_job(job_id)
    assert job is not None
    assert job.status == JobStatusEnum.DONE

    await store.close()


@pytest.mark.asyncio
async def test_execution_session_typed_subscription():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner(output_chunks=["Line 1\n", "Line 2\n"])
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)

    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="whois",
        params={"raw_flags": "example.com"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    await session.dispatch(action)

    # Subscribe to typed events
    events = []
    async for ev in session.subscribe(action.action_id):
        events.append(ev)

    types = [type(e) for e in events]
    assert ExecutionChunk in types
    assert ExecutionCompleted in types

    await store.close()


@pytest.mark.asyncio
async def test_execution_session_kill_job():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner()
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)

    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="nmap",
        params={"raw_flags": "-sV 10.0.0.1"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    job_id = await session.dispatch(action)
    killed = await session.kill_job(job_id)
    assert killed is True
    assert str(job_id) in runner.stopped_tasks

    await store.close()


@pytest.mark.asyncio
async def test_privileged_action_cached_credentials_no_suspend():
    """When sudo credentials are authenticated (sudo -n true succeeds), TUI is not suspended."""
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner(output_chunks=["uid=0(root) gid=0(root)\n"])
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)
    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )
    suspend_ctx = RecordingSuspendContext()

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="sudo",
        params={"raw_flags": "whoami"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    chunks_received = []

    async def on_chunk(t: str):
        chunks_received.append(t)

    with (
        patch("shutil.which", return_value="/usr/bin/sudo"),
        patch("subprocess.run") as mock_subproc,
    ):
        mock_subproc.return_value = MagicMock(returncode=0)

        job_id = await session.dispatch(action, suspend_context=suspend_ctx, on_chunk=on_chunk)
        task = session.get_running_task(job_id)
        if task:
            await task

    # TUI was NOT suspended because credentials were already cached
    assert suspend_ctx.suspended is False
    assert len(runner.executed_calls) == 1
    call_params = runner.executed_calls[0]["params"]["raw_flags"]
    assert call_params == "sudo whoami"
    assert any("uid=0(root)" in c for c in chunks_received)

    job = session.get_job(job_id)
    assert job.status == JobStatusEnum.DONE
    await store.close()


@pytest.mark.asyncio
async def test_privileged_action_prompt_and_resume_stream():
    """When sudo credentials are expired (sudo -n true fails), TUI suspends for sudo -v, then resumes and streams."""
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner(output_chunks=["Nmap scan report for 10.0.0.1\n", "Port 22 OPEN\n"])
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)
    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )
    suspend_ctx = RecordingSuspendContext()

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="sudo",
        params={"raw_flags": "nmap -sS 10.0.0.1"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    chunks_received = []

    async def on_chunk(t: str):
        chunks_received.append(t)

    def fake_subprocess_run(cmd, **kwargs):
        if cmd == ["sudo", "-n", "true"]:
            return MagicMock(returncode=1)  # Needs auth!
        elif cmd == ["sudo", "-v"]:
            return MagicMock(returncode=0)  # Sudo -v authenticated successfully
        return MagicMock(returncode=0)

    with (
        patch("shutil.which", return_value="/usr/bin/sudo"),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        job_id = await session.dispatch(action, suspend_context=suspend_ctx, on_chunk=on_chunk)
        task = session.get_running_task(job_id)
        if task:
            await task

    # TUI was suspended for authentication, then resumed
    assert suspend_ctx.suspended is True
    assert suspend_ctx.resumed is True

    # Output chunks were streamed into on_chunk!
    assert any("Authentication required" in c for c in chunks_received)
    assert any("Sudo credentials validated" in c for c in chunks_received)
    assert any("Nmap scan report" in c for c in chunks_received)

    assert len(runner.executed_calls) == 1
    assert runner.executed_calls[0]["params"]["raw_flags"] == "sudo nmap -sS 10.0.0.1"

    job = session.get_job(job_id)
    assert job.status == JobStatusEnum.DONE
    await store.close()


@pytest.mark.asyncio
async def test_privileged_action_auth_failure():
    """When sudo password prompt fails or is cancelled, execution stops and job fails."""
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner()
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)
    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )
    suspend_ctx = RecordingSuspendContext()

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="sudo",
        params={"raw_flags": "whoami"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    chunks_received = []

    async def on_chunk(t: str):
        chunks_received.append(t)

    def fake_subprocess_run(cmd, **kwargs):
        if cmd == ["sudo", "-n", "true"]:
            return MagicMock(returncode=1)
        elif cmd == ["sudo", "-v"]:
            return MagicMock(returncode=1)  # Auth cancelled or incorrect password
        return MagicMock(returncode=0)

    with (
        patch("shutil.which", return_value="/usr/bin/sudo"),
        patch("subprocess.run", side_effect=fake_subprocess_run),
    ):
        job_id = await session.dispatch(action, suspend_context=suspend_ctx, on_chunk=on_chunk)
        task = session.get_running_task(job_id)
        if task:
            await task

    assert suspend_ctx.suspended is True
    # Command was NEVER executed via runner
    assert len(runner.executed_calls) == 0

    job = session.get_job(job_id)
    assert job.status == JobStatusEnum.FAILED
    assert any("Sudo authentication failed" in c for c in chunks_received)
    await store.close()


@pytest.mark.asyncio
async def test_privileged_action_deduplicates_sudo_flags():
    """Redundant sudo prefixes (!sudo sudo whoami) are safely deduplicated to a single sudo invocation."""
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner(output_chunks=["root\n"])
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)
    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="sudo",
        params={"raw_flags": "sudo whoami"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    with (
        patch("shutil.which", return_value="/usr/bin/sudo"),
        patch("subprocess.run", return_value=MagicMock(returncode=0)),
    ):
        job_id = await session.dispatch(action)
        task = session.get_running_task(job_id)
        if task:
            await task

    assert len(runner.executed_calls) == 1
    assert runner.executed_calls[0]["params"]["raw_flags"] == "sudo whoami"
    await store.close()


@pytest.mark.asyncio
async def test_privileged_action_missing_sudo_binary():
    """When sudo is not installed on PATH, job cleanly fails."""
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    runner = FakeInMemoryRunner()
    registry = ToolRegistry()
    gateway = ActionGateway(registry, store)
    session = ExecutionSession(
        store=store,
        gateway=gateway,
        registry=registry,
        command_runner=runner,
    )

    action = ActionRequest(
        action_id=uuid4(),
        session_id=UUID(sess_id),
        tool_name="sudo",
        params={"raw_flags": "whoami"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
    )

    chunks_received = []

    async def on_chunk(t: str):
        chunks_received.append(t)

    with patch("shutil.which", return_value=None):
        job_id = await session.dispatch(action, on_chunk=on_chunk)
        task = session.get_running_task(job_id)
        if task:
            await task

    job = session.get_job(job_id)
    assert job.status == JobStatusEnum.FAILED
    assert any("'sudo' binary not found" in c for c in chunks_received)
    await store.close()
