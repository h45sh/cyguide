import asyncio
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
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
        if self.fail_with:
            if on_error_output:
                await on_error_output(self.fail_with)
            raise RuntimeError(self.fail_with)

        for chunk in self.output_chunks:
            if on_output:
                await on_output(chunk)
            await asyncio.sleep(0.01)

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
