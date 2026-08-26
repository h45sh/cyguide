import os
import pytest
import json
from uuid import uuid4
from cyguide.engine.store import GraphStore
from cyguide.engine.reporter import generate_markdown_report
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.power import ActionRequest, ActionSource

@pytest.mark.asyncio
async def test_report_generation(tmp_path):
    db_file = str(tmp_path / "test_cyguide.db")
    store = GraphStore(db_file)
    await store.initialize()
    
    ws_id = await store.create_workspace("Test Project")
    sess_id = await store.create_session(ws_id, "Test Session")
    
    # 1. Upsert a host node
    host = NetworkHost.create(ip="192.168.1.10")
    host.data["os"] = "Linux"
    await store.upsert_finding(sess_id, host)
    
    # 2. Append a tool execution event
    action = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        params={"raw_flags": "-sV 192.168.1.10"},
        triggered_by=ActionSource.USER
    )
    await store.append_event(
        sess_id,
        action,
        {"output": "Nmap scan completed successfully.", "error": None},
        "Ran nmap"
    )
    
    # Generate report
    report = await generate_markdown_report(store, sess_id)
    
    assert "CyGuide Investigation Report: Test Session" in report
    assert "Test Project" in report
    assert "192.168.1.10" in report
    assert "Linux" in report
    assert "nmap -sV 192.168.1.10" in report
    assert "Nmap scan completed successfully." in report
    
    await store.close()

@pytest.mark.asyncio
async def test_export_import_session(tmp_path):
    src_db_file = str(tmp_path / "src_cyguide.db")
    dest_db_file = str(tmp_path / "dest_cyguide.db")
    export_db_file = str(tmp_path / "export_session.db")
    
    # 1. Setup Source DB
    src_store = GraphStore(src_db_file)
    await src_store.initialize()
    
    ws_id = await src_store.create_workspace("Target Project")
    sess_id = await src_store.create_session(ws_id, "Target Session")
    
    # Insert findings
    host = NetworkHost.create(ip="10.10.10.10")
    await src_store.upsert_finding(sess_id, host)
    
    # Insert event log
    action = ActionRequest(
        session_id=sess_id,
        tool_name="gobuster",
        params={"raw_flags": "-u http://10.10.10.10"},
        triggered_by=ActionSource.USER
    )
    await src_store.append_event(
        sess_id,
        action,
        {"output": "Gobuster results.", "error": None},
        "Ran gobuster"
    )
    
    # 2. Export session
    await src_store.export_session(sess_id, export_db_file)
    assert os.path.exists(export_db_file)
    
    await src_store.close()
    
    # 3. Setup Destination DB & Import
    dest_store = GraphStore(dest_db_file)
    await dest_store.initialize()
    
    new_sess_id = await dest_store.import_session(export_db_file)
    assert new_sess_id is not None
    assert new_sess_id == sess_id  # Should preserve original session ID
    
    # Verify imported workspace exists
    workspaces = await dest_store.list_workspaces()
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Target Project"
    
    # Verify imported session exists
    sessions = await dest_store.list_sessions(workspaces[0]["id"])
    assert len(sessions) == 1
    assert sessions[0]["name"] == "Target Session"
    assert sessions[0]["id"] == new_sess_id
    
    # Verify nodes imported
    nodes = await dest_store.get_all_nodes(new_sess_id)
    assert len(nodes) == 1
    pik = json.loads(nodes[0]["pik_json"])
    assert pik["ip"] == "10.10.10.10"
    
    # Verify event_log imported
    events = await dest_store.get_event_log(new_sess_id)
    tool_events = [ev for ev in events if ev.get("schema_type") == "system.event"]
    assert len(tool_events) == 1
    action_payload = json.loads(tool_events[0]["action_payload"])
    assert action_payload["session_id"] == new_sess_id
    
    # Verify importing session again overwrites/restores it (count remains 1)
    duplicate_sess_id = await dest_store.import_session(export_db_file)
    assert duplicate_sess_id == new_sess_id
    sessions = await dest_store.list_sessions(workspaces[0]["id"])
    assert len(sessions) == 1
    
    # Verify importing a different session ID with the same name triggers collision rename
    # We alter the session ID in the exported DB to simulate a different session with the same name
    import aiosqlite
    async with aiosqlite.connect(export_db_file) as conn:
        new_uuid = str(uuid4())
        await conn.execute("UPDATE sessions SET id = ?", (new_uuid,))
        await conn.execute("UPDATE nodes SET session_id = ?", (new_uuid,))
        await conn.execute("UPDATE edges SET session_id = ?", (new_uuid,))
        await conn.execute("UPDATE event_log SET session_id = ?", (new_uuid,))
        await conn.commit()
        
    diff_sess_id = await dest_store.import_session(export_db_file)
    assert diff_sess_id == new_uuid
    sessions = await dest_store.list_sessions(workspaces[0]["id"])
    assert len(sessions) == 2
    session_names = {s["name"] for s in sessions}
    assert "Target Session (Imported 1)" in session_names
    
    await dest_store.close()
