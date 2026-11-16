#!/usr/bin/env python3
"""CyGuide Comprehensive Limit-Testing & Bottleneck Profiling Suite.

This script benchmarks the extreme limits of CyGuide across:
1. Startup & Import Latency (venv vs pipx vs dependency breakdown)
2. Terminal Stream Ingestion (up to 500,000 lines, memory & throughput)
3. GraphStore High-Scale Ingestion (batch vs single, 10k+ nodes, WAL scaling)
4. GraphStore Query Latency (1k to 20k nodes, get_all_nodes, get_graph_snapshot)
5. Tool Output Parsing & Pydantic Deserialization (50,000 lines throughput)
6. EntityBrowser UI & Virtualization Scaling (1,000 to 10,000 entities)
"""

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc


def format_bytes(num_bytes: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def section(title: str):
    print("\n" + "=" * 70)
    print(f" {title.upper()}")
    print("=" * 70)


def benchmark_startup_and_imports():
    section("1. Startup & Import Latency Profile")

    # A. Dependency breakdown
    modules_to_test = [
        ("pydantic", "import pydantic"),
        ("rich", "import rich"),
        ("textual", "import textual"),
        ("aiosqlite", "import aiosqlite"),
        ("httpx", "import httpx"),
        ("dnspython", "import dns.resolver"),
        ("cyguide.paths", "from cyguide.paths import get_default_data_dir"),
        ("cyguide.schemas", "from cyguide.schemas.network import NetworkHost"),
        ("cyguide.engine.store", "from cyguide.engine.store import GraphStore"),
        ("cyguide.ui.widgets.power", "from cyguide.ui.widgets.power import EntityBrowser"),
        ("cyguide.app (FULL APP)", "from cyguide.app import CyGuideApp"),
    ]

    print("--- Subsystem Import Latencies (Fresh Python Process) ---")
    python_bin = sys.executable
    for name, code in modules_to_test:
        t0 = time.perf_counter()
        subprocess.run(
            [python_bin, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  {name:<32} : {elapsed:>7.1f} ms")

    # B. CLI Startup: venv vs pipx
    print("\n--- CLI Invocation Comparison: venv vs pipx ---")
    venv_cyg = os.path.join(os.path.dirname(sys.executable), "cyg")
    pipx_cyg = shutil.which("cyg")
    pipx_python = "/home/harsh/.local/share/pipx/venvs/cyguide/bin/python"

    def time_cli(cmd_list, iterations=3):
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            times.append((time.perf_counter() - t0) * 1000)
        return min(times), sum(times) / len(times), max(times)

    if os.path.exists(venv_cyg):
        v_min, v_avg, v_max = time_cli([venv_cyg, "--version"])
        print(f"  venv cyg --version       : min={v_min:.1f}ms, avg={v_avg:.1f}ms, max={v_max:.1f}ms")
    if pipx_cyg and os.path.exists(pipx_cyg):
        p_min, p_avg, p_max = time_cli([pipx_cyg, "--version"])
        print(f"  pipx cyg --version       : min={p_min:.1f}ms, avg={p_avg:.1f}ms, max={p_max:.1f}ms")

    if os.path.exists(pipx_python):
        pv_min, pv_avg, pv_max = time_cli([pipx_python, "-c", "from cyguide.app import CyGuideApp"])
        vv_min, vv_avg, vv_max = time_cli([python_bin, "-c", "from cyguide.app import CyGuideApp"])
        print(f"  pipx import cyguide.app  : min={pv_min:.1f}ms, avg={pv_avg:.1f}ms, max={pv_max:.1f}ms")
        print(f"  venv import cyguide.app  : min={vv_min:.1f}ms, avg={vv_avg:.1f}ms, max={vv_max:.1f}ms")


def benchmark_terminal_stream_limits():
    section("2. Terminal Stream Ingestion Limits (Bombardment)")
    from cyguide.ui.widgets.terminal_stream import TerminalStreamPane

    line_counts = [50_000, 100_000, 250_000, 500_000]

    for total_lines in line_counts:
        pane = TerminalStreamPane(max_lines=5000)
        tracemalloc.start()
        t0 = time.perf_counter()

        chunk_size = 500
        num_chunks = total_lines // chunk_size
        for i in range(num_chunks):
            chunk = "".join(f"SCAN_LOG_{i*chunk_size + j:07d}: Host 10.0.{j%254}.{j%254} port {j%65535} OPEN service=http\n" for j in range(chunk_size))
            pane.write(chunk)

        pane.flush()
        elapsed = time.perf_counter() - t0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        rate = total_lines / elapsed
        print(f"  Lines: {total_lines:>7,d} | Time: {elapsed:>5.2f}s | Rate: {rate:>10,.0f} lines/sec | Peak RAM: {format_bytes(peak_mem):>9} | Ring Buf Size: {len(pane._lines):>5d}")


async def benchmark_graphstore_limits():
    section("3. GraphStore Scale & Ingestion Limits")
    from cyguide.engine.store import GraphStore
    from cyguide.schemas.network import NetworkHost, NetworkService

    scales = [1000, 5000, 10000]

    for count in scales:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "bench.db")
            store = GraphStore(db_path)
            await store.initialize()
            ws_id = await store.create_workspace("BenchWS")
            sess_id = await store.create_session(ws_id, "BenchSess")

            hosts_count = count // 2
            services_count = count // 2

            findings = [
                NetworkHost.create(ip=f"10.{i // 65536}.{(i // 256) % 256}.{i % 256 + 1}", hostname=f"h-{i}.local")
                for i in range(hosts_count)
            ] + [
                NetworkService.create(host_ip=f"10.{i // 65536}.{(i // 256) % 256}.{i % 256 + 1}", port=80 + (i % 1000), service_name="http")
                for i in range(services_count)
            ]

            # Test A: Micro-batch atomic upsert (upsert_findings_batch with 100 items)
            t0 = time.perf_counter()
            batch_size = 100
            for b in range(0, len(findings), batch_size):
                await store.upsert_findings_batch(sess_id, findings[b : b + batch_size])
            elapsed_batch = time.perf_counter() - t0
            rate_batch = len(findings) / elapsed_batch

            # Query timings at this scale
            t_q_nodes = time.perf_counter()
            nodes = await store.get_all_nodes(sess_id)
            elapsed_q_nodes = (time.perf_counter() - t_q_nodes) * 1000

            t_q_edges = time.perf_counter()
            edges = await store.get_all_edges(sess_id)
            elapsed_q_edges = (time.perf_counter() - t_q_edges) * 1000

            t_q_snap = time.perf_counter()
            confirmed_nodes = [n for n in nodes if n.get("status") == "confirmed"]
            snap = {"nodes": confirmed_nodes, "edges": edges}
            elapsed_q_snap = (time.perf_counter() - t_q_snap) * 1000

            print(f"  Findings: {count:>6,d} | Batch Upsert (100): {elapsed_batch:>5.2f}s ({rate_batch:>8,.0f}/s) | Query Nodes: {elapsed_q_nodes:>5.1f}ms | Edges: {elapsed_q_edges:>5.1f}ms | Snapshot: {elapsed_q_snap:>5.1f}ms (Nodes={len(nodes):,}, Edges={len(edges):,})")

            # Test B: Export performance
            export_path = os.path.join(tmpdir, "export.db")
            t_exp = time.perf_counter()
            await store.export_session(sess_id, export_path)
            elapsed_exp = (time.perf_counter() - t_exp) * 1000

            # Test C: Import performance
            t_imp = time.perf_counter()
            await store.import_session(export_path, ws_id)
            elapsed_imp = (time.perf_counter() - t_imp) * 1000

            print(f"            --> Export DB: {elapsed_exp:>6.1f}ms | Import DB: {elapsed_imp:>6.1f}ms | DB File Size: {format_bytes(os.path.getsize(db_path))}")

            await store.close()

    # Comparison: Single upsert vs Batch upsert
    print("\n--- Single Transaction vs Batch Ingestion Comparison (250 Findings) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "single_bench.db")
        store = GraphStore(db_path)
        await store.initialize()
        ws_id = await store.create_workspace("CompWS")
        sess_id = await store.create_session(ws_id, "CompSess")
        comp_count = 250
        test_findings = [NetworkHost.create(ip=f"192.168.1.{i+1}") for i in range(comp_count)]

        # 1. Single upserts (each opens transaction & commits)
        t0 = time.perf_counter()
        for f in test_findings:
            await store.upsert_finding(sess_id, f)
        elapsed_single = time.perf_counter() - t0
        rate_single = comp_count / elapsed_single

        # 2. Batch upsert of 250 findings (single transaction)
        sess_id2 = await store.create_session(ws_id, "CompSess2")
        t0 = time.perf_counter()
        await store.upsert_findings_batch(sess_id2, test_findings)
        elapsed_all_batch = time.perf_counter() - t0
        rate_all_batch = comp_count / elapsed_all_batch

        print(f"  {comp_count} single upsert_finding calls  : {elapsed_single:.2f}s ({rate_single:.0f} findings/sec) - Contention & Commit Overhead")
        print(f"  {comp_count} batch upsert_findings_batch : {elapsed_all_batch:.3f}s ({rate_all_batch:.0f} findings/sec) - {elapsed_single/elapsed_all_batch:.1f}x FASTER")
        await store.close()


def benchmark_parsing_and_models():
    section("4. Tool Output Parsing & Schema Model Validation Limits")
    from cyguide.schemas.network import NetworkHost
    from cyguide.schemas.web import WebEndpoint

    # A. Raw Pydantic model creation
    counts = [10_000, 50_000]
    for n in counts:
        t0 = time.perf_counter()
        hosts = [
            NetworkHost.create(ip=f"10.0.{i//254}.{i%254+1}", hostname=f"srv-{i}.corp")
            for i in range(n)
        ]
        elapsed = time.perf_counter() - t0
        rate = n / elapsed
        print(f"  Pydantic NetworkHost.create x {n:>6,d} : {elapsed:>5.2f}s ({rate:>9,.0f} models/sec)")

    for n in counts:
        t0 = time.perf_counter()
        endpoints = [
            WebEndpoint.create(url=f"https://target.corp/api/v1/resource/{i}", status_code=200, content_length=1024)
            for i in range(n)
        ]
        elapsed = time.perf_counter() - t0
        rate = n / elapsed
        print(f"  Pydantic WebEndpoint.create x {n:>6,d} : {elapsed:>5.2f}s ({rate:>9,.0f} models/sec)")

    # B. Regex Parsing simulation (50,000 lines of nmap output)
    import re
    port_pattern = re.compile(r"(\d+)/(tcp|udp)\s+open\s+(\S+)")
    lines = [f"{80 + (i%1000)}/tcp open http" for i in range(50_000)]

    t0 = time.perf_counter()
    matches = 0
    for l in lines:
        m = port_pattern.search(l)
        if m:
            matches += 1
    elapsed_regex = time.perf_counter() - t0
    print(f"  Pre-compiled Regex parse x 50,000 lines : {elapsed_regex:>5.3f}s ({50000/elapsed_regex:>9,.0f} lines/sec)")


async def benchmark_entity_browser_limits():
    section("5. EntityBrowser UI & Virtualization Limits")
    from cyguide.ui.widgets.power import EntityBrowser

    scales = [1000, 5000, 10000, 25000]

    for n in scales:
        browser = EntityBrowser()
        mock_nodes = [
            {
                "id": f"node_{i:06d}",
                "schema_type": "network.host" if i % 3 == 0 else ("network.service" if i % 3 == 1 else "web.endpoint"),
                "pik": {"ip": f"10.0.{i//254}.{i%254+1}", "port": 80 + (i % 100)} if i % 3 != 2 else {"url": f"http://10.0.{i//254}.{i%254+1}:{80 + (i % 100)}/path"},
                "data_json": "{}",
                "status": "confirmed",
                "custom_alias": None,
            }
            for i in range(n)
        ]
        mock_edges = [
            {"source_id": f"node_{(i//3)*3:06d}", "target_id": f"node_{i:06d}", "relation_type": "HAS_CHILD"}
            for i in range(1, n)
            if i % 3 != 0
        ]
        graph_data = {"nodes": mock_nodes, "edges": mock_edges}

        # 1. Full Tree Refresh
        t0 = time.perf_counter()
        await browser.refresh_entities(graph_data)
        elapsed_refresh = (time.perf_counter() - t0) * 1000

        # 2. Filter / Search across all entities
        browser.set_filter("10.0.1")
        t0 = time.perf_counter()
        await browser.refresh_entities(graph_data)
        elapsed_filter = (time.perf_counter() - t0) * 1000

        # 3. Fast-path (identical data)
        t0 = time.perf_counter()
        await browser.refresh_entities(graph_data)
        elapsed_fast = (time.perf_counter() - t0) * 1000

        print(f"  Entities: {n:>6,d} | Initial Tree Build: {elapsed_refresh:>6.1f}ms | Filter Query: {elapsed_filter:>6.1f}ms | Fast Path: {elapsed_fast:>6.2f}ms | DOM Tree Nodes: {len(browser.root.children)}")


async def main():
    print("=" * 70)
    print(" CYGUIDE SYSTEM PERFORMANCE & BOTTLENECK LIMIT SUITE")
    print(f" Python: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 70)

    benchmark_startup_and_imports()
    benchmark_terminal_stream_limits()
    await benchmark_graphstore_limits()
    benchmark_parsing_and_models()
    await benchmark_entity_browser_limits()

    section("Summary of Limits & Bottlenecks")
    print("Suite completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
