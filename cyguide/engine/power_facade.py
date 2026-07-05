"""Coordination layer for Power Mode investigation sessions."""

import asyncio
import json
import os
from uuid import UUID
from datetime import datetime, UTC
from typing import Optional, Dict, List, Any, Callable
from cyguide.schemas.power import (
    PowerSession, ActionRequest, WorkspaceContext, JobStatus, JobStatusEnum, ActionSource
)
from cyguide.schemas.base import BaseFinding
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.adapter import ToolAdapter


class ShellAdapter(ToolAdapter):
    """Adapter for explicit shell commands (prefix '!')."""
    def validate_install(self) -> bool:
        return True
    
    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # raw_flags contains the pre-substituted full command string
        import shlex
        return shlex.split(params.get("raw_flags", ""))

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        if False: yield # Shell commands don't produce findings by default


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
        
        # Session state tracking (CWD)
        # session_id -> current_working_dir
        self._session_cwd: Dict[str, str] = {}

    def _get_cwd(self, session_id: str) -> str:
        return self._session_cwd.get(session_id, os.getcwd())

    async def create_session(self, workspace_id: str, name: Optional[str] = None) -> PowerSession:
        """Create a new investigation session in a workspace."""
        session_id = await self.store.create_session(workspace_id, name or "New Investigation")
        # Note: PowerSession in schemas uses UUID, store uses str. We'll bridge them.
        return PowerSession(session_id=UUID(session_id), name=name)

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
        # ...
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
        job = JobStatus(
            job_id=action.action_id,
            tool_name=action.tool_name,
            status=JobStatusEnum.RUNNING
        )
        self._active_jobs[job.job_id] = job
        
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
        user_env = getattr(self, "user_env", os.environ.copy())
        user_shell = getattr(self, "user_shell", "/bin/bash")
        
        asyncio.create_task(self._run_action_task(
            action, adapter, target, on_output, on_complete, 
            on_error_output=on_error_output,
            env=user_env, shell_path=user_shell
        ))
        
        return job.job_id

    async def kill_job(self, job_id: UUID) -> bool:
        """Terminate a running job."""
        job = self._active_jobs.get(job_id)
        if not job or job.status != JobStatusEnum.RUNNING:
            return False
        
        await self.executor.stop_task(str(job_id))
        job.status = JobStatusEnum.FAILED
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
        try:
            findings_count = 0
            async for finding in self.executor.run_tool(
                adapter=adapter,
                target=target,
                params=action.params,
                session_id=str(action.session_id),
                task_id=str(action.action_id),
                cwd=cwd,
                env=env,
                use_shell=action.is_explicit_shell,
                shell_path=shell_path,
                on_output=on_output,
                on_error_output=on_error_output
            ):
                findings_count += 1
            
            # Only set to DONE if it hasn't been set to FAILED (e.g., by manual termination)
            if job.status == JobStatusEnum.RUNNING:
                job.status = JobStatusEnum.DONE
        except Exception as e:
            job.status = JobStatusEnum.FAILED
            await self.store.append_event(
                str(action.session_id),
                action,
                {"error": str(e)},
                f"Failed to run {action.tool_name}: {str(e)}"
            )
        finally:
            job.completed_at = datetime.now(UTC)
            if on_complete:
                try:
                    await on_complete()
                except:
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
                    resolved_vars["PROTO"] = pik["protocol"]

        # 2. Aggregate counts and jobs
        stats = await self.store.get_stats(session_id)
        # Keep completed jobs visible to show status icons (DONE/FAILED/RUNNING) until closed
        active_jobs = [j for j in self._active_jobs.values()]

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

    async def get_graph_snapshot(self, session_id: str) -> List[Dict]:
        """Returns all confirmed nodes for the session."""
        nodes = await self.store.get_all_nodes(session_id)
        return [n for n in nodes if n.get("status") == "confirmed"]

    def remove_job(self, job_id: UUID) -> None:
        """Remove a job from tracking, e.g., when its tab is closed."""
        self._active_jobs.pop(job_id, None)
