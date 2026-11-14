"""Deep module managing Workspace and Session persistence, lifecycle, and forensic auditing."""

import logging
from typing import Any, Dict, List, Optional

from cyguide.engine.execution_session import ExecutionSession
from cyguide.engine.store import GraphStore

logger = logging.getLogger(__name__)


class WorkspaceRepository:
    """The deep module managing persistent lifecycle operations, entity indexing,

    forensic archiving, and portability for Workspaces and Sessions.
    """

    def __init__(self, store: GraphStore, execution: Optional[ExecutionSession] = None):
        self.store = store
        self.execution = execution

    # --- Workspace Operations ---

    async def create_workspace(self, name: str) -> str:
        """Create a new workspace, ensuring its name is unique (case-insensitive)."""
        existing = await self.store.list_workspaces()
        if any(ws["name"].strip().lower() == name.strip().lower() for ws in existing):
            raise ValueError("Workspace with this name already exists.")
        return await self.store.create_workspace(name)

    async def rename_workspace(self, workspace_id: str, new_name: str) -> None:
        """Rename a workspace, ensuring the new name is unique."""
        existing = await self.store.list_workspaces()
        if any(
            ws["name"].strip().lower() == new_name.strip().lower() and ws["id"] != workspace_id
            for ws in existing
        ):
            raise ValueError("Workspace with this name already exists.")
        await self.store.rename_workspace(workspace_id, new_name)

    async def delete_workspace(self, workspace_id: str) -> None:
        """Clean up active execution jobs for all sessions in the workspace, then delete it."""
        sessions = await self.store.list_sessions(workspace_id)
        session_ids = {s["id"] for s in sessions}

        if self.execution:
            await self.execution.evict_sessions(session_ids)

        await self.store.delete_workspace(workspace_id)

    async def close_workspace(self, workspace_id: str) -> None:
        """Close all sessions in the workspace and close the workspace."""
        sessions = await self.store.list_sessions(workspace_id)
        for s in sessions:
            if s.get("status") != "CLOSED":
                await self.close_session(s["id"])
        await self.store.close_workspace(workspace_id)

    async def reopen_workspace(self, workspace_id: str) -> None:
        """Reopen a closed workspace."""
        await self.store.reopen_workspace(workspace_id)

    async def list_workspaces(self, status_filter: Optional[str] = None) -> List[Dict]:
        """List all workspaces, optionally filtered by status ('ACTIVE' or 'CLOSED')."""
        return await self.store.list_workspaces(status_filter=status_filter)

    async def get_workspace(self, workspace_id: str) -> Optional[Dict]:
        """Fetch workspace metadata by ID."""
        return await self.store.get_workspace(workspace_id)

    # --- Session Operations ---

    async def create_session(self, workspace_id: str, name: Optional[str] = None) -> str:
        """Create a new session, ensuring its name is unique in this workspace."""
        final_name = (name or "New Investigation").strip()
        existing = await self.store.list_sessions(workspace_id)
        if any(s["name"].strip().lower() == final_name.lower() for s in existing):
            raise ValueError("Session with this name already exists in this workspace.")
        return await self.store.create_session(workspace_id, final_name)

    async def rename_session(self, session_id: str, new_name: str) -> None:
        """Rename a session, ensuring its new name is unique in its workspace."""
        session = await self.store.get_session(session_id)
        if not session:
            raise ValueError("Session not found.")
        workspace_id = session["workspace_id"]
        existing = await self.store.list_sessions(workspace_id)
        if any(
            s["name"].strip().lower() == new_name.strip().lower() and s["id"] != session_id
            for s in existing
        ):
            raise ValueError("Session with this name already exists in this workspace.")
        await self.store.rename_session(session_id, new_name)

    async def delete_session(self, session_id: str) -> None:
        """Clean up active execution jobs for the session, then delete it."""
        if self.execution:
            await self.execution.evict_session(session_id)

        await self.store.delete_session(session_id)

    async def close_session(self, session_id: str) -> None:
        """Archive a session and log the closure."""
        await self.store.close_session(session_id)
        await self.store.log_audit_event(
            session_id,
            "session_closed",
            "Session archived/closed (forensic audit preserved).",
            "CLOSED",
        )

    async def reopen_session(self, session_id: str) -> None:
        """Reopen an archived session back to ACTIVE."""
        await self.store.reopen_session(session_id)
        await self.store.log_audit_event(
            session_id, "session_reopened", "Session reopened to ACTIVE status.", "ACTIVE"
        )

    async def move_session(self, session_id: str, target_workspace_id: str) -> None:
        """Move a session to another workspace, ensuring no name collision."""
        session = await self.store.get_session(session_id)
        if not session:
            raise ValueError("Session not found.")
        existing = await self.store.list_sessions(target_workspace_id)
        if any(s["name"].strip().lower() == session["name"].strip().lower() for s in existing):
            raise ValueError("A session with this name already exists in the target workspace.")
        await self.store.move_session(session_id, target_workspace_id)

    async def move_sessions(
        self, session_ids: List[str], target_workspace_id: str
    ) -> Dict[str, Any]:
        """Move multiple sessions to a target workspace with collision checks and validation."""
        target_ws = await self.store.get_workspace(target_workspace_id)
        if not target_ws:
            raise ValueError("Target workspace not found.")

        existing = await self.store.list_sessions(target_workspace_id)
        existing_names = {s["name"].strip().lower() for s in existing}

        moved: List[str] = []
        errors: List[str] = []

        for sid in session_ids:
            session = await self.store.get_session(sid)
            if not session:
                errors.append(f"Session {sid} not found.")
                continue
            sess_name_lower = session["name"].strip().lower()
            if sess_name_lower in existing_names:
                errors.append(f"Session '{session['name']}' already exists in target workspace.")
                continue
            await self.store.move_session(sid, target_workspace_id)
            existing_names.add(sess_name_lower)
            moved.append(sid)

        return {"moved": moved, "errors": errors}

    async def batch_delete(
        self, workspace_ids: List[str], session_ids: List[str]
    ) -> Dict[str, Any]:
        """Atomically delete multiple workspaces and sessions, safeguarding SYSTEM workspaces."""
        deleted_workspaces: List[str] = []
        skipped_system: List[str] = []
        deleted_sessions: List[str] = []

        # 1. Process workspaces with SYSTEM guard
        for wid in workspace_ids:
            ws = await self.store.get_workspace(wid)
            if not ws:
                continue
            if ws.get("status") == "SYSTEM":
                skipped_system.append(ws["name"])
                continue
            await self.delete_workspace(wid)
            deleted_workspaces.append(wid)

        # 2. Process sessions (excluding sessions belonging to already deleted workspaces)
        for sid in session_ids:
            sess = await self.store.get_session(sid)
            if not sess:
                continue
            await self.delete_session(sid)
            deleted_sessions.append(sid)

        return {
            "deleted_workspaces": deleted_workspaces,
            "skipped_system_workspaces": skipped_system,
            "deleted_sessions": deleted_sessions,
        }

    async def list_sessions(
        self, workspace_id: str, status_filter: Optional[str] = None
    ) -> List[Dict]:
        """List sessions within a workspace, optionally filtered by status."""
        return await self.store.list_sessions(workspace_id, status_filter=status_filter)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Fetch session metadata by ID."""
        return await self.store.get_session(session_id)

    # --- Entity & Graph Data Queries ---

    async def set_entity_alias(self, session_id: str, node_id: str, alias: str) -> None:
        """Set a user-defined friendly name or alias for an entity node."""
        await self.store.update_node_data(session_id, node_id, {"alias": alias.strip()})

    async def get_node(self, session_id: str, node_id: str) -> Optional[Dict]:
        """Fetch a specific node by ID."""
        return await self.store.get_node(session_id, node_id)

    async def get_all_nodes(self, session_id: str) -> List[Dict]:
        """Fetch all nodes for a session."""
        return await self.store.get_all_nodes(session_id)

    async def get_all_edges(self, session_id: str) -> List[Dict]:
        """Fetch all edges for a session."""
        return await self.store.get_all_edges(session_id)

    async def get_stats(
        self, session_id: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get aggregate node and vulnerability counts."""
        return await self.store.get_stats(session_id=session_id, workspace_id=workspace_id)

    async def get_recent_activity(self, workspace_id: str, limit: int = 5) -> List[Dict]:
        """Fetch recent findings across all sessions in a workspace."""
        return await self.store.get_recent_activity(workspace_id, limit=limit)

    # --- Export / Import ---

    async def export_session(self, session_id: str, dest_db_path: str) -> None:
        """Export a session's database rows to a portable database."""
        await self.store.export_session(session_id, dest_db_path)

    async def export_markdown_report(self, session_id: str, dest_path: str) -> None:
        """Export a session's finding summary and logs to a hardened Markdown report file."""
        from cyguide.engine.reporter import export_markdown_report

        await export_markdown_report(self.store, session_id, dest_path)

    async def import_session(
        self, src_db_path: str, target_workspace_id: Optional[str] = None
    ) -> str:
        """Import a session from an exported database."""
        return await self.store.import_session(src_db_path, target_workspace_id)
