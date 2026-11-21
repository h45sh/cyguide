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
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.power import ActionRequest, ActionSource, JobStatusEnum

pytestmark = [pytest.mark.fast, pytest.mark.asyncio]


class HighVolumeStressRunner:
    """CommandRunner that streams thousands of lines and emits findings concurrently."""

    def __init__(self, line_count: int = 10_000, findings_per_job: int = 5):
        self.line_count = line_count
        self.findings_per_job = findings_per_job
        self.stopped_tasks: List[str] = []
        self._task_indices: Dict[str, int] = {}
        self._counter: int = 0

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
        # Stream chunks in batches to simulate realistic high-throughput PTY bursts
        batch_size = 200
        for i in range(0, self.line_count, batch_size):
            for j in range(i, min(i + batch_size, self.line_count)):
                if on_output:
                    await on_output(f"[{task_id[:8]}] log line {j:06d}: payload flood data...\n")
            # Yield control to event loop to allow concurrent jobs and subscriber tasks to interleave
            await asyncio.sleep(0)  # codeguard: disable[TEST_FLAKY_SLEEP]

        # Emit findings with guaranteed unique IPs per task
        if task_id not in self._task_indices:
            self._counter += 1
            self._task_indices[task_id] = self._counter
        idx = self._task_indices[task_id]

        for f_idx in range(self.findings_per_job):
            yield NetworkHost.create(ip=f"10.{idx}.{f_idx + 1}.1")

    async def stop(self, task_id: str) -> None:
        self.stopped_tasks.append(task_id)


async def test_high_volume_stream_bounding_and_concurrency():
    """Verify O(1) in-memory buffer bounding and zero event loop deadlocks

    under high volume concurrent execution.
    """
    store = GraphStore(":memory:")
    await store.initialize()
    try:
        ws_id = await store.create_workspace("StressWS")
        sess_id = await store.create_session(ws_id, "StressSess")

        # 5 concurrent jobs each emitting 8,000 lines (40,000 lines total)
        lines_per_job = 8_000
        findings_per_job = 4
        num_jobs = 5

        runner = HighVolumeStressRunner(line_count=lines_per_job, findings_per_job=findings_per_job)
        registry = ToolRegistry()
        gateway = ActionGateway(registry, store)

        session = ExecutionSession(
            store=store,
            gateway=gateway,
            registry=registry,
            command_runner=runner,
        )

        job_ids: List[UUID] = []
        action_tasks = []

        # Dispatch 5 jobs concurrently
        for i in range(num_jobs):
            action = ActionRequest(
                action_id=uuid4(),
                session_id=UUID(sess_id),
                tool_name="nmap",
                params={"raw_flags": f"-sV 10.0.{i}.1"},
                triggered_by=ActionSource.USER,
                is_explicit_shell=True,
            )
            job_id = await session.dispatch(action)
            job_ids.append(job_id)
            task = session.get_running_task(job_id)
            assert task is not None
            action_tasks.append(task)

        # Wait for all concurrent streaming tasks to complete without deadlocking
        await asyncio.gather(*action_tasks)

        # Assertions
        for j_id in job_ids:
            job = session.get_job(j_id)
            assert job is not None
            assert job.status == JobStatusEnum.DONE

            # Verify O(1) ring-buffer bounding:
            # Although 8,000 lines were emitted, buffer caps at 5,000 and retains latest 2,500
            buf = session.get_output_history(j_id)
            assert len(buf) <= 5000, f"Job buffer exceeded 5000 lines: {len(buf)}"
            assert len(buf) >= 2500, f"Job buffer unexpectedly lost too many lines: {len(buf)}"
            # Verify latest lines are present
            assert f"log line {lines_per_job - 1:06d}" in buf[-1]

        # Verify all findings from all concurrent jobs were flushed to store
        nodes = await store.get_all_nodes(sess_id)
        assert len(nodes) == num_jobs * findings_per_job

    finally:
        await store.close()


async def test_live_subscriber_backpressure_and_interleaving():
    """Verify live subscriber receives chunks without deadlocks while stream floods."""
    store = GraphStore(":memory:")
    await store.initialize()
    try:
        ws_id = await store.create_workspace("SubWS")
        sess_id = await store.create_session(ws_id, "SubSess")

        runner = HighVolumeStressRunner(line_count=4_000, findings_per_job=2)
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

        received_chunks = []
        subscriber_completed = False

        async def subscriber():
            nonlocal subscriber_completed
            async for event in session.subscribe(action.action_id):
                if isinstance(event, ExecutionChunk):
                    received_chunks.append(event.text)
                elif isinstance(event, ExecutionCompleted):
                    subscriber_completed = True

        # Start job
        job_id = await session.dispatch(action)

        # Start subscriber concurrently
        sub_task = asyncio.create_task(subscriber())

        # Wait for action task
        job_task = session.get_running_task(job_id)
        assert job_task is not None
        await job_task

        # Wait for subscriber task
        await asyncio.wait_for(sub_task, timeout=5.0)

        assert subscriber_completed is True
        # Subscriber gets streamed chunks
        assert len(received_chunks) == 4_000
        assert f"log line {3_999:06d}" in received_chunks[-1]

    finally:
        await store.close()
