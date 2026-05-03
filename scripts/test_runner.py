"""Standalone test script to verify the executor -> adapter -> store pipeline."""

import asyncio
import json
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from tools.nmap.adapter import NmapAdapter
from cyguide.schemas.network import NetworkHost

async def main():
    print("--- Step 1: Testing Runner in Isolation ---")
    
    # 1. Setup in-memory store
    store = GraphStore(":memory:")
    await store.initialize()
    
    try:
        # 2. Register a callback to verify reactivity (Pre-Step 2 check)
        def sync_callback(session_id, finding):
            print(f"  [Callback] New finding: {finding.schema_type}")

        async def async_callback(session_id, finding):
            print(f"  [Async Callback] Registered {finding.schema_type} in {session_id}")

        store.on_upsert(async_callback)

        # 3. Initialize Adapter and Executor
        adapter = NmapAdapter()
        if not adapter.validate_install():
            print("Error: nmap not found on PATH. Please install nmap to run this test.")
            return
            
        executor = Executor(store)
        
        # 4. Create a target finding (network.host)
        target_ip = "127.0.0.1"
        target = NetworkHost.create(ip=target_ip)
        session_id = "test-session-123"
        
        print(f"Running nmap against {target_ip}...")
        
        # 5. Run the tool and process findings as they arrive
        findings_count = 0
        async for finding in executor.run_tool(adapter, target, params={"service_version": True}, session_id=session_id):
            findings_count += 1
            print(f"  [{finding.schema_type}] {finding.pik}")

        print(f"\nExecution complete. Found {findings_count} findings.")

        # 6. Verify Graph Store state
        hosts = await store.query("network.host", session_id=session_id)
        services = await store.query("network.service", session_id=session_id)
        
        print(f"\n--- Graph State (Session: {session_id}) ---")
        print(f"Hosts: {len(hosts)}")
        for h in hosts:
            print(f"  - {h['pik_json']}")
            
        print(f"Services: {len(services)}")
        for s in services:
            data = json.loads(s['data_json'])
            print(f"  - {s['pik_json']} (Service: {data.get('service_name')})")
        
        # 7. Verify Event Log
        events = await store.get_event_log(session_id)
        print(f"\nEvent Log: {len(events)} entries")
        
        assert len(hosts) >= 1, "Should have at least one host"
        assert len(events) == findings_count, "Event log count should match findings count"
        
        print("\n--- Test Passed Successfully ---")
    finally:
        await store.close()

if __name__ == "__main__":
    asyncio.run(main())
