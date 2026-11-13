"""Unit tests verifying tool execution pipeline behavior for guided Learning Mode."""

import pytest

from cyguide.engine.executor import Executor
from cyguide.engine.manifest import Manifest
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost
from tests.fixtures.mock_tools import MockSimpleAdapter


@pytest.fixture
def mock_registry():
    registry = ToolRegistry()
    # Manually register a mock tool
    manifest_data = {
        "meta": {
            "name": "mock_tool", 
            "description": "A mock tool", 
            "version": "1.0",
            "categories": ["Scanning"],
            "binary": "echo"
        },
        "modes": {"learning": True, "power": True},
        "input": {"accepts": ["network.host"]},
        "output": {"produces": ["network.service"]},
        "learning": {
            "flags": [{"flag": "-v", "explanation": "Verbose"}],
            "recipes": []
        }
    }
    registry.tools["mock_tool"] = {
        "manifest": Manifest(**manifest_data),
        "adapter": MockSimpleAdapter()
    }
    return registry

@pytest.mark.asyncio
async def test_learning_mode_execution(mock_registry):
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    
    tool_data = mock_registry.get_tool("mock_tool")
    adapter = tool_data["adapter"]
    target = NetworkHost.create(ip="2.2.2.2")
    
    findings = []
    async for f in executor.run_tool(adapter, target, {}, session_id=session_id):
        findings.append(f)
        
    assert len(findings) == 1
    assert findings[0].pik["ip"] == "8.8.8.8" # From MockSimpleAdapter
    await store.close()
