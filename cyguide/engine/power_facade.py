"""Coordination layer for Power Mode investigation sessions."""

import asyncio
import os
from typing import Any, AsyncIterator, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.context_builder import WorkspaceContextBuilder
from cyguide.engine.execution_session import (
    CommandRunner,
    ExecutionEvent,
    ExecutionSession,
    SubprocessCommandRunner,
    TerminalSuspendContext,
)
from cyguide.engine.executor import Executor, sanitize_subprocess_env
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.network import get_lhost_info
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.engine.workspace_repository import WorkspaceRepository
from cyguide.paths import get_action_log_path
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest, JobStatus, JobStatusEnum, WorkspaceContext

__all__ = ["PowerWorkspaceFacade", "ShellAdapter", "get_lhost_info"]


class ShellAdapter(ToolAdapter):
    """Adapter for explicit shell commands (prefix '!')."""

    def validate_install(self) -> bool:
        return True

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        import shlex

        return shlex.split(params.get("raw_flags", ""))

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        return
        yield


class PowerWorkspaceFacade:
    """The central coordination layer for Power Mode.

    This is the primary API for the TUI and future agents. It orchestrates
    sessions, validates actions, manages tool execution, and builds workspace context.
    """

    def __init__(
        self,
        store: GraphStore,
        executor: Executor,
        registry: ToolRegistry,
        command_runner: Optional[CommandRunner] = None,
    ):
        self._store = store
        self.executor = executor
        self.registry = registry
        self.gateway = ActionGateway(registry, store)

        # Injected or default CommandRunner for ExecutionSession
        self.runner = command_runner or SubprocessCommandRunner(executor)
        self.execution = ExecutionSession(
            store=self._store,
            gateway=self.gateway,
            registry=self.registry,
            command_runner=self.runner,
            user_env=sanitize_subprocess_env(getattr(self, "user_env", os.environ.copy())),
            user_shell=getattr(self, "user_shell", "/bin/bash"),
        )
        self.workspaces = WorkspaceRepository(self._store, self.execution)
        self.context_builder = WorkspaceContextBuilder(self._store, self.execution)

        # Global status change listeners
        self._job_change_listeners: List[Callable] = []
        self.execution.add_status_listener(self._notify_job_change)

        # Callback subscribers for output chunks (job_id -> set of callbacks)
        self._output_subscribers: Dict[UUID, set] = {}

    @property
    def store(self) -> GraphStore:
        return self._store

    @store.setter
    def store(self, new_store: GraphStore) -> None:
        self._store = new_store
        if hasattr(self, "workspaces"):
            self.workspaces.store = new_store
        if hasattr(self, "execution"):
            self.execution.store = new_store
        if hasattr(self, "gateway"):
            self.gateway.store = new_store
        if hasattr(self, "context_builder"):
            self.context_builder.store = new_store

    @property
    def _active_jobs(self) -> Dict[UUID, JobStatus]:
        return self.execution._active_jobs

    @property
    def _job_actions(self) -> Dict[UUID, ActionRequest]:
        return self.execution._job_actions

    @property
    def _job_subscribers(self) -> Dict[UUID, set]:
        return self._output_subscribers

    @property
    def _job_buffers(self) -> Dict[UUID, List[str]]:
        return self.execution._job_buffers

    @property
    def _session_cwd(self) -> Dict[str, str]:
        return self.execution._session_cwd

    @property
    def closed_job_ids(self) -> set[str]:
        return self.execution.closed_job_ids

    @property
    def _running_tasks(self) -> Dict[UUID, asyncio.Task]:
        return self.execution._running_tasks

    def _get_cwd(self, session_id: str) -> str:
        return self.execution.get_cwd(session_id)

    def get_running_task(self, job_id: UUID) -> Optional[asyncio.Task]:
        """Retrieve background execution task for a job by UUID."""
        return self.execution.get_running_task(job_id)

    async def create_workspace(self, name: str) -> str:
        """Create a new workspace, ensuring its name is unique (case-insensitive)."""
        return await self.workspaces.create_workspace(name)

    async def rename_workspace(self, workspace_id: str, new_name: str) -> None:
        """Rename a workspace, ensuring the new name is unique."""
        await self.workspaces.rename_workspace(workspace_id, new_name)

    async def create_session(self, workspace_id: str, name: Optional[str] = None) -> str:
        """Create a new session, ensuring its name is unique in this workspace."""
        return await self.workspaces.create_session(workspace_id, name)

    async def rename_session(self, session_id: str, new_name: str) -> None:
        """Rename a session, ensuring its new name is unique in its workspace."""
        await self.workspaces.rename_session(session_id, new_name)

    async def set_entity_alias(self, session_id: str, node_id: str, alias: str) -> None:
        """Set a user-defined friendly name or alias for an entity node."""
        await self.workspaces.set_entity_alias(session_id, node_id, alias)

    async def move_session(self, session_id: str, target_workspace_id: str) -> None:
        """Move a session to another workspace, ensuring no name collision."""
        await self.workspaces.move_session(session_id, target_workspace_id)

    async def delete_session(self, session_id: str) -> None:
        """Clean up active jobs for the session, then delete it."""
        await self.workspaces.delete_session(session_id)

    async def delete_workspace(self, workspace_id: str) -> None:
        """Clean up active jobs for all sessions in the workspace, then delete it."""
        await self.workspaces.delete_workspace(workspace_id)

    async def close_session(self, session_id: str) -> None:
        """Archive a session and log the closure."""
        await self.workspaces.close_session(session_id)

    async def reopen_session(self, session_id: str) -> None:
        """Reopen an archived session back to ACTIVE."""
        await self.workspaces.reopen_session(session_id)

    async def close_workspace(self, workspace_id: str) -> None:
        """Close all sessions in the workspace and close the workspace."""
        await self.workspaces.close_workspace(workspace_id)

    async def reopen_workspace(self, workspace_id: str) -> None:
        """Reopen a closed workspace."""
        await self.workspaces.reopen_workspace(workspace_id)

    async def list_workspaces(self, status_filter: Optional[str] = None) -> List[Dict]:
        """List all workspaces, optionally filtered by status ('ACTIVE' or 'CLOSED')."""
        return await self.workspaces.list_workspaces(status_filter=status_filter)

    async def get_workspace(self, workspace_id: str) -> Optional[Dict]:
        """Fetch workspace metadata by ID."""
        return await self.workspaces.get_workspace(workspace_id)

    async def list_sessions(
        self, workspace_id: str, status_filter: Optional[str] = None
    ) -> List[Dict]:
        """List sessions within a workspace, optionally filtered by status."""
        return await self.workspaces.list_sessions(workspace_id, status_filter=status_filter)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Fetch session metadata by ID."""
        return await self.workspaces.get_session(session_id)

    async def get_node(self, session_id: str, node_id: str) -> Optional[Dict]:
        """Fetch a specific node by ID."""
        return await self.workspaces.get_node(session_id, node_id)

    async def get_all_nodes(self, session_id: str) -> List[Dict]:
        """Fetch all nodes for a session."""
        return await self.workspaces.get_all_nodes(session_id)

    async def get_all_edges(self, session_id: str) -> List[Dict]:
        """Fetch all edges for a session."""
        return await self.workspaces.get_all_edges(session_id)

    async def get_stats(
        self, session_id: Optional[str] = None, workspace_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get aggregate node and vulnerability counts."""
        return await self.workspaces.get_stats(session_id=session_id, workspace_id=workspace_id)

    async def get_recent_activity(self, workspace_id: str, limit: int = 5) -> List[Dict]:
        """Get recent activity audit events for a workspace."""
        return await self.workspaces.get_recent_activity(workspace_id, limit=limit)

    async def get_closed_events_count(self, session_id: str) -> int:
        """Count closed tool execution events for a session."""
        return await self.store.get_closed_events_count(session_id)

    def on_finding_upsert(self, callback: Any) -> None:
        """Register a callback for finding upserts."""
        self.store.on_upsert(callback)

    async def get_report_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch structured session audit and findings data bundle for reporting."""
        from cyguide.engine.reporter import fetch_report_data

        return await fetch_report_data(self.store, session_id)

    async def generate_markdown_report(self, session_id: str) -> str:
        """Generate markdown report string for a session."""
        from cyguide.engine.reporter import generate_markdown_report

        return await generate_markdown_report(self.store, session_id)

    async def submit_action(
        self,
        action: ActionRequest,
        on_output: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error_output: Optional[Callable] = None,
        suspend_context: Optional[TerminalSuspendContext] = None,
    ) -> UUID:
        """Validate and execute a tool action via ExecutionSession deep module."""

        async def handle_chunk(text: str) -> None:
            if on_output:
                try:
                    res = on_output(text)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
            for sub in list(self._output_subscribers.get(action.action_id, set())):
                try:
                    res = sub(text)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass

        return await self.execution.dispatch(
            action=action,
            suspend_context=suspend_context,
            on_chunk=handle_chunk,
            on_complete=on_complete,
        )

    def subscribe_events(self, action_id: UUID) -> AsyncIterator[ExecutionEvent]:
        """Subscribe to live typed execution events from ExecutionSession."""
        return self.execution.subscribe(action_id)

    async def shutdown(self) -> None:
        """Cancel and drain all running action tasks before store closes."""
        await self.execution.shutdown()

    async def kill_job(self, job_id: UUID) -> bool:
        """Terminate a running job."""
        return await self.execution.kill_job(job_id)

    async def get_context(
        self, session_id: str, selected_entity_id: Optional[str] = None
    ) -> WorkspaceContext:
        """Build a point-in-time snapshot of the workspace context."""
        return await self.context_builder.build(session_id, selected_entity_id)

    async def get_session_events(self, session_id: str) -> List[Dict]:
        return await self.store.get_event_log(session_id)

    async def get_graph_snapshot(self, session_id: str) -> Dict[str, List[Dict]]:
        """Returns all confirmed nodes and edges for the session."""
        nodes = await self.store.get_all_nodes(session_id)
        edges = await self.store.get_all_edges(session_id)
        confirmed_nodes = [n for n in nodes if n.get("status") == "confirmed"]
        return {"nodes": confirmed_nodes, "edges": edges}

    async def get_workspace_graph_snapshot(self, workspace_id: str) -> Dict[str, List[Dict]]:
        """Returns all confirmed nodes and edges across the workspace, deduplicated."""
        nodes = await self.store.get_workspace_nodes(workspace_id)
        edges = await self.store.get_workspace_edges(workspace_id)

        unique_nodes = {}
        for n in nodes:
            if n.get("status") == "confirmed":
                unique_nodes[n["id"]] = n

        unique_edges = {}
        for e in edges:
            key = (e["source_id"], e["target_id"], e["relation_type"])
            unique_edges[key] = e

        return {"nodes": list(unique_nodes.values()), "edges": list(unique_edges.values())}

    async def remove_job(self, job_id: UUID) -> None:
        """Remove a job from tracking, e.g., when its tab is closed."""
        job = self.execution._active_jobs.pop(job_id, None)
        self.execution._job_actions.pop(job_id, None)
        self.execution._job_buffers.pop(job_id, None)
        self._output_subscribers.pop(job_id, None)
        self.execution.closed_job_ids.add(str(job_id))
        session_id = str(job.session_id) if job else None
        await self.store.mark_event_closed(str(job_id), session_id=session_id)
        if job:
            self._notify_job_change(job)

    def subscribe_job_output(self, job_id: UUID, callback: Callable[[str], Coroutine]) -> None:
        """Subscribe a live UI tab to output streaming for a running job."""
        if job_id not in self._output_subscribers:
            self._output_subscribers[job_id] = set()
        self._output_subscribers[job_id].add(callback)

    def unsubscribe_job_output(self, job_id: UUID, callback: Callable[[str], Coroutine]) -> None:
        """Unsubscribe a tab from a job's output stream."""
        if job_id in self._output_subscribers:
            self._output_subscribers[job_id].discard(callback)

    def get_job_buffer(self, job_id: UUID) -> str:
        """Get accumulated stdout/stderr output for an active/running job."""
        chunks = self.execution.get_output_history(job_id)
        if chunks:
            return "".join(chunks)
        log_path = get_action_log_path(str(job_id))
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception:
                pass
        return ""

    def on_job_status_change(self, callback: Callable[[JobStatus], Any]) -> None:
        """Register a callback for job state changes (started, running, completed, killed)."""
        if callback not in self._job_change_listeners:
            self._job_change_listeners.append(callback)

    def remove_job_status_change(self, callback: Callable[[JobStatus], Any]) -> None:
        """Unregister a job state change callback."""
        if callback in self._job_change_listeners:
            self._job_change_listeners.remove(callback)

    def _notify_job_change(self, job: JobStatus) -> None:
        """Notify all listeners that a job status changed."""
        for cb in list(self._job_change_listeners):
            try:
                res = cb(job)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

    def get_active_jobs_count(self, session_id: str) -> int:
        """Get count of active (running/queued) jobs for a session."""
        return sum(
            1
            for j in self.execution.get_active_jobs()
            if str(j.session_id) == session_id
            and j.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
        )

    async def get_workspace_running_jobs_count(self, workspace_id: str) -> int:
        """Get count of active (running/queued) jobs for all sessions in a workspace."""
        sessions = await self.store.list_sessions(workspace_id)
        session_ids = {s["id"] for s in sessions}
        return sum(
            1
            for j in self.execution.get_active_jobs()
            if str(j.session_id) in session_ids
            and j.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
        )

    def get_session_active_jobs(self, session_id: str) -> List[JobStatus]:
        """Get all active/tracked jobs for a session (running, queued, or recently completed)."""
        return [j for j in self.execution.get_active_jobs() if str(j.session_id) == str(session_id)]

    def get_job(self, job_id: UUID) -> Optional[JobStatus]:
        """Fetch JobStatus by UUID from active job registry."""
        return self.execution.get_job(job_id)

    def register_job(self, job: JobStatus) -> None:
        """Register or update a JobStatus in the active job registry."""
        self.execution._active_jobs[job.job_id] = job
        self._notify_job_change(job)

    def is_job_closed(self, job_id: str) -> bool:
        """Check if a job has been marked closed by the operator."""
        return str(job_id) in self.execution.closed_job_ids

    async def validate_action(self, action: ActionRequest) -> bool:
        """Validate an action request against registry and store policies."""
        return await self.gateway.validate_action(action)

    async def stop_job(self, job_id: str) -> None:
        """Terminate a running job task via executor."""
        await self.execution.runner.stop(str(job_id))

    def get_job_action(self, job_id: UUID) -> Optional[ActionRequest]:
        """Get the original ActionRequest for a job."""
        return self.execution._job_actions.get(job_id)

    async def export_session(self, session_id: str, dest_db_path: str) -> None:
        """Export a session's database rows to a portable database."""
        await self.workspaces.export_session(session_id, dest_db_path)

    async def export_markdown_report(self, session_id: str, dest_path: str) -> None:
        """Export a session's finding summary and logs to a hardened Markdown report file."""
        await self.workspaces.export_markdown_report(session_id, dest_path)

    async def import_session(
        self, src_db_path: str, target_workspace_id: Optional[str] = None
    ) -> str:
        """Import a session from an exported database."""
        return await self.workspaces.import_session(src_db_path, target_workspace_id)
