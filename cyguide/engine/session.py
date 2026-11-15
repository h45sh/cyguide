"""InvestigationSession: Core seam defining investigation runtime lifecycles."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Tuple, runtime_checkable
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
