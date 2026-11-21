"""Coordination layer for Power Mode investigation sessions."""

import asyncio
import os
import shutil
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from uuid import UUID

from cyguide.engine.context_builder import WorkspaceContextBuilder
from cyguide.engine.execution_session import (
    CommandRunner,
    ExecutionSession,
    SubprocessCommandRunner,
    TerminalSuspendContext,
)
from cyguide.engine.executor import Executor, sanitize_subprocess_env
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.graph_analytics import GraphAnalyticsEngine
from cyguide.engine.network import get_lhost_info
from cyguide.engine.preflight import PreflightReport, PreflightVerifier
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.engine.workspace_repository import WorkspaceRepository
from cyguide.paths import get_action_log_path
from cyguide.schemas.power import ActionRequest, JobStatus, JobStatusEnum, WorkspaceContext

__all__ = ["PowerWorkspaceFacade", "get_lhost_info", "send_desktop_notification"]


async def send_desktop_notification(title: str, message: str) -> None:
    """Send an OS desktop notification using notify-send if available."""
    try:
        if shutil.which("notify-send"):
            proc = await asyncio.create_subprocess_exec(
                "notify-send",
                "-a",
                "CyGuide",
                title,
                message,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
    except Exception:
        pass


class PowerWorkspaceFacade:
    """The central coordination layer for Power Mode.

    This is the primary API for the TUI and future agents. It orchestrates
    sessions, validates actions, manages tool execution, and builds workspace context.
    """

    @staticmethod
    async def send_desktop_notification(title: str, message: str) -> None:
        """Send an OS desktop notification using notify-send if available."""
        await send_desktop_notification(title, message)

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

        # InvestigationSession seam fields
        self.session_id: Optional[UUID] = None
        self.workspace_id: Optional[UUID] = None
        self.explainer: Optional[Any] = None
        self.preflight_verifier = PreflightVerifier(registry=self.registry)

    def verify_preflight(
        self,
        tool_name: str,
        target: str,
        flags: str = "",
        recipe_idx: Optional[int] = None,
    ) -> PreflightReport:
        """Validate execution dependencies, target variables, and security parameters."""
        return self.preflight_verifier.verify(
            tool_name=tool_name,
            target=target,
            flags=flags,
            recipe_idx=recipe_idx,
        )

    async def extract_structured_findings(
        self,
        store: Optional[GraphStore] = None,
        session_id: Optional[Any] = None,
    ) -> Tuple[str, str]:
        """Format discovered graph findings for UI display and AI context."""
        from cyguide.engine.reporter import SessionReportService

        target_store = store or self.store
        target_session_id = session_id or self.session_id
        if not target_store or not target_session_id:
            return "*No structured findings in current session yet.*", "None"
        return await SessionReportService(target_store).extract_structured_findings(
            str(target_session_id)
        )

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

    def mark_job_closed(self, job_id: Any) -> None:
        """Mark a job as closed."""
        self.execution.mark_job_closed(job_id)

    def has_job_subscriber(self, job_id: UUID, callback: Callable) -> bool:
        """Check if an output subscriber is registered for a job."""
        return callback in self._output_subscribers.get(job_id, set())

    def get_running_task(self, job_id: UUID) -> Optional[asyncio.Task]:
        """Retrieve background execution task for a job by UUID."""
        return self.execution.get_running_task(job_id)

    def track_task(self, job_id: UUID, task: asyncio.Task) -> None:
        """Register an asynchronous task under session lifecycle management."""
        self.execution.track_task(job_id, task)

    async def get_notes(self, session_id: Optional[str] = None) -> str:
        """Fetch persistent notes for an investigation session from SQLite."""
        target_id = session_id or (str(self.session_id) if self.session_id else None)
        if not target_id:
            return ""
        return await self.workspaces.get_session_notes(target_id)

    async def save_notes(self, content: str, session_id: Optional[str] = None) -> None:
        """Atomically persist notes for an investigation session into SQLite."""
        target_id = session_id or (str(self.session_id) if self.session_id else None)
        if target_id:
            await self.workspaces.save_session_notes(target_id, content)

    async def get_closed_events_count(self, session_id: str) -> int:
        """Count closed tool execution events for a session."""
        return await self.store.get_closed_events_count(session_id)

    def on_finding_upsert(self, callback: Any) -> None:
        """Register a callback for finding upserts."""
        self.store.on_upsert(callback)

    def on_findings_batch(self, callback: Any) -> None:
        """Register a callback for batched finding upserts."""
        self.store.on_findings_batch(callback)

    async def generate_markdown_report(self, session_id: str) -> str:
        """Generate markdown report string for a session."""
        from cyguide.engine.reporter import SessionReportService

        return await SessionReportService(self.store).generate_markdown_report(session_id)

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

    # Alias for InvestigationSession polymorphic interface
    execute = submit_action

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

    async def get_graph_snapshot(self, session_id: Optional[str] = None) -> Dict[str, List[Dict]]:
        """Returns all confirmed nodes and edges for the session."""
        target_id = session_id or (str(self.session_id) if self.session_id else None)
        if not target_id:
            return {"nodes": [], "edges": []}
        nodes = await self.store.get_all_nodes(target_id)
        edges = await self.store.get_all_edges(target_id)
        confirmed_nodes = [n for n in nodes if n.get("status") == "confirmed"]
        return {"nodes": confirmed_nodes, "edges": edges}

    async def get_graph_analytics(self, session_id: Optional[str] = None) -> GraphAnalyticsEngine:
        """Instantiate a GraphAnalyticsEngine over the session's confirmed graph snapshot."""
        snapshot = await self.get_graph_snapshot(session_id)
        return GraphAnalyticsEngine(snapshot["nodes"], snapshot["edges"])

    async def get_critical_pivot_nodes(
        self, session_id: Optional[str] = None, top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Identify top-k critical choke points and dual-homed pivot nodes via betweenness centrality."""
        analytics = await self.get_graph_analytics(session_id)
        centrality = analytics.calculate_betweenness_centrality()
        sorted_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
        results: List[Tuple[Dict[str, Any], float]] = []
        for n_id, score in sorted_nodes[:top_k]:
            if score > 0.0 and n_id in analytics.nodes_by_id:
                results.append((analytics.nodes_by_id[n_id], score))
        return results

    async def get_cyclic_attack_chains(
        self, session_id: Optional[str] = None
    ) -> List[List[Dict[str, Any]]]:
        """Detect circular exploit and lateral movement paths across session entities."""
        analytics = await self.get_graph_analytics(session_id)
        sccs = analytics.find_strongly_connected_components()
        cycles = [comp for comp in sccs if len(comp) >= 2]
        return [
            [analytics.nodes_by_id[nid] for nid in comp if nid in analytics.nodes_by_id]
            for comp in cycles
        ]

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
        job = self.execution.remove_job(job_id)
        self._output_subscribers.pop(job_id, None)
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

    def append_job_buffer(self, job_id: UUID, chunk: str) -> None:
        """Append an output chunk to in-memory job buffer."""
        self.execution.append_job_buffer(job_id, chunk)

    def register_job(self, job: JobStatus) -> None:
        """Register or update a JobStatus in active job tracking."""
        self.execution.register_job(job)

    def register_action(self, action: ActionRequest) -> None:
        """Register the ActionRequest for a job."""
        self.execution.register_action(action)

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
        return self.execution.get_active_jobs_count(session_id)

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
        return self.execution.get_session_active_jobs(session_id)

    def get_job(self, job_id: UUID) -> Optional[JobStatus]:
        """Fetch JobStatus by UUID from active job registry."""
        return self.execution.get_job(job_id)

    def is_job_closed(self, job_id: str) -> bool:
        """Check if a job has been marked closed by the operator."""
        return self.execution.is_job_closed(job_id)

    async def validate_action(self, action: ActionRequest) -> bool:
        """Validate an action request against registry and store policies."""
        return await self.gateway.validate_action(action)

    async def stop_job(self, job_id: str) -> None:
        """Terminate a running job task via executor."""
        await self.execution.runner.stop(str(job_id))

    def get_job_action(self, job_id: UUID) -> Optional[ActionRequest]:
        """Get the original ActionRequest for a job."""
        return self.execution.get_job_action(job_id)
