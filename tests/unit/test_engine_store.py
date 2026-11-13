import json
from uuid import uuid4

import pytest

from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.power import ActionRequest


@pytest.mark.asyncio
async def test_structured_event_log():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")

    action = ActionRequest(
        session_id=uuid4(),  # different just for payload test
        tool_name="nmap",
        target_entity_id="test_node",
        params={"f": "v"},
    )

    await store.append_event(sess_id, action, {"status": "ok"}, "Ran nmap")

    events = await store.get_event_log(sess_id)
    assert len(events) == 1
    assert events[0]["human_readable"] == "Ran nmap"
    assert "nmap" in events[0]["action_payload"]
    assert json.loads(events[0]["result_payload"]) == {"status": "ok"}

    await store.close()


@pytest.mark.asyncio
async def test_mark_event_closed():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")

    action = ActionRequest(
        session_id=uuid4(), tool_name="nmap", target_entity_id="test_node", params={"f": "v"}
    )

    await store.append_event(sess_id, action, {"status": "ok"}, "Ran nmap")

    events = await store.get_event_log(sess_id)
    assert len(events) == 1

    # Initially 0 closed events
    assert await store.get_closed_events_count(sess_id) == 0

    # Mark it closed
    await store.mark_event_closed(str(action.action_id))

    # Ensure it is filtered out from get_event_log
    events_after = await store.get_event_log(sess_id)
    assert len(events_after) == 0

    # Ensure closed events count is 1
    assert await store.get_closed_events_count(sess_id) == 1

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


@pytest.mark.asyncio
async def test_auto_create_nonexistent_parent_dir(tmp_path):
    # Specify a path inside non-existent nested subdirectories
    nested_db = tmp_path / "deep" / "nested" / "dir" / "test.db"
    assert not nested_db.parent.exists()

    store = GraphStore(str(nested_db))
    await store.initialize()
    assert nested_db.parent.exists()
    assert nested_db.exists()
    await store.close()


@pytest.mark.asyncio
async def test_wal_mode_pragmas(tmp_path):
    db_file = tmp_path / "wal_test.db"
    store = GraphStore(str(db_file))
    await store.initialize()

    async with store._get_conn() as db:
        cursor = await db.execute("PRAGMA journal_mode")
        mode = (await cursor.fetchone())[0]
        assert mode.upper() == "WAL"

        cursor = await db.execute("PRAGMA busy_timeout")
        timeout = (await cursor.fetchone())[0]
        assert timeout == 5000

        cursor = await db.execute("PRAGMA synchronous")
        sync_mode = (await cursor.fetchone())[0]
        # NORMAL synchronous is 1
        assert sync_mode == 1

    await store.close()


@pytest.mark.asyncio
async def test_get_stats_by_workspace(tmp_path):
    db_file = tmp_path / "stats_ws.db"
    store = GraphStore(str(db_file))
    await store.initialize()

    ws1 = await store.create_workspace("WS1")
    ws2 = await store.create_workspace("WS2")

    sess1 = await store.create_session(ws1, "Sess1")
    sess2 = await store.create_session(ws2, "Sess2")

    svc1 = NetworkService.create(host_ip="192.168.1.10", port=80, protocol="tcp")
    await store.upsert_finding(sess1, svc1)

    svc2 = NetworkService.create(host_ip="10.0.0.1", port=443, protocol="tcp")
    await store.upsert_finding(sess2, svc2)

    stats_ws1 = await store.get_stats(workspace_id=ws1)
    stats_ws2 = await store.get_stats(workspace_id=ws2)
    stats_all = await store.get_stats()

    assert stats_ws1["network.service"] == 1
    assert stats_ws1["network.host"] == 1
    assert stats_ws1["total"] == 2

    assert stats_ws2["network.service"] == 1
    assert stats_ws2["network.host"] == 1
    assert stats_ws2["total"] == 2

    assert stats_all["network.service"] == 2
    assert stats_all["network.host"] == 2
    assert stats_all["total"] == 4

    await store.close()


@pytest.mark.asyncio
async def test_upsert_findings_batch(tmp_path):
    db_file = tmp_path / "batch_test.db"
    store = GraphStore(str(db_file))
    await store.initialize()

    ws_id = await store.create_workspace("BatchWS")
    sess_id = await store.create_session(ws_id, "BatchSess")

    findings = [
        NetworkService.create(host_ip="10.0.0.1", port=80, protocol="tcp"),
        NetworkService.create(host_ip="10.0.0.1", port=443, protocol="tcp"),
        NetworkService.create(host_ip="10.0.0.2", port=22, protocol="tcp"),
    ]

    callback_findings = []

    async def on_upsert_hook(s_id, finding):
        callback_findings.append((s_id, finding))

    store.on_upsert(on_upsert_hook)

    node_ids = await store.upsert_findings_batch(sess_id, findings)
    assert len(node_ids) == 3
    assert len(callback_findings) == 3

    # Check that services and parent hosts were created
    stats = await store.get_stats(sess_id)
    assert stats["network.service"] == 3
    assert stats["network.host"] == 2
    assert stats["total"] == 5

    await store.close()
