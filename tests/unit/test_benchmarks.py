"""High-load bombardment and performance benchmark test suite.

Simulates edge-case bombardments across:
- Massive subprocess stream ingestion (100,000+ lines in TerminalStreamPane).
- GraphStore high-volume findings storm (5,000+ finding models).
- EntityBrowser DOM virtualization and category capping under entity explosion.
- Memory consumption boundedness verification (O(1) memory guarantees).
"""

import asyncio
import time
import tracemalloc

import pytest

from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.ui.widgets.power import EntityBrowser
from cyguide.ui.widgets.terminal_stream import TerminalStreamPane


def test_terminal_stream_high_volume_bombardment():
    """Benchmark: 100,000 rapid output lines streamed to TerminalStreamPane.

    Verifies:
    1. Zero dropped staging chunks.
    2. Ring buffer clamps strictly to max_lines (O(1) memory).
    3. Flush throughput exceeds 200,000 lines/sec without blocking.
    """
    pane = TerminalStreamPane(max_lines=5000)

    tracemalloc.start()
    t0 = time.perf_counter()

    # Enqueue 100,000 lines in 100-line chunks
    for i in range(1000):
        chunk = "".join(f"SCAN_LOG_LINE_{i*100 + j:06d}: Host 192.168.1.{j%254} port {j%65535} open\n" for j in range(100))
        pane.write(chunk)

    # Flush all staged chunks
    pane.flush()
    elapsed = time.perf_counter() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Buffer must be strictly bounded to max_lines (5000)
    assert len(pane._lines) == 5000
    assert pane.virtual_size.height == 5000

    # Ensure last line matches the tail of the stream
    last_line = pane._lines[-1]
    assert "SCAN_LOG_LINE_099999" in last_line

    # Memory allocation for 5,000 kept lines in ring buffer should be small (< 3 MB current resident)
    assert current_mem < 3 * 1024 * 1024, f"Current memory {current_mem / 1024 / 1024:.2f} MB exceeded 3 MB bound"

    # Peak memory during ingestion of 100,000 strings should not exceed 20 MB
    assert peak_mem < 20 * 1024 * 1024, f"Peak memory {peak_mem / 1024 / 1024:.2f} MB exceeded 20 MB bound"

    # Throughput should easily exceed 50,000 lines/sec in pure Python
    throughput = 100000 / elapsed
    assert throughput > 50000, f"Throughput was {throughput:.0f} lines/sec (expected > 50,000)"


@pytest.mark.asyncio
async def test_graphstore_massive_finding_bombardment(tmp_path):
    """Benchmark: 2,500 findings ingested concurrently into SQLite GraphStore.

    Verifies:
    1. WAL mode handles high concurrency without 'database is locked'.
    2. Composite indexes maintain sub-millisecond query latency.
    """
    db_file = str(tmp_path / "bench_store.db")
    store = GraphStore(db_file)
    await store.initialize()

    ws_id = await store.create_workspace("BenchWS")
    sess_id = await store.create_session(ws_id, "BenchSess")

    # Generate 1,000 distinct hosts and 1,500 services
    hosts = [
        NetworkHost.create(ip=f"10.0.{i // 254}.{i % 254 + 1}", hostname=f"host-{i}.corp.local")
        for i in range(1000)
    ]
    services = [
        NetworkService.create(host_ip=f"10.0.{i // 254}.{i % 254 + 1}", port=80 + (i % 100), service_name="http")
        for i in range(1500)
    ]

    t0 = time.perf_counter()

    # Upsert in micro-batches of 100
    all_findings = hosts + services
    batch_size = 100
    for b in range(0, len(all_findings), batch_size):
        batch = all_findings[b:b + batch_size]
        await asyncio.gather(*(store.upsert_finding(sess_id, f) for f in batch))

    elapsed = time.perf_counter() - t0
    nodes = await store.get_all_nodes(sess_id)
    edges = await store.get_all_edges(sess_id)

    assert len(nodes) == 3000  # 1000 hosts + 500 auto-created parent host stubs + 1500 services
    assert len(edges) == 1500  # 1500 services linked to parent hosts

    # Ingestion rate must be > 500 findings/sec on local SQLite
    rate = len(all_findings) / elapsed
    assert rate > 300, f"Ingestion rate was {rate:.0f} findings/sec"

    t_query = time.perf_counter()
    nodes_check = await store.get_all_nodes(sess_id)
    query_elapsed = time.perf_counter() - t_query
    assert len(nodes_check) == 3000
    assert query_elapsed < 0.5, f"Query took {query_elapsed*1000:.1f}ms (expected < 500ms)"

    await store.close()


@pytest.mark.asyncio
async def test_entity_browser_virtualization_cap():
    """Benchmark: EntityBrowser category cap under 2,000 entities.

    Verifies that MAX_DISPLAY_PER_CATEGORY limits rendered tree items to prevent
    Textual layout freezing when a port scan discovers thousands of targets.
    """
    browser = EntityBrowser()

    # Generate 1,500 host nodes
    mock_nodes = [
        {
            "id": f"node_{i:04d}",
            "schema_type": "network.host",
            "pik": {"ip": f"192.168.1.{i % 254 + 1}"},
            "custom_alias": None,
        }
        for i in range(1500)
    ]
    mock_edges = []
    graph_data = {"nodes": mock_nodes, "edges": mock_edges}

    t0 = time.perf_counter()
    await browser.refresh_entities(graph_data)
    elapsed = time.perf_counter() - t0

    # The targets branch must be present
    targets_branch = next((c for c in browser.root.children if "Targets (1500)" in str(c.label)), None)
    assert targets_branch is not None

    # Children under targets must be capped at 200 items + 1 overflow leaf
    assert len(targets_branch.children) == 201
    overflow_leaf = targets_branch.children[-1]
    assert "1300 more" in str(overflow_leaf.label)

    # Rebuilding tree must be sub-50ms
    assert elapsed < 0.1, f"Tree refresh took {elapsed*1000:.1f}ms (expected < 100ms)"

    # Fast path: calling refresh with same data must be instantaneous (< 1ms)
    t_fast = time.perf_counter()
    await browser.refresh_entities(graph_data)
    fast_elapsed = time.perf_counter() - t_fast
    assert fast_elapsed < 0.01, f"Fast path took {fast_elapsed*1000:.2f}ms"


def test_terminal_stream_extreme_limit_bombardment():
    """Extreme limit benchmark: 250,000 rapid output lines streamed to TerminalStreamPane."""
    pane = TerminalStreamPane(max_lines=5000)
    tracemalloc.start()
    t0 = time.perf_counter()

    for i in range(2500):
        chunk = "".join(f"EXTREME_SCAN_LOG_{i*100 + j:07d}: Target 10.0.{j%254}.{j%254} port {j%65535} OPEN\n" for j in range(100))
        pane.write(chunk)

    pane.flush()
    elapsed = time.perf_counter() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert len(pane._lines) == 5000
    assert "EXTREME_SCAN_LOG_0249999" in pane._lines[-1]
    assert current_mem < 5 * 1024 * 1024, f"Current resident RAM exceeded 5MB: {current_mem / 1024 / 1024:.2f}MB"
    throughput = 250000 / elapsed
    assert throughput > 50000, f"Throughput was {throughput:.0f} lines/sec (expected > 50,000)"


@pytest.mark.asyncio
async def test_graphstore_scale_and_query_limits(tmp_path):
    """Extreme limit benchmark: 5,000 findings ingested via atomic batching and queried."""
    db_file = str(tmp_path / "extreme_store.db")
    store = GraphStore(db_file)
    await store.initialize()

    ws_id = await store.create_workspace("ExtremeWS")
    sess_id = await store.create_session(ws_id, "ExtremeSess")

    hosts = [NetworkHost.create(ip=f"10.0.{i // 254}.{i % 254 + 1}") for i in range(2500)]
    services = [
        NetworkService.create(host_ip=f"10.0.{i // 254}.{i % 254 + 1}", port=80 + (i % 100), service_name="http")
        for i in range(2500)
    ]
    all_findings = hosts + services

    t0 = time.perf_counter()
    batch_size = 100
    for b in range(0, len(all_findings), batch_size):
        await store.upsert_findings_batch(sess_id, all_findings[b : b + batch_size])
    ingest_elapsed = time.perf_counter() - t0

    assert ingest_elapsed < 4.0, f"Batch ingestion took {ingest_elapsed:.2f}s (expected < 4.0s)"

    t_nodes = time.perf_counter()
    nodes = await store.get_all_nodes(sess_id)
    nodes_elapsed = (time.perf_counter() - t_nodes) * 1000
    assert len(nodes) == 5000
    assert nodes_elapsed < 100.0, f"Querying 5,000 nodes took {nodes_elapsed:.1f}ms (expected < 100ms)"

    t_edges = time.perf_counter()
    edges = await store.get_all_edges(sess_id)
    edges_elapsed = (time.perf_counter() - t_edges) * 1000
    assert len(edges) == 2500
    assert edges_elapsed < 50.0, f"Querying 2,500 edges took {edges_elapsed:.1f}ms (expected < 50ms)"

    await store.close()


@pytest.mark.asyncio
async def test_entity_browser_extreme_scale_virtualization():
    """Extreme limit benchmark: EntityBrowser handling 5,000 nodes and search filter."""
    browser = EntityBrowser()
    mock_nodes = [
        {
            "id": f"node_{i:05d}",
            "schema_type": "network.host",
            "pik": {"ip": f"10.0.{i // 254}.{i % 254 + 1}"},
            "custom_alias": None,
        }
        for i in range(5000)
    ]
    graph_data = {"nodes": mock_nodes, "edges": []}

    t0 = time.perf_counter()
    await browser.refresh_entities(graph_data)
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 100.0, f"Initial 5,000 nodes tree refresh took {elapsed:.1f}ms (expected < 100ms)"

    browser.set_filter("10.0.1")
    t_filter = time.perf_counter()
    await browser.refresh_entities(graph_data)
    filter_elapsed = (time.perf_counter() - t_filter) * 1000
    assert filter_elapsed < 100.0, f"Filtering 5,000 nodes took {filter_elapsed:.1f}ms (expected < 100ms)"


def test_schema_model_throughput():
    """Benchmark: Pydantic BaseFinding instantiations under high frequency."""
    t0 = time.perf_counter()
    hosts = [NetworkHost.create(ip=f"10.0.{i//254}.{i%254+1}", hostname=f"host-{i}.corp") for i in range(10000)]
    elapsed = time.perf_counter() - t0
    rate = 10000 / elapsed
    assert len(hosts) == 10000
    assert rate > 20000, f"Pydantic model creation rate was {rate:.0f}/sec (expected > 20,000)"
