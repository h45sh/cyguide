import pytest
import json
from pathlib import Path
from cyguide.engine.store import GraphStore
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.recommendation import RecommendationEngine
from cyguide.schemas.dns import DomainInfo, DnsRecord
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.web import WebEndpoint, WebVulnerability
from tools.subfinder.adapter import SubfinderAdapter
from tools.nmap.adapter import NmapAdapter
from tools.gobuster.adapter import GobusterAdapter
from tools.nikto.adapter import NiktoAdapter


@pytest.mark.asyncio
async def test_multi_tool_investigation_pipeline(tmp_path):
    """
    End-to-end multi-step investigation pipeline test:
    Domain (Subfinder) -> Host/Ports (Nmap) -> Recommendation (Gobuster) -> Endpoints (Gobuster) -> Vulns (Nikto) -> Graph Validation
    """
    db_path = tmp_path / "pipeline.db"
    store = GraphStore(str(db_path))
    await store.initialize()

    # 1. Setup Recommendation Engine listener
    recommendation_engine = RecommendationEngine(store)
    store.on_upsert(recommendation_engine.handle_upsert)

    ws_id, sess_id = await store.get_or_create_learning_sandbox()

    # --- STEP 1: Subdomain Discovery (Subfinder) ---
    subfinder_adapter = SubfinderAdapter()
    subfinder_output = """
api.example.com
admin.example.com
"""
    domain_target = DomainInfo.create(domain="example.com")
    await store.upsert_finding(sess_id, domain_target)

    async for finding in subfinder_adapter.parse_output(subfinder_output, domain_target):
        await store.upsert_finding(sess_id, finding)

    dns_records = await store.query("dns.record", session_id=sess_id)
    assert len(dns_records) >= 2

    # --- STEP 2: Host & Port Scanning (Nmap) ---
    nmap_adapter = NmapAdapter()
    nmap_output = """
Nmap scan report for api.example.com (10.0.0.5)
PORT     STATE SERVICE
80/tcp   open  http
443/tcp  open  https
"""
    host_target = NetworkHost.create(ip="10.0.0.5", hostname="api.example.com")
    await store.upsert_finding(sess_id, host_target)

    async for finding in nmap_adapter.parse_output(nmap_output, host_target):
        await store.upsert_finding(sess_id, finding)

    services = await store.query("network.service", session_id=sess_id)
    assert len(services) == 2
    ports = [json.loads(s["data_json"]).get("port") or json.loads(s["pik_json"]).get("port") for s in services]
    assert 80 in ports
    assert 443 in ports

    # --- STEP 3: Automated Recommendation Check ---
    # The RecommendationEngine should have reacted to port 80 and created a proposed gobuster node
    all_nodes = await store.get_all_nodes(sess_id)
    proposed_nodes = [n for n in all_nodes if n.get("status") == "proposed"]
    assert len(proposed_nodes) >= 1
    assert any(json.loads(p["data_json"]).get("tool_suggestion") == "gobuster" for p in proposed_nodes)

    # --- STEP 4: Directory Brute-Forcing (Gobuster) ---
    gobuster_adapter = GobusterAdapter()
    gobuster_output = """
/admin               (Status: 200) [Size: 1024]
/login               (Status: 200) [Size: 512]
"""
    http_service = NetworkService.create(host_ip="10.0.0.5", port=80, protocol="tcp")
    async for finding in gobuster_adapter.parse_output(gobuster_output, http_service):
        await store.upsert_finding(sess_id, finding)

    endpoints = await store.query("web.endpoint", session_id=sess_id)
    assert len(endpoints) >= 2
    confirmed_endpoints = [e for e in endpoints if e.get("status") == "confirmed"]
    assert len(confirmed_endpoints) == 2
    urls = [json.loads(e["pik_json"])["url"] for e in confirmed_endpoints]
    assert "http://10.0.0.5/admin" in urls or "http://10.0.0.5:80/admin" in urls

    # --- STEP 5: Web Vulnerability Scanning (Nikto) ---
    nikto_adapter = NiktoAdapter()
    nikto_output = """
+ /admin/: Directory indexing found.
+ OSVDB-3092: /admin/config.php: Configuration file found.
"""
    admin_endpoint = WebEndpoint.create(url="http://10.0.0.5/admin")
    async for finding in nikto_adapter.parse_output(nikto_output, admin_endpoint):
        await store.upsert_finding(sess_id, finding)

    web_vulns = await store.query("web.vulnerability", session_id=sess_id)
    assert len(web_vulns) >= 1

    # --- STEP 6: Complete Graph Validation ---
    stats = await store.get_stats(sess_id)
    assert stats["domain.info"] == 1
    assert stats["dns.record"] >= 2
    assert stats["network.host"] == 1
    assert stats["network.service"] == 2
    assert stats["web.endpoint"] >= 2
    assert stats["web.vulnerability"] >= 1

    await store.close()
