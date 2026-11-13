# codeguard: ignore-file[DEBUG_PYTHON_PRINT, TEST_FLAKY_SLEEP]
import asyncio
import os
import stat
from unittest.mock import patch

import pytest

from cyguide.engine.executor import Executor
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost
from tools.nmap.adapter import NmapAdapter

MOCK_NMAP_CONTENT = """#!/usr/bin/env python3
import sys
import time

print("Starting Nmap 7.94 ( https://nmap.org )")
print("PORT     STATE SERVICE")
print("80/tcp   open  http")
print("443/tcp  open  https")
sys.stdout.flush()
"""

MOCK_STDERR_TOOL_CONTENT = """#!/usr/bin/env python3
import sys
print("Diagnostic warning: target responds slowly", file=sys.stderr)
print("8080/tcp open http-proxy")
sys.stderr.flush()
sys.stdout.flush()
"""

MOCK_LONG_RUNNING_CONTENT = """#!/usr/bin/env python3
import time
import sys
print("Running long task...", flush=True)
time.sleep(10)
print("Finished long task.", flush=True)
"""


@pytest.mark.asyncio
async def test_full_executor_nmap_flow(tmp_path):
    """
    Integration test: Spawns real OS process, streams stdout chunks, parses findings, and saves to DB.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mock_nmap = bin_dir / "nmap"
    mock_nmap.write_text(MOCK_NMAP_CONTENT)
    mock_nmap.chmod(mock_nmap.stat().st_mode | stat.S_IEXEC)
    
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    
    db_path = tmp_path / "test.db"
    store = GraphStore(str(db_path))
    await store.initialize()
    
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    adapter = NmapAdapter()
    target = NetworkHost.create(ip="127.0.0.1")
    
    received_lines = []
    async def on_output(line: str):
        received_lines.append(line)

    with patch.dict(os.environ, env):
        findings = []
        async for finding in executor.run_tool(
            adapter, 
            target, 
            params={}, 
            session_id=session_id,
            on_output=on_output
        ):
            findings.append(finding)
            await store.upsert_finding(session_id, finding)

    assert len(findings) == 2
    assert findings[0].schema_type == "network.service"
    assert findings[0].data["port"] == 80
    assert findings[1].data["port"] == 443
    assert len(received_lines) > 0

    # Verify DB persistence
    db_findings = await store.query("network.service", session_id=session_id)
    assert len(db_findings) == 2
    
    await store.close()


@pytest.mark.asyncio
async def test_executor_stderr_streaming(tmp_path):
    """
    Integration test: Verifies that stderr streams to on_error_output callback independently from stdout.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mock_tool = bin_dir / "nmap"
    mock_tool.write_text(MOCK_STDERR_TOOL_CONTENT)
    mock_tool.chmod(mock_tool.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    adapter = NmapAdapter()
    target = NetworkHost.create(ip="127.0.0.1")

    stdout_chunks = []
    stderr_chunks = []

    async def on_stdout(chunk: str):
        stdout_chunks.append(chunk)

    async def on_stderr(chunk: str):
        stderr_chunks.append(chunk)

    with patch.dict(os.environ, env):
        findings = []
        async for f in executor.run_tool(
            adapter,
            target,
            params={},
            session_id=session_id,
            on_output=on_stdout,
            on_error_output=on_stderr
        ):
            findings.append(f)

    assert len(findings) == 1
    assert any("Diagnostic warning" in c for c in stderr_chunks)
    assert any("8080/tcp open" in c for c in stdout_chunks)
    await store.close()


@pytest.mark.asyncio
async def test_executor_stop_task_cancellation(tmp_path):
    """
    Integration test: Verifies stopping an active long-running task terminates the OS process.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mock_long = bin_dir / "nmap"
    mock_long.write_text(MOCK_LONG_RUNNING_CONTENT)
    mock_long.chmod(mock_long.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    adapter = NmapAdapter()
    target = NetworkHost.create(ip="127.0.0.1")

    task_id = "test_task_cancellation"

    async def run_in_bg():
        findings = []
        with patch.dict(os.environ, env):
            async for f in executor.run_tool(adapter, target, {}, task_id=task_id, session_id=session_id):
                findings.append(f)
        return findings

    bg_task = asyncio.create_task(run_in_bg())
    await asyncio.sleep(0.1) # Let process start

    # Stop task
    assert task_id in executor._active_processes
    await executor.stop_task(task_id)

    # Process should be terminated quickly
    await asyncio.wait_for(bg_task, timeout=2.0)
    assert task_id not in executor._active_processes
    await store.close()
