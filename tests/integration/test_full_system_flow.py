import pytest
import asyncio
import os
import sys
import stat
from pathlib import Path
from unittest.mock import patch

from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from cyguide.schemas.network import NetworkHost
from tools.nmap.adapter import NmapAdapter

MOCK_NMAP_CONTENT = """#!/usr/bin/env python3
print("Starting Nmap 7.94 ( https://nmap.org )")
print("PORT     STATE SERVICE")
print("80/tcp   open  http")
print("443/tcp  open  https")
"""

@pytest.mark.asyncio
async def test_full_executor_nmap_flow(tmp_path):
    """
    Real integration test that spawns a process, parses it, and saves to DB.
    """
    # 1. Setup mock nmap executable
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mock_nmap = bin_dir / "nmap"
    mock_nmap.write_text(MOCK_NMAP_CONTENT)
    mock_nmap.chmod(mock_nmap.stat().st_mode | stat.S_IEXEC)
    
    # Add our mock bin to PATH
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    
    # 2. Setup System
    db_path = tmp_path / "test.db"
    store = GraphStore(str(db_path))
    await store.initialize()
    
    # Create session
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    
    executor = Executor(store)
    adapter = NmapAdapter()
    
    target = NetworkHost.create(ip="127.0.0.1")
    
    # 3. Run tool (in an environment where 'nmap' is our mock)
    with patch.dict(os.environ, env):
        findings = []
        async for finding in executor.run_tool(
            adapter, 
            target, 
            params={}, 
            session_id=session_id
        ):
            findings.append(finding)

    # 4. Verify results
    assert len(findings) == 2
    assert findings[0].schema_type == "network.service"
    assert findings[0].data["port"] == 80
    assert findings[1].data["port"] == 443
    
    # Verify DB persistence
    db_findings = await store.query("network.service", session_id=session_id)
    assert len(db_findings) == 2
    
    await store.close()
