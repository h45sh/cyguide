"""Power Mode legacy workflow orchestration.

NOTE: For active Power Mode session management, variable resolution, and gateway policies,
use `cyguide.engine.power_facade.PowerWorkspaceFacade`. This class is maintained for backwards
compatibility with basic tool chaining and legacy test fixtures.
"""

from typing import Dict, Any, List, Optional, AsyncIterator
from cyguide.engine.executor import Executor
from cyguide.engine.registry import ToolRegistry
from cyguide.schemas.base import BaseFinding


class PowerModeEngine:
    """
    Legacy workflow orchestration helper.
    Maintained for backwards compatibility. Prefer PowerWorkspaceFacade for new code.
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

        # 2. Advanced: Complex graph-reactive suggestions are handled by
        # RecommendationEngine in cyguide/engine/recommendation.py.
        # This helper remains for basic input schema compatibility queries.
        return suggestions
