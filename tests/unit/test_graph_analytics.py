"""Unit tests for GraphAnalyticsEngine and attack path / blast radius calculations."""

import pytest

pytestmark = pytest.mark.fast

from cyguide.engine.graph_analytics import GraphAnalyticsEngine
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.vulnerability import VulnerabilityFound
from cyguide.schemas.web import WebEndpoint


def test_empty_graph_analytics():
    engine = GraphAnalyticsEngine([], [])
    assert engine.find_shortest_attack_path("node1", "node2") is None
    assert engine.calculate_blast_radius("node1") == set()
    assert engine.identify_critical_assets() == []
    assert engine.find_all_attack_paths_to_critical() == {}


def test_shortest_attack_path():
    nodes = [
        {"id": "dns_1", "schema_type": "dns.record"},
        {"id": "host_1", "schema_type": "network.host"},
        {"id": "web_1", "schema_type": "web.endpoint"},
        {"id": "vuln_1", "schema_type": "vulnerability.found"},
        {"id": "cred_1", "schema_type": "credential.found"},
        {"id": "isolated_1", "schema_type": "network.host"},
    ]
    edges = [
        {"source_id": "dns_1", "target_id": "host_1", "relation_type": "resolves_to"},
        {"source_id": "host_1", "target_id": "web_1", "relation_type": "hosts"},
        {"source_id": "web_1", "target_id": "vuln_1", "relation_type": "vulnerable_to"},
        {"source_id": "vuln_1", "target_id": "cred_1", "relation_type": "yields"},
    ]

    engine = GraphAnalyticsEngine(nodes, edges)

    # 1. Path from dns_1 to cred_1
    path = engine.find_shortest_attack_path("dns_1", "cred_1")
    assert path is not None
    assert [n["id"] for n in path] == ["dns_1", "host_1", "web_1", "vuln_1", "cred_1"]

    # 2. Self path
    self_path = engine.find_shortest_attack_path("dns_1", "dns_1")
    assert self_path is not None
    assert [n["id"] for n in self_path] == ["dns_1"]

    # 3. Isolated node (unreachable)
    unreachable = engine.find_shortest_attack_path("dns_1", "isolated_1")
    assert unreachable is None


def test_calculate_blast_radius():
    nodes = [
        {"id": "host_1", "schema_type": "network.host"},
        {"id": "svc_1", "schema_type": "network.service"},
        {"id": "svc_2", "schema_type": "network.service"},
        {"id": "web_1", "schema_type": "web.endpoint"},
    ]
    edges = [
        {"source_id": "host_1", "target_id": "svc_1", "relation_type": "runs"},
        {"source_id": "host_1", "target_id": "svc_2", "relation_type": "runs"},
        {"source_id": "svc_1", "target_id": "web_1", "relation_type": "exposes"},
    ]

    engine = GraphAnalyticsEngine(nodes, edges)

    # From host_1, everything is in the blast radius
    radius_host = engine.calculate_blast_radius("host_1")
    assert radius_host == {"svc_1", "svc_2", "web_1"}

    # From svc_1, web_1 and parent host_1 are reachable
    radius_svc = engine.calculate_blast_radius("svc_1")
    assert "web_1" in radius_svc
    assert "host_1" in radius_svc


def test_critical_asset_identification():
    nodes = [
        {
            "id": "node_cred",
            "schema_type": "credential.found",
            "data_json": '{"username": "admin"}',
            "pik_json": "{}",
        },
        {
            "id": "node_vuln_crit",
            "schema_type": "vulnerability.found",
            "data_json": '{"severity": "CRITICAL", "name": "RCE"}',
            "pik_json": "{}",
        },
        {
            "id": "node_vuln_low",
            "schema_type": "vulnerability.found",
            "data_json": '{"severity": "LOW", "name": "Info Leak"}',
            "pik_json": "{}",
        },
        {
            "id": "node_ssh",
            "schema_type": "network.service",
            "data_json": "{}",
            "pik_json": '{"port": 22}',
        },
        {
            "id": "node_custom_port",
            "schema_type": "network.service",
            "data_json": "{}",
            "pik_json": '{"port": 9999}',
        },
        {
            "id": "node_internal",
            "schema_type": "host_internal",
            "data_json": "{}",
            "pik_json": "{}",
        },
    ]

    engine = GraphAnalyticsEngine(nodes, [])
    critical = engine.identify_critical_assets()
    critical_ids = {n["id"] for n in critical}

    assert "node_cred" in critical_ids
    assert "node_vuln_crit" in critical_ids
    assert "node_ssh" in critical_ids
    assert "node_internal" in critical_ids
    assert "node_vuln_low" not in critical_ids
    assert "node_custom_port" not in critical_ids


@pytest.mark.asyncio
async def test_facade_graph_analytics_integration(tmp_path):
    store = GraphStore(str(tmp_path / "analytics_test.db"))
    await store.initialize()
    ws_id = await store.create_workspace("AnalyticsWS")
    sess_id = await store.create_session(ws_id, "AnalyticsSess")

    # Ingest findings
    h = NetworkHost.create(ip="10.0.0.5")
    s = NetworkService.create(host_ip="10.0.0.5", port=22, protocol="tcp")
    w = WebEndpoint.create(url="http://10.0.0.5:80/admin")
    v = VulnerabilityFound.create(
        host_ip="10.0.0.5", port=80, vuln_id="CVE-2026-0001", severity="CRITICAL"
    )
    c = CredentialFound.create(
        context="SSH login", username="root", password="toor", host_ip="10.0.0.5"
    )

    await store.upsert_findings_batch(sess_id, [h, s, w, v, c])

    from cyguide.engine.executor import Executor

    executor = Executor()
    facade = PowerWorkspaceFacade(store, executor, ToolRegistry())
    analytics = await facade.get_graph_analytics(sess_id)

    # Verify critical assets detected
    crit = analytics.identify_critical_assets()
    assert len(crit) >= 2  # Credential, Critical vuln, and port 22 SSH service

    pivots = await facade.get_critical_pivot_nodes(sess_id)
    assert isinstance(pivots, list)

    cycles = await facade.get_cyclic_attack_chains(sess_id)
    assert isinstance(cycles, list)

    await store.close()


def test_graph_analytics_betweenness_centrality():
    """Verify Brandes' algorithm computes betweenness centrality correctly on a bridge graph."""
    # Graph: A -> B -> C -> D -> E
    # C is the central bottleneck/choke point bridging {A, B} and {D, E}.
    nodes = [
        {"id": "A", "schema_type": "network.host"},
        {"id": "B", "schema_type": "network.host"},
        {"id": "C", "schema_type": "network.host"},  # Central bridge
        {"id": "D", "schema_type": "network.host"},
        {"id": "E", "schema_type": "network.host"},
    ]
    edges = [
        {"source_id": "A", "target_id": "B", "relation_type": "connects"},
        {"source_id": "B", "target_id": "C", "relation_type": "connects"},
        {"source_id": "C", "target_id": "D", "relation_type": "connects"},
        {"source_id": "D", "target_id": "E", "relation_type": "connects"},
    ]

    engine = GraphAnalyticsEngine(nodes, edges)
    centrality = engine.calculate_betweenness_centrality()

    # C has the highest betweenness centrality
    assert centrality["C"] > centrality["B"]
    assert centrality["C"] > centrality["D"]
    assert centrality["A"] == 0.0
    assert centrality["E"] == 0.0


def test_graph_analytics_strongly_connected_components():
    """Verify Tarjan's SCC algorithm partitions cycles into strongly connected components."""
    # Graph:
    # Component 1 (cycle): 1 -> 2 -> 3 -> 1
    # Component 2 (cycle): 4 -> 5 -> 4
    # Cross edge: 3 -> 4
    nodes = [{"id": str(i), "schema_type": "network.host"} for i in range(1, 6)]
    edges = [
        {"source_id": "1", "target_id": "2"},
        {"source_id": "2", "target_id": "3"},
        {"source_id": "3", "target_id": "1"},
        {"source_id": "3", "target_id": "4"},
        {"source_id": "4", "target_id": "5"},
        {"source_id": "5", "target_id": "4"},
    ]

    engine = GraphAnalyticsEngine(nodes, edges)
    sccs = engine.find_strongly_connected_components()

    # Should find exactly 2 SCC components
    scc_sets = [set(comp) for comp in sccs]
    assert {"1", "2", "3"} in scc_sets
    assert {"4", "5"} in scc_sets


def test_graph_analytics_transitive_closure():
    """Verify transitive closure computes full reachability matrix."""
    nodes = [
        {"id": "X", "schema_type": "host"},
        {"id": "Y", "schema_type": "host"},
        {"id": "Z", "schema_type": "host"},
    ]
    edges = [
        {"source_id": "X", "target_id": "Y"},
        {"source_id": "Y", "target_id": "Z"},
    ]
    engine = GraphAnalyticsEngine(nodes, edges)
    closure = engine.compute_transitive_closure()

    assert closure["X"] == {"Y", "Z"}
    assert closure["Y"] == {"Z"}
    assert closure["Z"] == set()
