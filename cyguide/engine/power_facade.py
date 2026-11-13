"""Coordination layer for Power Mode investigation sessions."""

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.executor import Executor, sanitize_subprocess_env
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.network import get_lhost_info
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.paths import get_action_log_path
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest, JobStatus, JobStatusEnum, WorkspaceContext


class ShellAdapter(ToolAdapter):
    """Adapter for explicit shell commands (prefix '!')."""
    def validate_install(self) -> bool:
        return True

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # raw_flags contains the pre-substituted full command string
        import shlex
        return shlex.split(params.get("raw_flags", ""))

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        return
        yield  # Shell commands don't produce findings by default


class PowerWorkspaceFacade:
    """The central coordination layer for Power Mode.

    This is the primary API for the TUI and future agents. It orchestrates
    sessions, validates actions, manages tool execution, and builds workspace context.
    """

    def __init__(self, store: GraphStore, executor: Executor, registry: ToolRegistry):
        self.store = store
        self.executor = executor
        self.registry = registry
        self.gateway = ActionGateway(registry, store)

        # In-memory tracking of jobs for the current process
        # job_id -> JobStatus
        self._active_jobs: Dict[UUID, JobStatus] = {}

        # Job metadata & live output streaming
        # job_id -> ActionRequest
        self._job_actions: Dict[UUID, ActionRequest] = {}
        # job_id -> list of output strings
        self._job_buffers: Dict[UUID, List[str]] = {}
        # job_id -> set of subscriber coroutines
        self._job_subscribers: Dict[UUID, set] = {}
        # Global status change listeners
        self._job_change_listeners: List[Callable] = []

        # Session state tracking (CWD)
        # session_id -> current_working_dir
        self._session_cwd: Dict[str, str] = {}

        # Track jobs that the user explicitly closed so they aren't restored
        self.closed_job_ids: set[str] = set()

        # Track background asyncio.Tasks for clean shutdown
        self._running_tasks: Dict[UUID, asyncio.Task] = {}

    def _get_cwd(self, session_id: str) -> str:
        return self._session_cwd.get(session_id, os.getcwd())

    def get_running_task(self, job_id: UUID) -> Optional[asyncio.Task]:
        """Retrieve background execution task for a job by UUID."""
        return self._running_tasks.get(job_id)

    async def create_workspace(self, name: str) -> str:
        """Create a new workspace, ensuring its name is unique (case-insensitive)."""
        existing = await self.store.list_workspaces()
        if any(ws["name"].strip().lower() == name.strip().lower() for ws in existing):
            raise ValueError("Workspace with this name already exists.")
        return await self.store.create_workspace(name)

    async def rename_workspace(self, workspace_id: str, new_name: str) -> None:
        """Rename a workspace, ensuring the new name is unique."""
        existing = await self.store.list_workspaces()
        if any(ws["name"].strip().lower() == new_name.strip().lower() and ws["id"] != workspace_id for ws in existing):
            raise ValueError("Workspace with this name already exists.")
        await self.store.rename_workspace(workspace_id, new_name)

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
        if any(s["name"].strip().lower() == new_name.strip().lower() and s["id"] != session_id for s in existing):
            raise ValueError("Session with this name already exists in this workspace.")
        await self.store.rename_session(session_id, new_name)

    async def set_entity_alias(self, session_id: str, node_id: str, alias: str) -> None:
        """Set a user-defined friendly name or alias for an entity node."""
        await self.store.update_node_data(session_id, node_id, {"alias": alias.strip()})

    async def move_session(self, session_id: str, target_workspace_id: str) -> None:
        """Move a session to another workspace, ensuring no name collision."""
        session = await self.store.get_session(session_id)
        if not session:
            raise ValueError("Session not found.")
        existing = await self.store.list_sessions(target_workspace_id)
        if any(s["name"].strip().lower() == session["name"].strip().lower() for s in existing):
            raise ValueError("A session with this name already exists in the target workspace.")
        await self.store.move_session(session_id, target_workspace_id)

    async def delete_session(self, session_id: str) -> None:
        """Clean up active jobs for the session, then delete it."""
        target_jobs = [j for j in self._active_jobs.values() if str(j.session_id) == session_id]
        for job in target_jobs:
            try:
                await self.executor.stop_task(str(job.job_id))
            except Exception:
                pass
            self._active_jobs.pop(job.job_id, None)
            self.closed_job_ids.discard(str(job.job_id))
        await self.store.delete_session(session_id)

    async def delete_workspace(self, workspace_id: str) -> None:
        """Clean up active jobs for all sessions in the workspace, then delete it."""
        sessions = await self.store.list_sessions(workspace_id)
        session_ids = {s["id"] for s in sessions}
        target_jobs = [j for j in self._active_jobs.values() if str(j.session_id) in session_ids]
        for job in target_jobs:
            try:
                await self.executor.stop_task(str(job.job_id))
            except Exception:
                pass
            self._active_jobs.pop(job.job_id, None)
            self.closed_job_ids.discard(str(job.job_id))
        await self.store.delete_workspace(workspace_id)

    async def close_session(self, session_id: str) -> None:
        """Clean up active jobs for the session, mark closed, and log audit event."""
        target_jobs = [j for j in self._active_jobs.values() if str(j.session_id) == session_id]
        for job in target_jobs:
            try:
                await self.executor.stop_task(str(job.job_id))
            except Exception:
                pass
            self._active_jobs.pop(job.job_id, None)
            self.closed_job_ids.discard(str(job.job_id))
        await self.store.close_session(session_id)
        await self.store.log_audit_event(
            session_id,
            "session_closed",
            "Session archived/closed (forensic audit preserved).",
            "CLOSED"
        )

    async def reopen_session(self, session_id: str) -> None:
        """Reopen an archived session back to ACTIVE."""
        await self.store.reopen_session(session_id)
        await self.store.log_audit_event(
            session_id,
            "session_reopened",
            "Session reopened to ACTIVE status.",
            "ACTIVE"
        )

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

    async def list_sessions(self, workspace_id: str, status_filter: Optional[str] = None) -> List[Dict]:
        """List sessions within a workspace, optionally filtered by status."""
        return await self.store.list_sessions(workspace_id, status_filter=status_filter)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Fetch session metadata by ID."""
        return await self.store.get_session(session_id)

    async def get_node(self, session_id: str, node_id: str) -> Optional[Dict]:
        """Fetch a specific node by ID."""
        return await self.store.get_node(session_id, node_id)

    async def get_all_nodes(self, session_id: str) -> List[Dict]:
        """Fetch all nodes for a session."""
        return await self.store.get_all_nodes(session_id)

    async def get_all_edges(self, session_id: str) -> List[Dict]:
        """Fetch all edges for a session."""
        return await self.store.get_all_edges(session_id)

    async def get_stats(self, session_id: Optional[str] = None, workspace_id: Optional[str] = None) -> Dict[str, int]:
        """Get aggregate node and vulnerability counts."""
        return await self.store.get_stats(session_id=session_id, workspace_id=workspace_id)

    async def get_recent_activity(self, workspace_id: str, limit: int = 5) -> List[Dict]:
        """Get recent activity audit events for a workspace."""
        return await self.store.get_recent_activity(workspace_id, limit=limit)

    async def get_closed_events_count(self, session_id: str) -> int:
        """Count closed tool execution events for a session."""
        return await self.store.get_closed_events_count(session_id)

    def on_finding_upsert(self, callback: Any) -> None:
        """Register a callback for finding upserts."""
        self.store.on_upsert(callback)

    def on_upsert(self, callback: Any) -> None:
        """Alias for on_finding_upsert."""
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
        on_error_output: Optional[Callable] = None
    ) -> UUID:
        """Validate and execute a tool action.

        Returns:
            The UUID of the created job.
        """
        # 0. Forensic Guard: Verify session is ACTIVE
        session_info = await self.store.get_session(str(action.session_id))
        if session_info and session_info.get("status") == "CLOSED":
            raise PermissionError("Cannot execute actions in an archived session. Reopen the session first.")

        # 1. Resolve Session and Context for Variable Substitution (if target exists)
        ctx = await self.get_context(str(action.session_id), action.target_entity_id)

        # 2. Variable Substitution ($TARGET, etc.)
        raw_flags = action.params.get("raw_flags", "")
        if ctx.resolved_vars:
            for var_name, val in ctx.resolved_vars.items():
                placeholder = f"${var_name}"
                if placeholder in raw_flags:
                    raw_flags = raw_flags.replace(placeholder, str(val))

        # 3. Resolve components for execution
        tool_data = self.registry.get_tool(action.tool_name)

        # 3.1 Handle Built-ins (cd)
        if not tool_data and action.tool_name == "cd":
            try:
                dest = action.params.get("raw_flags", "").strip()
                current = self._get_cwd(str(action.session_id))
                new_path = os.path.abspath(os.path.join(current, dest))
                if os.path.isdir(new_path):
                    self._session_cwd[str(action.session_id)] = new_path
                    if on_output: await on_output(f"Changed directory to: {new_path}\n")
                else:
                    if on_output: await on_output(f"cd: no such directory: {dest}\n")
            except Exception as e:
                if on_output: await on_output(f"cd error: {str(e)}\n")
            return UUID(int=0)

        # 3.2 Determine Adapter
        if action.is_explicit_shell:
            # Explicit shell command (!)
            action.params["raw_flags"] = f"{action.tool_name} {raw_flags}".strip()
            adapter = ShellAdapter()
        elif tool_data:
            # Registered tool
            action.params["raw_flags"] = raw_flags
            adapter = tool_data["adapter"]
        else:
            raise ValueError(f"No tool or explicit shell prefix found for '{action.tool_name}'")

        # 4. Validation (Enforces USER vs AGENT policy)
        await self.gateway.validate_action(action)

        # 5. Setup job tracking
        log_file_path = get_action_log_path(str(action.action_id))
        cmd_raw = action.params.get("raw_flags", "") if action.params else ""
        cmd_snippet = f"{action.tool_name} {cmd_raw}".strip() if cmd_raw else action.tool_name

        job = JobStatus(
            job_id=action.action_id,
            session_id=action.session_id,
            tool_name=action.tool_name,
            status=JobStatusEnum.RUNNING,
            log_file=log_file_path,
            command_snippet=cmd_snippet
        )
        self._active_jobs[job.job_id] = job
        self._job_actions[job.job_id] = action
        self._job_buffers[job.job_id] = []
        if job.job_id not in self._job_subscribers:
            self._job_subscribers[job.job_id] = set()
        if on_output:
            self._job_subscribers[job.job_id].add(on_output)

        self._notify_job_change(job)

        # 6. Get target finding (or create dummy for shell)
        if not action.is_explicit_shell and action.target_entity_id:
            node_data = await self.store.get_node(str(action.session_id), action.target_entity_id)
            target = BaseFinding(
                schema_type=node_data["schema_type"],
                pik=json.loads(node_data["pik_json"]),
                data=json.loads(node_data["data_json"]),
                status=node_data.get("status", "confirmed")
            )
        else:
            target = BaseFinding(
                schema_type="system.shell",
                pik={"cmd": action.tool_name},
                data={},
                status="confirmed"
            )

        # 7. Start execution as a background task
        # Retrieve environment from app if available (passed during init or via a global)
        # For now, we'll expect the caller or a reference to 'app'
        user_env = sanitize_subprocess_env(getattr(self, "user_env", os.environ.copy()))
        user_shell = getattr(self, "user_shell", "/bin/bash")

        task = asyncio.create_task(self._run_action_task(
            action, adapter, target, on_output, on_complete,
            on_error_output=on_error_output,
            env=user_env, shell_path=user_shell
        ))
        self._running_tasks[action.action_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(action.action_id, None))

        return job.job_id

    async def shutdown(self) -> None:
        """Cancel and drain all running action tasks before store closes."""
        tasks = list(self._running_tasks.values())
        if tasks:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def kill_job(self, job_id: UUID) -> bool:
        """Terminate a running job."""
        job = self._active_jobs.get(job_id)
        if not job or job.status != JobStatusEnum.RUNNING:
            return False

        await self.executor.stop_task(str(job_id))
        job.status = JobStatusEnum.FAILED
        self._notify_job_change(job)
        return True

    async def _run_action_task(
        self,
        action: ActionRequest,
        adapter: Any,
        target: BaseFinding,
        on_output: Optional[Callable],
        on_complete: Optional[Callable] = None,
        on_error_output: Optional[Callable] = None,
        env: Optional[Dict[str, str]] = None,
        shell_path: Optional[str] = None
    ):
        job = self._active_jobs[action.action_id]
        cwd = self._get_cwd(str(action.session_id))
        log_file_path = job.log_file or get_action_log_path(str(action.action_id))

        if action.action_id not in self._job_buffers:
            self._job_buffers[action.action_id] = []

        # Initialize disk log file with execution header
        try:
            log_dir = os.path.dirname(log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"=== Execution Start: {datetime.now(UTC).isoformat()} ===\n")
                f.write(f"Tool: {action.tool_name}\n")
                f.write(f"Session: {action.session_id}\n")
                f.write(f"Action ID: {action.action_id}\n")
                f.write("=" * 50 + "\n\n")
        except Exception:
            pass

        async def intercept_output(text: str):
            buf = self._job_buffers[action.action_id]
            buf.append(text)
            if len(buf) > 5000:
                self._job_buffers[action.action_id] = buf[-2500:]

            try:
                with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(text)
            except Exception:
                pass

            subs = list(self._job_subscribers.get(action.action_id, set()))
            for sub in subs:
                try:
                    await sub(text)
                except Exception:
                    pass

        async def intercept_error(text: str):
            buf = self._job_buffers[action.action_id]
            buf.append(text)
            if len(buf) > 5000:
                self._job_buffers[action.action_id] = buf[-2500:]

            try:
                with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                    f.write(text)
            except Exception:
                pass

            subs = list(self._job_subscribers.get(action.action_id, set()))
            for sub in subs:
                try:
                    await sub(text)
                except Exception:
                    pass

        err_msg = None
        try:
            findings_count = 0
            finding_buffer: List[BaseFinding] = []
            last_flush = asyncio.get_event_loop().time()

            async def flush_findings():
                nonlocal last_flush
                if not finding_buffer:
                    return
                to_flush = list(finding_buffer)
                finding_buffer.clear()
                last_flush = asyncio.get_event_loop().time()
                if not getattr(self.store, "_closed", False):
                    try:
                        await self.store.upsert_findings_batch(str(action.session_id), to_flush)
                    except Exception:
                        pass

            async for finding in self.executor.run_tool(
                adapter=adapter,
                target=target,
                params=action.params,
                session_id=None,
                task_id=str(action.action_id),
                cwd=cwd,
                env=env,
                use_shell=action.is_explicit_shell,
                shell_path=shell_path,
                on_output=intercept_output,
                on_error_output=intercept_error,
                timeout_seconds=getattr(action, "timeout_seconds", None)
            ):
                findings_count += 1
                finding_buffer.append(finding)
                now = asyncio.get_event_loop().time()
                if len(finding_buffer) >= 50 or (now - last_flush) >= 0.25:
                    await flush_findings()

            await flush_findings()

            # Only set to DONE if it hasn't been set to FAILED (e.g., by manual termination)
            if job.status == JobStatusEnum.RUNNING:
                job.status = JobStatusEnum.DONE
        except asyncio.CancelledError:
            err_msg = "Job cancelled on shutdown"
            job.status = JobStatusEnum.FAILED
        except Exception as e:
            err_msg = str(e)
            job.status = JobStatusEnum.FAILED
        finally:
            job.completed_at = datetime.now(UTC)

            # Record final status in disk log
            try:
                with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                    status_str = "SUCCESS" if job.status == JobStatusEnum.DONE else f"FAILED ({err_msg})"
                    f.write(f"\n\n=== Execution End: {datetime.now(UTC).isoformat()} [{status_str}] ===\n")
            except Exception:
                pass

            # Persist output to event log so tabs can be restored across sessions (guard against closed store)
            if not getattr(self.store, "_closed", False):
                try:
                    buf_output = "".join(self._job_buffers.get(action.action_id, []))
                    if len(buf_output) > 200_000:
                        db_output = (
                            buf_output[:100_000]
                            + f"\n\n... [Log truncated for database storage. Full log at {log_file_path}] ...\n\n"
                            + buf_output[-100_000:]
                        )
                    else:
                        db_output = buf_output

                    await self.store.append_event(
                        str(action.session_id),
                        action,
                        {"output": db_output, "log_file": log_file_path, "error": err_msg},
                        f"Ran {action.tool_name}" + (f" (failed: {err_msg})" if err_msg else "")
                    )
                    if str(action.action_id) in self.closed_job_ids:
                        await self.store.mark_event_closed(str(action.action_id), session_id=str(action.session_id))
                except Exception:
                    pass

            self._notify_job_change(job)

            if on_complete:
                try:
                    await on_complete()
                except Exception:
                    pass

    async def get_context(self, session_id: str, selected_entity_id: Optional[str] = None) -> WorkspaceContext:
        """Build a point-in-time snapshot of the workspace context."""
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
                    status=node_data.get("status", "confirmed")
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
            lhost_ip, _ = get_lhost_info()
            if lhost_ip:
                resolved_vars["LHOST"] = lhost_ip
        except Exception:
            pass

        # 2. Aggregate counts and jobs
        stats = await self.store.get_stats(session_id)

        # Get all valid sessions in the current workspace
        workspace_id = session_data["workspace_id"]
        workspace_sessions = await self.store.list_sessions(workspace_id)
        workspace_session_ids = {s["id"] for s in workspace_sessions}

        # Keep completed jobs visible to show status icons (DONE/FAILED/RUNNING) until closed
        # Filter to only include jobs belonging to sessions in this workspace
        active_jobs = [j for j in self._active_jobs.values() if str(j.session_id) in workspace_session_ids]

        return WorkspaceContext(
            session_id=UUID(session_id),
            session_name=session_data["name"],
            selected_entity=selected_entity,
            resolved_vars=resolved_vars,
            active_jobs=active_jobs,
            entity_counts=stats,
            cwd=self._get_cwd(session_id)
        )

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

        # Deduplicate nodes by id
        unique_nodes = {}
        for n in nodes:
            if n.get("status") == "confirmed":
                unique_nodes[n["id"]] = n

        # Deduplicate edges by source, target, type
        unique_edges = {}
        for e in edges:
            key = (e["source_id"], e["target_id"], e["relation_type"])
            unique_edges[key] = e

        return {"nodes": list(unique_nodes.values()), "edges": list(unique_edges.values())}

    async def remove_job(self, job_id: UUID) -> None:
        """Remove a job from tracking, e.g., when its tab is closed."""
        job = self._active_jobs.pop(job_id, None)
        self._job_actions.pop(job_id, None)
        self._job_buffers.pop(job_id, None)
        self._job_subscribers.pop(job_id, None)
        self.closed_job_ids.add(str(job_id))
        session_id = str(job.session_id) if job else None
        await self.store.mark_event_closed(str(job_id), session_id=session_id)
        if job:
            self._notify_job_change(job)

    def subscribe_job_output(self, job_id: UUID, callback: Callable[[str], Coroutine]) -> None:
        """Subscribe a live UI tab to output streaming for a running job."""
        if job_id not in self._job_subscribers:
            self._job_subscribers[job_id] = set()
        self._job_subscribers[job_id].add(callback)

    def unsubscribe_job_output(self, job_id: UUID, callback: Callable[[str], Coroutine]) -> None:
        """Unsubscribe a tab from a job's output stream."""
        if job_id in self._job_subscribers:
            self._job_subscribers[job_id].discard(callback)

    def get_job_buffer(self, job_id: UUID) -> str:
        """Get accumulated stdout/stderr output for an active/running job."""
        chunks = self._job_buffers.get(job_id)
        if chunks:
            return "".join(chunks)
        # Fallback to reading disk log if in-memory buffer was cleared or closed
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
        from cyguide.schemas.power import JobStatusEnum
        return sum(
            1 for j in self._active_jobs.values()
            if str(j.session_id) == session_id and j.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
        )

    async def get_workspace_running_jobs_count(self, workspace_id: str) -> int:
        """Get count of active (running/queued) jobs for all sessions in a workspace."""
        from cyguide.schemas.power import JobStatusEnum
        sessions = await self.store.list_sessions(workspace_id)
        session_ids = {s["id"] for s in sessions}
        return sum(
            1 for j in self._active_jobs.values()
            if str(j.session_id) in session_ids and j.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
        )

    def get_session_active_jobs(self, session_id: str) -> List[JobStatus]:
        """Get all active/tracked jobs for a session (running, queued, or recently completed)."""
        return [j for j in self._active_jobs.values() if str(j.session_id) == str(session_id)]

    def get_job(self, job_id: UUID) -> Optional[JobStatus]:
        """Fetch JobStatus by UUID from active job registry."""
        return self._active_jobs.get(job_id)

    def register_job(self, job: JobStatus) -> None:
        """Register or update a JobStatus in the active job registry."""
        self._active_jobs[job.job_id] = job
        self._notify_job_change(job)

    def is_job_closed(self, job_id: str) -> bool:
        """Check if a job has been marked closed by the operator."""
        return str(job_id) in self.closed_job_ids

    async def validate_action(self, action: ActionRequest) -> bool:
        """Validate an action request against registry and store policies."""
        return await self.gateway.validate_action(action)

    async def stop_job(self, job_id: str) -> None:
        """Terminate a running job task via executor."""
        await self.executor.stop_task(str(job_id))

    def get_job_action(self, job_id: UUID) -> Optional[ActionRequest]:
        """Get the original ActionRequest for a job."""
        return self._job_actions.get(job_id)

    async def export_session(self, session_id: str, dest_db_path: str) -> None:
        """Export a session's database rows to a portable database."""
        await self.store.export_session(session_id, dest_db_path)

    async def export_markdown_report(self, session_id: str, dest_path: str) -> None:
        """Export a session's finding summary and logs to a hardened Markdown report file."""
        from cyguide.engine.reporter import export_markdown_report
        await export_markdown_report(self.store, session_id, dest_path)

    async def import_session(self, src_db_path: str, target_workspace_id: Optional[str] = None) -> str:
        """Import a session from an exported database."""
        return await self.store.import_session(src_db_path, target_workspace_id)
