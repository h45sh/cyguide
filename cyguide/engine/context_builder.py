"""Deep module assembling workspace execution context, target entity variables, and operator environment."""

import json
from typing import Optional
from uuid import UUID

from cyguide.engine.execution_session import ExecutionSession
from cyguide.engine.network import get_lhost_info
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
        resolved_vars = {}
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

                # Context Resolution Logic
                resolved_vars["TARGET"] = pik.get("ip") or pik.get("domain") or pik.get("host_ip")
                if "port" in pik:
                    resolved_vars["PORT"] = pik["port"]
                if "service" in pik:
                    resolved_vars["SERVICE"] = pik["service"]
                if "protocol" in pik:
                    resolved_vars["PROTOCOL"] = pik["protocol"]

        # Operator context resolution: Always resolve LHOST
        try:
            import sys

            pf = sys.modules.get("cyguide.engine.power_facade")
            resolver = getattr(pf, "get_lhost_info", get_lhost_info) if pf else get_lhost_info
            lhost_ip, _ = resolver()
            if lhost_ip:
                resolved_vars["LHOST"] = lhost_ip
        except Exception:
            pass

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
