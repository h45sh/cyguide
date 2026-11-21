"""InvestigationSession: Core seam defining investigation runtime lifecycles."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable
from uuid import UUID

from cyguide.engine.execution_session import ExecutionSession
from cyguide.engine.explainer import ExplanationTutor
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore


@runtime_checkable
class InvestigationSession(Protocol):
    """Core seam governing investigation runtime environments (Learning & Power)."""

    session_id: Optional[UUID]
    workspace_id: Optional[UUID]
    store: Optional[GraphStore]
    registry: Optional[ToolRegistry]
    execution: Optional[ExecutionSession]
    explainer: Optional[ExplanationTutor]

    async def extract_structured_findings(
        self,
        store: Optional[GraphStore] = None,
        session_id: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """Format discovered graph findings for UI display and AI context."""
        ...

    def verify_preflight(
        self,
        tool_name: str,
        target: str,
        flags: str = "",
        recipe_idx: Optional[int] = None,
    ) -> Any:
        """Validate tool installation, target semantics, and argument safety before execution."""
        ...

    async def get_graph_snapshot(self, session_id: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Fetch confirmed entity nodes and relational edges for the investigation."""
        ...

    async def get_notes(self, session_id: Optional[str] = None) -> str:
        """Fetch persistent notes for the investigation."""
        ...

    async def save_notes(self, content: str, session_id: Optional[str] = None) -> None:
        """Persist operator notes for the investigation."""
        ...
