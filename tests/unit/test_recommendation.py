import pytest
import json
from cyguide.engine.store import GraphStore
from cyguide.engine.recommendation import RecommendationEngine
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.schemas.network import NetworkService, NetworkHost
from cyguide.schemas.web import WebEndpoint


@pytest.mark.asyncio
async def test_web_service_recommendation():
    store = GraphStore(":memory:")
    await store.initialize()
    
    engine = RecommendationEngine(store)
    store.on_upsert(engine.handle_upsert)
    
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Session")
    
    # 1. Create a service finding on port 80
    service = NetworkService.create(
        host_ip="10.0.0.1",
        port=80,
        protocol="tcp",
        service_name="http"
    )
    
    # Save the finding (status defaults to 'confirmed')
    await store.upsert_finding(sess_id, service)
    
    # 2. Check that a proposed finding was automatically inserted
    nodes = await store.get_all_nodes(sess_id)
    proposed = [n for n in nodes if n.get("status") == "proposed"]
    
    assert len(proposed) == 1
    p_node = proposed[0]
    assert p_node["schema_type"] == "web.endpoint"
    
    pik = json.loads(p_node["pik_json"])
    assert pik["url"] == "http://10.0.0.1/"
    
    data = json.loads(p_node["data_json"])
    assert data["tool_suggestion"] == "gobuster"
    assert "gobuster dir -u http://10.0.0.1/" in data["recommended_command"]

    await store.close()


@pytest.mark.asyncio
async def test_unrelated_service_no_recommendation():
    store = GraphStore(":memory:")
    await store.initialize()
    
    engine = RecommendationEngine(store)
    store.on_upsert(engine.handle_upsert)
    
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Session")
    
    # Create an SSH service (port 22)
    service = NetworkService.create(
        host_ip="10.0.0.1",
        port=22,
        protocol="tcp",
        service_name="ssh"
    )
    
    await store.upsert_finding(sess_id, service)
    
    # Check that NO proposed findings exist
    nodes = await store.get_all_nodes(sess_id)
    proposed = [n for n in nodes if n.get("status") == "proposed"]
    assert len(proposed) == 0

    await store.close()


@pytest.mark.asyncio
async def test_web_vuln_recommendation():
    store = GraphStore(":memory:")
    await store.initialize()
    
    engine = RecommendationEngine(store)
    store.on_upsert(engine.handle_upsert)
    
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Session")
    
    # Create a confirmed WebEndpoint
    endpoint = WebEndpoint.create(
        url="http://10.0.0.1/admin",
        host_ip="10.0.0.1",
        port=80
    )
    
    await store.upsert_finding(sess_id, endpoint)
    
    # Check that a proposed vulnerability finding exists
    nodes = await store.get_all_nodes(sess_id)
    proposed = [n for n in nodes if n.get("status") == "proposed"]
    
    assert len(proposed) == 1
    p_node = proposed[0]
    assert p_node["schema_type"] == "web.vulnerability"
    
    data = json.loads(p_node["data_json"])
    assert data["tool_suggestion"] == "nikto"
    assert "nikto -h http://10.0.0.1/admin" in data["recommended_command"]

    await store.close()


@pytest.mark.asyncio
async def test_dismiss_recommendation():
    store = GraphStore(":memory:")
    await store.initialize()
    
    from unittest.mock import MagicMock
    facade = PowerWorkspaceFacade(store, MagicMock(), MagicMock())
    
    engine = RecommendationEngine(store)
    store.on_upsert(engine.handle_upsert)
    
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Session")
    
    # Create service to trigger recommendation
    service = NetworkService.create(
        host_ip="10.0.0.1",
        port=80,
        protocol="tcp",
        service_name="http"
    )
    await store.upsert_finding(sess_id, service)
    
    # Verify it exists
    nodes = await store.get_all_nodes(sess_id)
    proposed = [n for n in nodes if n.get("status") == "proposed"]
    assert len(proposed) == 1
    
    # Dismiss it
    pik = json.loads(proposed[0]["pik_json"])
    schema_type = proposed[0]["schema_type"]
    await facade.dismiss_proposed_finding(sess_id, schema_type, pik)
    
    # Verify it is deleted
    nodes_after = await store.get_all_nodes(sess_id)
    proposed_after = [n for n in nodes_after if n.get("status") == "proposed"]
    assert len(proposed_after) == 0

    await store.close()
