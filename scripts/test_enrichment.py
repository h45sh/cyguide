"""Stress test for semantic enrichment and multi-adapter pipeline."""

import asyncio
import json
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from tools.nmap.adapter import NmapAdapter
from tools.whois.adapter import WhoisAdapter
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.dns import DnsRecord

async def main():
    print("--- Step 1b: Testing Enrichment & Graph Wiring ---")
    
    store = GraphStore(":memory:")
    await store.initialize()

    try:
        executor = Executor(store)
        session_id = "enrichment-test"

        # 1. Start with an IP
        target_ip = "8.8.8.8"
        host_target = NetworkHost.create(ip=target_ip)

        print(f"\n1. Running Nmap against {target_ip} to establish host...")
        nmap = NmapAdapter()
        async for f in executor.run_tool(nmap, host_target, {}, session_id=session_id):
            print(f"   [Nmap] Discovered {f.schema_type}")

        # Verify host exists
        hosts = await store.query("network.host", session_id=session_id)
        print(f"   Current Graph: {len(hosts)} hosts")
        print(f"   Host Data: {hosts[0]['data_json']}")

        # 2. Run Whois against the SAME IP to test ENRICHMENT
        print(f"\n2. Running Whois against {target_ip} to enrich host...")
        whois = WhoisAdapter()
        async for f in executor.run_tool(whois, host_target, {}, session_id=session_id):
            print(f"   [Whois] Discovered {f.schema_type}")

        # Verify we still only have ONE host, but with more data
        hosts = await store.query("network.host", session_id=session_id)
        print(f"   Current Graph: {len(hosts)} hosts (Expect 1)")
        print(f"   Enriched Host Data: {hosts[0]['data_json']}")

        host_data = json.loads(hosts[0]['data_json'])
        assert len(hosts) == 1, "Should NOT have created a duplicate host"
        assert "organization" in host_data, "Host should now be enriched with organization data"

        # 3. Test DNS -> Host Association wiring...
        print("\n3. Testing DNS -> Host Association wiring...")
        dns_target = DnsRecord.create(domain="dns.google", record_type="A", value="8.8.8.8", resolved_ip="8.8.8.8")

        # Manually upsert this to see if it wires to the existing host
        await store.upsert_finding(session_id, dns_target)

        # Check edges
        async with store._get_conn() as db:
            db.row_factory = None
            cursor = await db.execute("SELECT * FROM edges WHERE session_id = ?", (session_id,))
            edges = await cursor.fetchall()
            print(f"   Edges found: {len(edges)}")
            for e in edges:
                print(f"   Edge: {e[1]} --({e[3]})--> {e[2]}")

        print("\n--- Enrichment Test Passed Successfully ---")
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
