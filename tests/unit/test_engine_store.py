import pytest
import aiosqlite
import json
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService

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
