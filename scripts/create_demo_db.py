import asyncio
import os
import json
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.web import WebEndpoint
from cyguide.schemas.power import ActionRequest

async def main():
    db_path = "assets/demo.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    store = GraphStore(db_path)
    await store.initialize()
    
    # 1. Create Workspaces
    ws_id = await store.create_workspace("Infrastructure Audit (Lab)")
    ws_ctf = await store.create_workspace("Cloud Penetration Test")
    
    # 2. Create Sessions
    sess_id = await store.create_session(ws_id, "Internal Recon & Discovery")
    sess_web = await store.create_session(ws_id, "Web API Assessment")
    
    # 3. Add Host Finding
    host_finding = NetworkHost.create(
        ip="10.0.0.45",
        hostname="edge-gateway.corp.internal",
        os="Linux 6.8 (Ubuntu 24.04)",
        tool="nmap"
    )
    await store.upsert_finding(sess_id, host_finding)
    
    # 4. Add Services
    services = [
        (22, "ssh", "OpenSSH 9.6p1 Ubuntu-3ubuntu13"),
        (80, "http", "nginx 1.24.0 (Ubuntu)"),
        (443, "https", "nginx 1.24.0 (TLSv1.3)"),
        (8080, "http-proxy", "Envoy Ingress Proxy 1.29"),
    ]
    for port, s_name, banner in services:
        svc = NetworkService.create(
            host_ip="10.0.0.45",
            port=port,
            protocol="tcp",
            service_name=s_name,
            banner=banner,
            tool="nmap"
        )
        await store.upsert_finding(sess_id, svc)
        
    # 5. Add Web Endpoints
    endpoints = [
        ("https://10.0.0.45:443/", 200, "Corporate Gateway"),
        ("https://10.0.0.45:443/api/v1/health", 200, "Healthy"),
        ("https://10.0.0.45:443/admin/login", 401, "Admin Console"),
    ]
    for url, status, title in endpoints:
        ep = WebEndpoint.create(
            url=url,
            status_code=status,
            tool="gobuster"
        )
        await store.upsert_finding(sess_id, ep)
        
    # 6. Action events
    req1 = ActionRequest(session_id=sess_id, tool_name="nmap", command_template="nmap -sV -Pn 10.0.0.45")
    await store.append_event(sess_id, req1, {"status": "success"}, "Run: nmap -sV -Pn 10.0.0.45")
    
    req2 = ActionRequest(session_id=sess_id, tool_name="gobuster", command_template="gobuster dir -u https://10.0.0.45:443 -w common.txt")
    await store.append_event(sess_id, req2, {"status": "success"}, "Run: gobuster dir -u https://10.0.0.45:443")
    
    await store.close()
    print("Demo DB successfully initialized at assets/demo.db")

if __name__ == "__main__":
    asyncio.run(main())
