"""Learning Mode logic and constraints."""

from typing import Any, AsyncIterator, Callable, Coroutine, Dict, Optional

from cyguide.engine.executor import Executor
from cyguide.engine.explainer import LearningExplainer
from cyguide.engine.registry import ToolRegistry
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

        async for finding in self.executor.run_tool(
            adapter, target, params,
            session_id=session_id,
            on_output=on_output
        ):
            yield finding

