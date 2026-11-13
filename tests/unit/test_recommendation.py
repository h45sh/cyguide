import json

import pytest

from cyguide.engine.recommendation import RecommendationEngine
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkService
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
        host_ip="10.0.0.1", port=80, protocol="tcp", service_name="http"
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
    service = NetworkService.create(host_ip="10.0.0.1", port=22, protocol="tcp", service_name="ssh")

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
    endpoint = WebEndpoint.create(url="http://10.0.0.1/admin", host_ip="10.0.0.1", port=80)

    await store.upsert_finding(sess_id, endpoint)

    # Check that a proposed vulnerability finding exists
    nodes = await store.get_all_nodes(sess_id)
    proposed = [n for n in nodes if n.get("status") == "proposed"]

    assert len(proposed) == 1
    p_node = proposed[0]
    assert p_node["schema_type"] == "web.vulnerability"

    data = json.loads(p_node["data_json"])
    assert data["tool_suggestion"] == "nikto"
    await store.close()


def test_recommendation_rule_pure_evaluation():
    """Verify recommendation rules evaluate findings purely in memory without database fixtures."""
    from cyguide.engine.recommendation import (
        SubdomainRecommendationRule,
        WebServiceRecommendationRule,
        WhoisRecommendationRule,
    )
    from cyguide.schemas.network import NetworkHost, NetworkService

    # 1. WebService rule
    service = NetworkService.create(
        host_ip="192.168.1.50", port=443, protocol="tcp", service_name="https"
    )
    web_rule = WebServiceRecommendationRule()
    results = web_rule.evaluate(service)
    assert len(results) == 1
    assert results[0].schema_type == "web.endpoint"
    assert results[0].pik["url"] == "https://192.168.1.50/"

    # 2. Subdomain rule
    host_domain = NetworkHost.create(ip="8.8.8.8", hostname="test.corp.local")
    sub_rule = SubdomainRecommendationRule()
    sub_results = sub_rule.evaluate(host_domain)
    assert len(sub_results) == 1
    assert sub_results[0].schema_type == "dns.record"

    # 3. Whois rule
    public_host = NetworkHost.create(ip="93.184.216.34")
    whois_rule = WhoisRecommendationRule()
    whois_results = whois_rule.evaluate(public_host)
    assert len(whois_results) == 1
    assert whois_results[0].schema_type == "domain.info"
