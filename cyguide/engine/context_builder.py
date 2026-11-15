"""Deep module assembling workspace execution context, target entity variables, and operator environment."""

import json
from typing import Optional
from uuid import UUID

from cyguide.engine.execution_session import ExecutionSession
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.store import GraphStore
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import WorkspaceContext


class WorkspaceContextBuilder:
    """The deep module responsible for compiling point-in-time snapshots of investigation

    context, resolving target entity variables, operator LHOST networking, and active job status.
    """

    def __init__(self, store: GraphStore, execution: ExecutionSession):
        self.store = store
        self.execution = execution

    async def build(
        self, session_id: str, selected_entity_id: Optional[str] = None
    ) -> WorkspaceContext:
        """Build a point-in-time snapshot of the workspace context for a session."""
        session_data = await self.store.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found.")

        # 1. Resolve selected entity and variables
        selected_entity = None
        pik = None
        if selected_entity_id:
            node_data = await self.store.get_node(session_id, selected_entity_id)
            if node_data:
                pik = json.loads(node_data["pik_json"])
                selected_entity = BaseFinding(
                    schema_type=node_data["schema_type"],
                    pik=pik,
                    data=json.loads(node_data["data_json"]),
                    status=node_data.get("status", "confirmed"),
                )

        resolved_vars = ActionGateway.resolve_entity_variables(pik)

        # 2. Aggregate counts and jobs
        stats = await self.store.get_stats(session_id)

        workspace_id = session_data["workspace_id"]
        workspace_sessions = await self.store.list_sessions(workspace_id)
        workspace_session_ids = {s["id"] for s in workspace_sessions}

        active_jobs = [
            j
            for j in self.execution.get_active_jobs()
            if str(j.session_id) in workspace_session_ids
        ]

        return WorkspaceContext(
            session_id=UUID(session_id),
            session_name=session_data["name"],
            selected_entity=selected_entity,
            resolved_vars=resolved_vars,
            active_jobs=active_jobs,
            entity_counts=stats,
            cwd=self.execution.get_cwd(session_id),
        )
