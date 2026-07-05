import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.schemas.network import NetworkHost

@pytest.mark.asyncio
async def test_facade_get_context_resolution():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()
    
    facade = PowerWorkspaceFacade(store, executor, registry)
    
    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")
    
    # 1. Create a node
    host = NetworkHost.create(ip="10.0.0.5")
    node_id = await store.upsert_finding(sess_id, host)
    
    # 2. Get context with selected node
    ctx = await facade.get_context(sess_id, node_id)
    
    assert ctx.session_name == "Session"
    assert ctx.resolved_vars["TARGET"] == "10.0.0.5"
    assert ctx.entity_counts["network.host"] == 1
    
    await store.close()

@pytest.mark.asyncio
async def test_facade_submit_action_validation():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()
    
    # Mock registry to return a tool that accepts network.host
    manifest = MagicMock()
    manifest.meta.name = "nmap"
    manifest.input.get.return_value = ["network.host"]
    registry.get_tool.return_value = {"adapter": MagicMock(), "manifest": manifest}
    
    facade = PowerWorkspaceFacade(store, executor, registry)
    
    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")
    host = NetworkHost.create(ip="10.0.0.5")
    node_id = await store.upsert_finding(sess_id, host)
    
    action = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        target_entity_id=node_id,
        triggered_by=ActionSource.USER
    )
    
    # This should pass validation and start a background task
    job_id = await facade.submit_action(action)
    assert job_id == action.action_id
    assert job_id in facade._active_jobs
    
    await store.close()
