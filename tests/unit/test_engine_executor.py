import pytest
from cyguide.engine.executor import Executor
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost
from tests.fixtures.mock_tools import MockNmapAdapter

@pytest.mark.asyncio
async def test_executor_run_tool():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = Executor(store)

    # Satisfy foreign key constraints
    ws_id, session_id = await store.get_or_create_learning_sandbox()

    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockNmapAdapter()

    findings = []
    async for f in executor.run_tool(adapter, target, {}, session_id=session_id):
        findings.append(f)

    assert len(findings) == 1
    assert findings[0].schema_type == "network.service"
    assert findings[0].pik["host_ip"] == "127.0.0.1"

    # Verify it was persisted to store
    stats = await store.get_stats(session_id)
    assert stats["network.service"] == 1
    await store.close()


class MockHangingAdapter(MockNmapAdapter):
    def build_command(self, target, params):
        return ["sleep", "5"]

    async def parse_output(self, raw_stdout, target, context=None):
        if False:
            yield


@pytest.mark.asyncio
async def test_executor_timeout():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = Executor(store)
    ws_id, session_id = await store.get_or_create_learning_sandbox()

    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockHangingAdapter()

    output_lines = []
    async def record_output(text):
        output_lines.append(text)

    with pytest.raises(TimeoutError):
        async for _ in executor.run_tool(
            adapter, target, {},
            session_id=session_id,
            timeout_seconds=0.2,
            on_output=record_output
        ):
            pass

    assert any("TIMEOUT" in line for line in output_lines)
    await store.close()
