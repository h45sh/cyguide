"""Learning Mode logic and constraints."""

from typing import Dict, Any, List, Optional, AsyncIterator, Callable, Coroutine
from cyguide.engine.executor import Executor
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.explainer import LearningExplainer
from cyguide.schemas.base import BaseFinding


class LearningModeEngine:
    """
    Manages guided tool execution.
    Enforces manifest-defined parameters and provides explanations.
    """

    def __init__(self, registry: ToolRegistry, executor: Executor, explainer: LearningExplainer):
        self.registry = registry
        self.executor = executor
        self.explainer = explainer

    async def execute(
        self, 
        tool_name: str, 
        target: BaseFinding, 
        params: Dict[str, Any],
        session_id: Optional[str] = None,
        on_explanation: Optional[Callable[[str], Coroutine]] = None,
        on_output: Optional[Callable[[str], Coroutine]] = None
    ) -> AsyncIterator[BaseFinding]:
        """
        Execute a tool with learning mode constraints and yield findings.
        """
        tool_data = self.registry.get_tool(tool_name)
        if not tool_data:
            raise ValueError(f"Tool '{tool_name}' not found.")

        manifest = tool_data["manifest"]
        adapter = tool_data["adapter"]

        if not manifest.modes.get("learning"):
            raise ValueError(f"Tool '{tool_name}' does not support Learning Mode.")

        async def milestone_handler(trigger: str, data: Dict[str, Any]):
            if on_explanation:
                # Signal the UI that a new explanation is starting
                await on_explanation(f"\n\n[MILESTONE: {trigger.upper()}]\n")
                async for chunk in self.explainer.get_explanation(manifest, trigger, data):
                    await on_explanation(chunk)

        async for finding in self.executor.run_tool(
            adapter, target, params, 
            session_id=session_id, 
            on_milestone=milestone_handler,
            on_output=on_output
        ):
            yield finding

    def get_tool_explanation(self, tool_name: str) -> Optional[str]:
        """Get the tool's general description for learning."""
        tool_data = self.registry.get_tool(tool_name)
        if tool_data:
            return tool_data["manifest"].meta.description
        return None

    def get_parameter_explanations(self, tool_name: str) -> Dict[str, str]:
        """Return descriptions for each parameter allowed in learning mode."""
        tool_data = self.registry.get_tool(tool_name)
        if not tool_data or not tool_data["manifest"].learning:
            return {}
        
        explanations = {}
        for item in tool_data["manifest"].learning.flags:
            # We map the flag name (e.g. -sV) to its explanation
            # Note: UI might use descriptive keys instead of raw flags
            explanations[item["flag"]] = item["explanation"]
        return explanations
