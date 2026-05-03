import pytest
from pathlib import Path
import textwrap
from cyguide.engine.registry import ToolRegistry

def test_tool_registry_discovery(tmp_path):
    # Create a mock tool structure
    tool_dir = tmp_path / "mock_tool"
    tool_dir.mkdir()
    
    manifest_content = textwrap.dedent("""
        [meta]
        name = "mock_tool"
        description = "A mock tool for testing discovery"
        version = "1.0"
        categories = ["Testing"]
        binary = "echo"

        [modes]
        learning = true
        power = true

        [input]
        accepts = ["network.host"]

        [output]
        produces = ["network.service"]

        [learning]
        flags = []
        recipes = []
    """)
    (tool_dir / "manifest.toml").write_text(manifest_content)
    
    adapter_content = textwrap.dedent("""
        from typing import Dict, Any, AsyncIterator, List
        from cyguide.engine.adapter import ToolAdapter
        from cyguide.schemas.base import BaseFinding

        class MockAdapter(ToolAdapter):
            def validate_install(self) -> bool: return True
            def build_command(self, t, p) -> List[str]: return ["echo"]
            async def parse_output(self, o, t) -> AsyncIterator[BaseFinding]:
                if False: yield BaseFinding(pik={}, data={})
    """)
    (tool_dir / "adapter.py").write_text(adapter_content)
    
    registry = ToolRegistry(tools_dir=str(tmp_path))
    registry.load_tools()
    
    assert "mock_tool" in registry.list_tools()
    tool = registry.get_tool("mock_tool")
    assert tool["manifest"].meta.name == "mock_tool"
    assert tool["adapter"].__class__.__name__ == "MockAdapter"
    
    # Test filtering
    matches = registry.find_tools_for_input("network.host")
    assert "mock_tool" in matches
    
    matches_none = registry.find_tools_for_input("nonexistent")
    assert matches_none == []
