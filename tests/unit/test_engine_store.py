import pytest
import aiosqlite
import json
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.power import ActionRequest, ActionSource
from uuid import uuid4

@pytest.mark.asyncio
async def test_structured_event_log():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")
    
    action = ActionRequest(
        session_id=uuid4(), # different just for payload test
        tool_name="nmap",
        target_entity_id="test_node",
        params={"f": "v"}
    )
    
    await store.append_event(sess_id, action, {"status": "ok"}, "Ran nmap")
    
    events = await store.get_event_log(sess_id)
    assert len(events) == 1
    assert events[0]["human_readable"] == "Ran nmap"
    assert "nmap" in events[0]["action_payload"]
    assert json.loads(events[0]["result_payload"]) == {"status": "ok"}
    
    await store.close()

@pytest.mark.asyncio
async def test_store_initialization():
    store = GraphStore(":memory:")
    await store.initialize()
    
    async with store._get_conn() as db:
        # Check if tables exist
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in await cursor.fetchall()]
        assert "workspaces" in tables
        assert "sessions" in tables
        assert "nodes" in tables
        assert "edges" in tables
        assert "event_log" in tables
    await store.close()

@pytest.mark.asyncio
async def test_learning_sandbox_creation():
    store = GraphStore(":memory:")
    await store.initialize()
    
    ws_id, sess_id = await store.get_or_create_learning_sandbox()
    assert ws_id is not None
    assert sess_id is not None
    
    # Run again, should return the same IDs
    ws_id2, sess_id2 = await store.get_or_create_learning_sandbox()
    assert ws_id == ws_id2
    assert sess_id == sess_id2
    await store.close()

@pytest.mark.asyncio
async def test_upsert_and_query_finding():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, sess_id = await store.get_or_create_learning_sandbox()
    
    host = NetworkHost.create(ip="127.0.0.1", hostname="localhost")
    node_id = await store.upsert_finding(sess_id, host)
    
    results = await store.query("network.host", session_id=sess_id)
    assert len(results) == 1
    assert results[0]["id"] == node_id
    assert json.loads(results[0]["pik_json"]) == {"ip": "127.0.0.1"}
    await store.close()

@pytest.mark.asyncio
async def test_graph_wiring_parent():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, sess_id = await store.get_or_create_learning_sandbox()
    
    # Upsert a service (which has a parent NetworkHost)
    service = NetworkService.create(host_ip="10.0.0.1", port=443, protocol="tcp")
    await store.upsert_finding(sess_id, service)
    
    # Should have created two nodes: the service AND the host
    stats = await store.get_stats(sess_id)
    assert stats["network.service"] == 1
    assert stats["network.host"] == 1
    
    # Should have created one edge
    async with store._get_conn() as db:
        cursor = await db.execute("SELECT count(*) FROM edges WHERE session_id = ?", (sess_id,))
        count = (await cursor.fetchone())[0]
        assert count == 1
    await store.close()
