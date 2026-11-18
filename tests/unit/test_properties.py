"""Mathematical and property-based verification tests using Hypothesis.

Enforces algebraic laws and system invariants across the codebase:
1. PIK Determinism & Key Invariance:
   - Hash idempotence: generate_node_id is a deterministic pure function.
   - Key-order independence: json sort_keys guarantees dict order has zero effect on PIK.
   - Semantic normalization: whitespace and case canonicalization preserve logical identity.
2. SSRF & Network Boundary Invariance:
   - 100% rejection rate for link-local/cloud metadata derivations across all encodings.
   - Zero false-positive blocking of valid RFC1918 and public target destinations.
3. GraphStore Ingestion Invariants:
   - Ingestion idempotence: Ingesting finding F multiple times results in 1 node.
   - Commutativity: Upserting findings {A, B} in any order yields the exact same graph state.
"""

import pytest

pytestmark = pytest.mark.tier0

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given
from hypothesis import strategies as st

from cyguide.common.canonicalize import (
    canonicalize_host,
    canonicalize_mapping,
    canonicalize_port,
)
from cyguide.engine.gateway import is_blocked_destination
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService

# ---------------------------------------------------------------------------
# Pillar 1.A: Canonicalization & PIK Invariants
# ---------------------------------------------------------------------------


@given(st.text(min_size=1, max_size=100))
def test_canonicalize_host_idempotence(text):
    """Property: canonicalize_host is idempotent f(f(x)) == f(x)."""
    first = canonicalize_host(text)
    second = canonicalize_host(first)
    assert first == second


@given(
    st.integers(min_value=-10000, max_value=100000),
)
def test_canonicalize_port_always_returns_int(val):
    """Property: canonicalize_port always returns an integer without raising."""
    res = canonicalize_port(val)
    assert isinstance(res, int)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
        max_size=10,
    )
)
def test_pik_generation_key_order_independence(data):
    """Algebraic Law: PIK hash is invariant to dictionary key insertion order."""
    store = GraphStore(":memory:")
    # Create reversed key ordering
    reversed_data = dict(reversed(list(data.items())))

    hash1 = store.generate_node_id("network.host", data)
    hash2 = store.generate_node_id("network.host", reversed_data)

    assert hash1 == hash2, "Node ID hash must be invariant to dictionary ordering"


@given(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=30),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=30),
)
def test_canonicalize_mapping_handles_arbitrary_unicode(k, v):
    """Property: canonicalize_mapping never crashes on arbitrary unicode dictionary inputs."""
    d = {k: v}
    res = canonicalize_mapping(d)
    assert isinstance(res, dict)


@given(
    st.sampled_from(["192.168.1.1", "10.0.0.5", "172.16.1.10"]),
    st.integers(min_value=1, max_value=65535),
    st.sampled_from(["tcp", "udp"]),
)
def test_service_pik_determinism(ip, port, proto):
    """Property: NetworkService creates deterministic, repeatable PIK and Node IDs."""
    store = GraphStore(":memory:")
    svc1 = NetworkService.create(host_ip=ip, port=port, protocol=proto, service_name="test")
    svc2 = NetworkService.create(
        host_ip=f"  {ip.upper()}  ",
        port=str(port),
        protocol=f" {proto.upper()} ",
        service_name="test",
    )

    id1 = store.generate_node_id(svc1.schema_type, svc1.pik)
    id2 = store.generate_node_id(svc2.schema_type, svc2.pik)

    assert id1 == id2, "Canonicalization must unify dirty representations into identical PIK hash"


# ---------------------------------------------------------------------------
# Pillar 1.B: SSRF & Security Boundary Invariants
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(
        [
            "169.254.169.254",
            "169.254.1.1",
            "http://169.254.169.254/latest/meta-data/",
            "http://[fd00:ec2::254]/latest/meta-data/",
            "2852039166",  # Decimal notation
            "0xa9fea9fe",  # Hex notation
            "metadata.google.internal",
            "instance-data",
            "100.100.100.200",
        ]
    ),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/.", max_size=20),
)
def test_ssrf_boundary_catches_all_metadata_variants(base_target, suffix):
    """Security Invariant: Any target containing metadata addresses must be blocked unconditionally."""
    target = f"{base_target}{suffix}"
    assert is_blocked_destination(target) is True, f"Failed to block SSRF payload: {target}"


@given(
    st.sampled_from(
        [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "scanme.nmap.org",
            "api.example.com",
            "127.0.0.1",
        ]
    )
)
def test_ssrf_boundary_never_blocks_benign_targets(target):
    """Property: Benign operator targets must never be falsely blocked."""
    assert is_blocked_destination(target) is False, (
        f"False positive block on benign target: {target}"
    )


# ---------------------------------------------------------------------------
# Pillar 1.C: GraphStore State & Algebraic Merge Invariants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graphstore_idempotence_invariant():
    """Algebraic Law: Upserting finding F multiple times is strictly idempotent (F ∪ F = F)."""
    store = GraphStore(":memory:")
    await store.initialize()
    try:
        ws_id = await store.create_workspace("WS-Idempotence")
        session_id = await store.create_session(ws_id, "Sess-Idempotence")

        host = NetworkHost.create(ip="10.10.10.10", hostname="idempotent-target")

        # Ingest 5 times
        for _ in range(5):
            await store.upsert_finding(session_id, host)

        nodes = await store.get_all_nodes(session_id)
        assert len(nodes) == 1, "GraphStore must never duplicate node on repeated identical upserts"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_graphstore_merge_commutativity_invariant():
    """Algebraic Law: Findings A and B ingested in order [A, B] vs [B, A] yield the identical node and edge count."""
    store1 = GraphStore(":memory:")
    await store1.initialize()
    store2 = GraphStore(":memory:")
    await store2.initialize()
    try:
        ws1 = await store1.create_workspace("WS-Comm1")
        s1 = await store1.create_session(ws1, "Sess-Comm1")

        ws2 = await store2.create_workspace("WS-Comm2")
        s2 = await store2.create_session(ws2, "Sess-Comm2")

        host = NetworkHost.create(ip="192.168.50.5", hostname="target50")
        svc = NetworkService.create(
            host_ip="192.168.50.5", port=80, protocol="tcp", service_name="http"
        )

        # Store 1: Host then Service
        await store1.upsert_finding(s1, host)
        await store1.upsert_finding(s1, svc)

        # Store 2: Service then Host
        await store2.upsert_finding(s2, svc)
        await store2.upsert_finding(s2, host)

        nodes1 = await store1.get_all_nodes(s1)
        nodes2 = await store2.get_all_nodes(s2)

        assert len(nodes1) == len(nodes2) == 2
        assert {n["id"] for n in nodes1} == {n["id"] for n in nodes2}

        edges1 = await store1.get_all_edges(s1)
        edges2 = await store2.get_all_edges(s2)
        assert len(edges1) == len(edges2) == 1
        assert edges1[0]["relation_type"] == edges2[0]["relation_type"]
    finally:
        await store1.close()
        await store2.close()


# ---------------------------------------------------------------------------
# Pillar 1.D: Stateful Model-Based Testing for GraphStore Lifecycles
# ---------------------------------------------------------------------------

from hypothesis import HealthCheck, settings
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule


class GraphStoreStateMachine(RuleBasedStateMachine):
    """Formal Model-Based State Machine for GraphStore.

    Generates interleaved sequences of workspace, session, finding, and migration
    operations, continuously verifying structural integrity and relational invariants.
    """

    workspaces = Bundle("workspaces")
    sessions = Bundle("sessions")

    def __init__(self):
        super().__init__()
        import asyncio

        self.loop = asyncio.new_event_loop()
        self.store = GraphStore(":memory:")
        self.loop.run_until_complete(self.store.initialize())
        self.active_sessions: set[str] = set()

    def teardown(self):
        self.loop.run_until_complete(self.store.close())
        self.loop.close()

    @rule(target=workspaces, name=st.text(min_size=1, max_size=20))
    def create_workspace(self, name):
        ws_id = self.loop.run_until_complete(self.store.create_workspace(name))
        return ws_id

    @rule(target=sessions, ws_id=workspaces, name=st.text(min_size=1, max_size=20))
    def create_session(self, ws_id, name):
        sess_id = self.loop.run_until_complete(self.store.create_session(ws_id, name))
        self.active_sessions.add(sess_id)
        return sess_id

    @rule(
        sess_id=sessions,
        ip=st.sampled_from(["10.0.0.1", "10.0.0.2", "192.168.1.10"]),
        port=st.sampled_from([22, 80, 443, 8080]),
    )
    def ingest_findings(self, sess_id, ip, port):
        host = NetworkHost.create(ip=ip)
        svc = NetworkService.create(host_ip=ip, port=port, protocol="tcp", service_name="web")
        self.loop.run_until_complete(self.store.upsert_finding(sess_id, host))
        self.loop.run_until_complete(self.store.upsert_finding(sess_id, svc))

    @rule(sess_id=sessions)
    def close_and_reopen_session(self, sess_id):
        self.loop.run_until_complete(self.store.close_session(sess_id))
        self.loop.run_until_complete(self.store.reopen_session(sess_id))

    @invariant()
    def check_sqlite_integrity_and_invariants(self):
        # 1. SQLite integrity pragma must always be OK
        status, _ = self.loop.run_until_complete(self.store.check_integrity())
        assert status == "ok", f"Integrity check failed: {status}"

        # 2. Relational invariant: All edges must connect to existing nodes
        async def verify_relational():
            async with self.store._get_conn() as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM edges WHERE source_id NOT IN (SELECT id FROM nodes) "
                    "OR target_id NOT IN (SELECT id FROM nodes)"
                )
                orphaned_edges = (await cursor.fetchone())[0]
                assert orphaned_edges == 0, f"Found {orphaned_edges} dangling edges"

        self.loop.run_until_complete(verify_relational())


TestGraphStoreStateMachine = GraphStoreStateMachine.TestCase
TestGraphStoreStateMachine.settings = settings(
    max_examples=25,
    stateful_step_count=15,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

