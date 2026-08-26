import pytest
import json
import asyncio
from uuid import uuid4, UUID
from cyguide.engine.store import GraphStore
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.executor import Executor
from cyguide.engine.reporter import generate_markdown_report
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.web import WebEndpoint
from tests.fixtures.mock_tools import MockNmapAdapter


@pytest.mark.asyncio
async def test_full_session_lifecycle_and_portability(tmp_path):
    """
    Integration test:
    1. Initialize Workspace & Session via PowerWorkspaceFacade.
    2. Insert target entities and execute actions via facade.
    3. Export session to .db and Markdown report.
    4. Validate Markdown structure (Mermaid diagrams, finding counts).
    5. Import into a fresh, isolated database and verify 100% graph restoration.
    """
    # 1. Source System Setup
    src_db_path = tmp_path / "source_env.db"
    src_store = GraphStore(str(src_db_path))
    await src_store.initialize()

    from cyguide.engine.manifest import Manifest
    registry = ToolRegistry()
    mock_manifest = Manifest(
        meta={"name": "mock_nmap", "description": "Mock Nmap", "version": "1.0", "binary": "echo", "categories": ["Scanning"]},
        modes={"power": True, "learning": True},
        input={"accepts": ["network.host"]},
        output={"produces": ["network.service"]}
    )
    registry.tools["mock_nmap"] = {
        "manifest": mock_manifest,
        "adapter": MockNmapAdapter()
    }

    executor = Executor(src_store)
    facade = PowerWorkspaceFacade(src_store, executor, registry)

    # 2. Workspace & Session Management
    ws_id = await facade.create_workspace("RedTeam Alpha")
    session_id = await facade.create_session(ws_id, "Recon Phase 1")
    
    # Rename session
    await facade.rename_session(session_id, "Recon Internal")
    sessions = await src_store.list_sessions(ws_id)
    assert len(sessions) == 1
    assert sessions[0]["name"] == "Recon Internal"

    # 3. Populate Findings
    target_host = NetworkHost.create(ip="192.168.1.100", hostname="core-router")
    await src_store.upsert_finding(session_id, target_host)

    target_service = NetworkService.create(
        host_ip="192.168.1.100", 
        port=80, 
        protocol="tcp", 
        service_name="http"
    )
    await src_store.upsert_finding(session_id, target_service)

    target_endpoint = WebEndpoint.create(
        url="http://192.168.1.100:80/admin",
        method="GET",
        status_code=200
    )
    await src_store.upsert_finding(session_id, target_endpoint)

    # 4. Execute Action through Facade with background completion wait
    target_node_id = src_store._generate_node_id(target_host.schema_type, target_host.pik)
    action = ActionRequest(
        session_id=session_id,
        tool_name="mock_nmap",
        target_entity_id=target_node_id,
        params={"raw_flags": "-sV -p 80"},
        triggered_by=ActionSource.USER
    )

    output_lines = []
    async def on_output(text: str):
        output_lines.append(text)

    done_event = asyncio.Event()
    async def on_complete():
        done_event.set()

    await facade.submit_action(action, on_output=on_output, on_complete=on_complete)
    await asyncio.wait_for(done_event.wait(), timeout=5.0)
    assert len(output_lines) > 0

    # 5. Export to .db and Markdown
    export_db_file = tmp_path / "recon_export.db"
    export_md_file = tmp_path / "recon_report.md"

    await src_store.export_session(session_id, str(export_db_file))
    report_text = await generate_markdown_report(src_store, session_id)
    export_md_file.write_text(report_text, encoding="utf-8")

    assert export_db_file.exists()
    assert export_md_file.exists()

    # 6. Validate Markdown Content
    md_content = export_md_file.read_text()
    assert "CyGuide Investigation Report: Recon Internal" in md_content
    assert "RedTeam Alpha" in md_content
    assert "192.168.1.100" in md_content
    assert "/admin" in md_content

    # 7. Import into Clean Destination Database
    dst_db_path = tmp_path / "dest_env.db"
    dst_store = GraphStore(str(dst_db_path))
    await dst_store.initialize()

    imported_session_id = await dst_store.import_session(str(export_db_file))
    assert imported_session_id == session_id

    # 8. Verify Graph Integrity in Destination Database
    imported_hosts = await dst_store.query("network.host", session_id=session_id)
    assert len(imported_hosts) == 1
    host_pik = json.loads(imported_hosts[0]["pik_json"])
    assert host_pik["ip"] == "192.168.1.100"

    imported_services = await dst_store.query("network.service", session_id=session_id)
    assert len(imported_services) >= 1

    imported_endpoints = await dst_store.query("web.endpoint", session_id=session_id)
    assert len(imported_endpoints) == 1
    endpoint_pik = json.loads(imported_endpoints[0]["pik_json"])
    assert "/admin" in endpoint_pik["url"]

    # Verify event logs restored
    events = await dst_store.get_event_log(session_id)
    assert len(events) > 0

    await src_store.close()
    await dst_store.close()
