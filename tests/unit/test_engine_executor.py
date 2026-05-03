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

@pytest.mark.asyncio
async def test_executor_milestones():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = Executor(store)
    
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockNmapAdapter()
    
    milestones = []
    async def on_milestone(trigger, data):
        milestones.append(trigger)
        
    async for _ in executor.run_tool(adapter, target, {}, session_id=session_id, on_milestone=on_milestone):
        pass
        
    assert "first_service" in milestones
    assert "scan_complete" in milestones
    await store.close()
