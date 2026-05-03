import pytest
from cyguide.modes.power import PowerModeEngine
from cyguide.modes.learning import LearningModeEngine
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.executor import Executor
from cyguide.engine.store import GraphStore
from cyguide.engine.manifest import Manifest
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
async def test_power_mode_execution(mock_registry):
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    engine = PowerModeEngine(mock_registry, executor)
    
    target = NetworkHost.create(ip="1.1.1.1")
    
    findings = []
    async for f in engine.execute("mock_tool", target, {"hostname": "power-host"}, session_id=session_id):
        findings.append(f)
        
    assert len(findings) == 1
    assert findings[0].data["hostname"] == "power-host"
    await store.close()

@pytest.mark.asyncio
async def test_learning_mode_execution(mock_registry):
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id, session_id = await store.get_or_create_learning_sandbox()
    executor = Executor(store)
    # Mocking LearningExplainer
    from cyguide.engine.explainer import LearningExplainer
    explainer = LearningExplainer(None) # None api_key
    
    engine = LearningModeEngine(mock_registry, executor, explainer)
    
    target = NetworkHost.create(ip="2.2.2.2")
    
    findings = []
    async for f in engine.execute("mock_tool", target, {}, session_id=session_id):
        findings.append(f)
        
    assert len(findings) == 1
    assert findings[0].pik["ip"] == "8.8.8.8" # From MockSimpleAdapter
    await store.close()

def test_power_mode_suggestions(mock_registry):
    engine = PowerModeEngine(mock_registry, None)
    finding = NetworkHost.create(ip="1.2.3.4")
    suggestions = engine.suggest_next_tools(finding)
    assert "mock_tool" in suggestions
