"""Power Mode logic and workflow orchestration."""

from typing import Dict, Any, List, Optional, AsyncIterator
from cyguide.engine.executor import Executor
from cyguide.engine.registry import ToolRegistry
from cyguide.schemas.base import BaseFinding


class PowerModeEngine:
    """
    Manages flexible, multi-tool workflows.
    Allows for tool chaining based on emitted findings.
    """

    def __init__(self, registry: ToolRegistry, executor: Executor):
        self.registry = registry
        self.executor = executor

    async def execute(
        self, 
        tool_name: str, 
        target: BaseFinding, 
        params: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> AsyncIterator[BaseFinding]:
        """Execute a tool in Power Mode and persist to session graph."""
        tool_data = self.registry.get_tool(tool_name)
        if not tool_data:
            raise ValueError(f"Tool '{tool_name}' not found.")

        adapter = tool_data["adapter"]
        async for finding in self.executor.run_tool(adapter, target, params, session_id=session_id):
            yield finding

    def suggest_next_tools(self, finding: BaseFinding) -> List[str]:
        """
        Suggest tools based on a finding's schema type and data.
        This implements 'Declarative Filtering' from the manifest.
        """
        # 1. Basic suggestion based on input schema compatibility
        suggestions = self.registry.find_tools_for_input(finding.schema_type)
        
        # 2. Advanced: Logic for manifest-defined suggestions based on data
        # (e.g., suggest 'gobuster' if 'port: 80' is found)
        # TODO: Implement complex filtering logic from manifest.power.suggests
        
        return suggestions
