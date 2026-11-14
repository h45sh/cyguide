"""ExecutionSession: Deep module encapsulating action execution, output spooling, and stream multiplexing."""

import asyncio
import os
import shlex
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import (
    Any,
    AsyncIterator,
    Callable,
    ContextManager,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)
from uuid import UUID

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.executor import Executor, sanitize_subprocess_env
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.paths import get_action_log_path
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.power import ActionRequest, JobStatus, JobStatusEnum

# --- Protocols & Seams ---


@runtime_checkable
class TerminalSuspendContext(Protocol):
    """Protocol for safely suspending a terminal UI during privileged operations."""

    def suspend(self) -> ContextManager[None]:
        """Context manager invoked before privileged execution to release terminal controls."""
        ...


class DefaultSuspendContext:
    """Default no-op suspend context for headless or testing execution."""

    @contextmanager
    def suspend(self) -> Iterator[None]:
        yield


@runtime_checkable
class CommandRunner(Protocol):
    """Protocol for executing tools or shell commands and streaming raw output."""

    async def run(
        self,
        adapter: ToolAdapter,
        target: BaseFinding,
        params: Dict[str, Any],
        task_id: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        use_shell: bool = False,
        shell_path: Optional[str] = None,
        on_output: Optional[Callable[[str], Any]] = None,
        on_error_output: Optional[Callable[[str], Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[BaseFinding]: ...

    async def stop(self, task_id: str) -> None: ...


class SubprocessCommandRunner:
    """Production CommandRunner delegating to Executor subprocess management."""

    def __init__(self, executor: Executor):
        self.executor = executor

    async def run(
        self,
        adapter: ToolAdapter,
        target: BaseFinding,
        params: Dict[str, Any],
        task_id: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        use_shell: bool = False,
        shell_path: Optional[str] = None,
        on_output: Optional[Callable[[str], Any]] = None,
        on_error_output: Optional[Callable[[str], Any]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> AsyncIterator[BaseFinding]:
        async for finding in self.executor.run_tool(
            adapter=adapter,
            target=target,
            params=params,
            session_id=None,
            task_id=task_id,
            cwd=cwd,
            env=env,
            use_shell=use_shell,
            shell_path=shell_path,
            on_output=on_output,
            on_error_output=on_error_output,
            timeout_seconds=timeout_seconds,
        ):
            yield finding

    async def stop(self, task_id: str) -> None:
        await self.executor.stop_task(task_id)


# --- Typed Execution Events ---


@dataclass(frozen=True)
class ExecutionEvent:
    """Base typed execution event emitted across the ExecutionSession stream."""

    action_id: UUID
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExecutionStarted(ExecutionEvent):
    tool_name: str = ""
    command_snippet: str = ""
    log_file: str = ""


@dataclass(frozen=True)
class ExecutionChunk(ExecutionEvent):
    text: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class ExecutionCompleted(ExecutionEvent):
    status: JobStatusEnum = JobStatusEnum.DONE
    findings_count: int = 0
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class ExecutionFailed(ExecutionEvent):
    error: str = ""
    duration_seconds: float = 0.0


# --- Internal Adapters ---


class InternalShellAdapter(ToolAdapter):
    """Adapter for explicit shell commands (prefix '!')."""

    def validate_install(self) -> bool:
        return True

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        return shlex.split(params.get("raw_flags", ""))

    async def parse_output(
        self,
        raw_stdout: str,
        target: BaseFinding,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[BaseFinding]:
        if False:
            yield target


# --- Deep ExecutionSession Module ---


class ExecutionSession:
    """Encapsulates in-memory action execution lifecycles, streaming multiplexers,

    disk log spooling, and interactive privileged command execution.
    """

    def __init__(
        self,
        store: GraphStore,
        gateway: ActionGateway,
        registry: ToolRegistry,
        command_runner: CommandRunner,
        user_env: Optional[Dict[str, str]] = None,
        user_shell: Optional[str] = None,
    ):
        self.store = store
        self.gateway = gateway
        self.registry = registry
        self.runner = command_runner
        self.user_env = user_env or os.environ.copy()
        self.user_shell = user_shell or "/bin/bash"

        # Action tracking
        self._active_jobs: Dict[UUID, JobStatus] = {}
        self._job_actions: Dict[UUID, ActionRequest] = {}
        self._job_buffers: Dict[UUID, List[str]] = {}
        self._event_queues: Dict[UUID, List[asyncio.Queue[Optional[ExecutionEvent]]]] = {}
        self._running_tasks: Dict[UUID, asyncio.Task] = {}
        self._status_listeners: List[Callable[[JobStatus], Any]] = []
        self._session_cwd: Dict[str, str] = {}
        self.closed_job_ids: set[str] = set()

    def add_status_listener(self, listener: Callable[[JobStatus], Any]) -> None:
        """Register a callback notified when any job changes status."""
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: Callable[[JobStatus], Any]) -> None:
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    def _notify_status(self, job: JobStatus) -> None:
        for listener in list(self._status_listeners):
            try:
                listener(job)
            except Exception:
                pass

    def get_job(self, action_id: UUID) -> Optional[JobStatus]:
        return self._active_jobs.get(action_id)

    def get_active_jobs(self) -> List[JobStatus]:
        return list(self._active_jobs.values())

    def get_running_task(self, action_id: UUID) -> Optional[asyncio.Task]:
        return self._running_tasks.get(action_id)

    def get_cwd(self, session_id: str) -> str:
        return self._session_cwd.get(session_id, os.getcwd())

    def set_cwd(self, session_id: str, new_path: str) -> None:
        self._session_cwd[session_id] = new_path

    def get_output_history(self, action_id: UUID) -> List[str]:
        """Return buffered output chunks for replay when switching or restoring tabs."""
        return list(self._job_buffers.get(action_id, []))

    async def subscribe(self, action_id: UUID) -> AsyncIterator[ExecutionEvent]:
        """Subscribe to live typed execution events for an action with backlog replay."""
        q: asyncio.Queue[Optional[ExecutionEvent]] = asyncio.Queue()
        if action_id not in self._event_queues:
            self._event_queues[action_id] = []
        self._event_queues[action_id].append(q)

        # Replay backlog if already started
        buffer_chunks = self.get_output_history(action_id)
        for chunk in buffer_chunks:
            await q.put(ExecutionChunk(action_id=action_id, text=chunk))

        job = self.get_job(action_id)
        if job and job.status != JobStatusEnum.RUNNING:
            if job.status == JobStatusEnum.DONE:
                await q.put(ExecutionCompleted(action_id=action_id, status=job.status))
            else:
                await q.put(
                    ExecutionFailed(action_id=action_id, error=job.error_snippet or "Failed")
                )
            await q.put(None)

        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            if action_id in self._event_queues and q in self._event_queues[action_id]:
                self._event_queues[action_id].remove(q)
                if not self._event_queues[action_id]:
                    self._event_queues.pop(action_id, None)

    async def _emit_event(self, action_id: UUID, event: Optional[ExecutionEvent]) -> None:
        queues = list(self._event_queues.get(action_id, []))
        for q in queues:
            try:
                await q.put(event)
            except Exception:
                pass

    async def dispatch(
        self,
        action: ActionRequest,
        suspend_context: Optional[TerminalSuspendContext] = None,
        on_chunk: Optional[Callable[[str], Any]] = None,
        on_complete: Optional[Callable[[], Any]] = None,
    ) -> UUID:
        """Dispatch an action request through preflight validation, disk spooling, and execution."""
        # 0. Session guard
        session_info = await self.store.get_session(str(action.session_id))
        if session_info and session_info.get("status") == "CLOSED":
            raise PermissionError(
                "Cannot execute actions in an archived session. Reopen the session first."
            )

        # 1. Variable substitution ($TARGET, $PORT, $LHOST, etc.)
        from cyguide.engine.network import get_lhost_info

        resolved_vars: Dict[str, Any] = {}
        if action.target_entity_id:
            node_data = await self.store.get_node(str(action.session_id), action.target_entity_id)
            if node_data:
                import json

                pik = json.loads(node_data.get("pik_json") or "{}")
                resolved_vars["TARGET"] = pik.get("ip") or pik.get("domain") or pik.get("host_ip")
                if "port" in pik:
                    resolved_vars["PORT"] = pik["port"]
                if "service" in pik:
                    resolved_vars["SERVICE"] = pik["service"]
                if "protocol" in pik:
                    resolved_vars["PROTOCOL"] = pik["protocol"]

        try:
            ip, iface = get_lhost_info()
            resolved_vars["LHOST"] = ip
            resolved_vars["IFACE"] = iface
        except Exception:
            pass

        raw_flags = action.params.get("raw_flags", "") if action.params else ""
        for var_name, val in resolved_vars.items():
            placeholder = f"${var_name}"
            if placeholder in raw_flags:
                raw_flags = raw_flags.replace(placeholder, str(val))
        if action.params:
            action.params["raw_flags"] = raw_flags

        # 2. Builtin 'cd' handling
        tool_data = self.registry.get_tool(action.tool_name)
        if not tool_data and action.tool_name == "cd":
            dest = raw_flags.strip()
            current = self.get_cwd(str(action.session_id))
            new_path = os.path.abspath(os.path.join(current, dest))
            if os.path.isdir(new_path):
                self.set_cwd(str(action.session_id), new_path)
                msg = f"Changed directory to: {new_path}\n"
            else:
                msg = f"cd: no such directory: {dest}\n"
            if on_chunk:
                await on_chunk(msg)
            return UUID(int=0)

        # 3. Determine Adapter
        if action.is_explicit_shell:
            action.params["raw_flags"] = f"{action.tool_name} {raw_flags}".strip()
            adapter = InternalShellAdapter()
        elif tool_data:
            action.params["raw_flags"] = raw_flags
            adapter = tool_data["adapter"]
        else:
            raise ValueError(f"No tool or explicit shell prefix found for '{action.tool_name}'")

        # 4. Preflight Validation
        try:
            await self.gateway.validate_action(action)
        except Exception as e:
            await self._emit_event(
                action.action_id, ExecutionFailed(action_id=action.action_id, error=str(e))
            )
            await self._emit_event(action.action_id, None)
            raise

        # 5. Job status initialization
        log_file_path = get_action_log_path(str(action.action_id))
        cmd_raw = action.params.get("raw_flags", "") if action.params else ""
        cmd_snippet = f"{action.tool_name} {cmd_raw}".strip() if cmd_raw else action.tool_name

        job = JobStatus(
            job_id=action.action_id,
            session_id=action.session_id,
            tool_name=action.tool_name,
            status=JobStatusEnum.RUNNING,
            log_file=log_file_path,
            command_snippet=cmd_snippet,
        )
        self._active_jobs[job.job_id] = job
        self._job_actions[job.job_id] = action
        self._job_buffers[job.job_id] = []
        self._notify_status(job)

        # 6. Resolve target finding
        if not action.is_explicit_shell and action.target_entity_id:
            import json

            node_data = await self.store.get_node(str(action.session_id), action.target_entity_id)
            target = BaseFinding(
                schema_type=node_data["schema_type"],
                pik=json.loads(node_data["pik_json"]),
                data=json.loads(node_data["data_json"]),
                status=node_data.get("status", "confirmed"),
            )
        else:
            target = BaseFinding(
                schema_type="system.shell",
                pik={"cmd": action.tool_name},
                data={},
                status="confirmed",
            )

        # 7. Privileged execution check (sudo)
        is_sudo = action.tool_name == "sudo"
        if is_sudo:
            # Handle sudo interactively using suspend context
            task = asyncio.create_task(
                self._run_privileged_action(
                    action, cmd_raw, log_file_path, job, suspend_context, on_chunk, on_complete
                )
            )
        else:
            # Handle regular background action
            task = asyncio.create_task(
                self._run_background_action(
                    action, adapter, target, log_file_path, job, on_chunk, on_complete
                )
            )

        self._running_tasks[action.action_id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(action.action_id, None))
        return job.job_id

    async def _append_chunk(
        self, action_id: UUID, text: str, log_file_path: str, is_error: bool = False
    ) -> None:
        buf = self._job_buffers.setdefault(action_id, [])
        buf.append(text)
        if len(buf) > 5000:
            self._job_buffers[action_id] = buf[-2500:]

        try:
            with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(text)
        except Exception:
            pass

        await self._emit_event(
            action_id, ExecutionChunk(action_id=action_id, text=text, is_error=is_error)
        )

    async def _run_privileged_action(
        self,
        action: ActionRequest,
        cmd_raw: str,
        log_file_path: str,
        job: JobStatus,
        suspend_context: Optional[TerminalSuspendContext],
        on_chunk: Optional[Callable[[str], Any]],
        on_complete: Optional[Callable[[], Any]],
    ) -> None:
        start_time = asyncio.get_event_loop().time()
        await self._emit_event(
            action.action_id,
            ExecutionStarted(
                action_id=action.action_id,
                tool_name="sudo",
                command_snippet=job.command_snippet,
                log_file=log_file_path,
            ),
        )

        ctx = suspend_context or DefaultSuspendContext()
        cmd_args = ["sudo"] + shlex.split(cmd_raw)
        clean_env = sanitize_subprocess_env(self.user_env)
        cwd = self.get_cwd(str(action.session_id))

        await self._append_chunk(
            action.action_id, f"❯ sudo {cmd_raw}\n[Suspending for sudo...]\n", log_file_path
        )
        if on_chunk:
            await on_chunk(f"❯ sudo {cmd_raw}\n[Suspending for sudo...]\n")

        returncode = 0
        err_msg = None
        try:
            with ctx.suspend():
                res = subprocess.run(cmd_args, shell=False, env=clean_env, cwd=cwd)
                returncode = res.returncode
            if returncode == 0:
                job.status = JobStatusEnum.DONE
                await self._append_chunk(
                    action.action_id, "[Resumed from sudo: Success]\n", log_file_path
                )
            else:
                job.status = JobStatusEnum.FAILED
                err_msg = f"Sudo command exited with code {returncode}"
                await self._append_chunk(
                    action.action_id,
                    f"[Resumed from sudo: Failed with code {returncode}]\n",
                    log_file_path,
                    is_error=True,
                )
        except Exception as e:
            job.status = JobStatusEnum.FAILED
            err_msg = str(e)
            await self._append_chunk(
                action.action_id, f"[Sudo execution error: {e}]\n", log_file_path, is_error=True
            )
        finally:
            elapsed = asyncio.get_event_loop().time() - start_time
            job.completed_at = datetime.now(UTC)
            self._notify_status(job)

            if job.status == JobStatusEnum.DONE:
                await self._emit_event(
                    action.action_id,
                    ExecutionCompleted(
                        action_id=action.action_id,
                        status=JobStatusEnum.DONE,
                        duration_seconds=elapsed,
                    ),
                )
            else:
                await self._emit_event(
                    action.action_id,
                    ExecutionFailed(
                        action_id=action.action_id,
                        error=err_msg or "Failed",
                        duration_seconds=elapsed,
                    ),
                )
            await self._emit_event(action.action_id, None)

            # Persist to database event log
            if not getattr(self.store, "_closed", False):
                try:
                    full_output = "".join(self.get_output_history(action.action_id))
                    await self.store.append_event(
                        str(action.session_id),
                        action,
                        {"output": full_output, "log_file": log_file_path, "error": err_msg},
                        f"Ran sudo {cmd_raw}" + (f" (failed: {err_msg})" if err_msg else ""),
                    )
                except Exception:
                    pass

            if on_complete:
                try:
                    await on_complete()
                except Exception:
                    pass

    async def _run_background_action(
        self,
        action: ActionRequest,
        adapter: ToolAdapter,
        target: BaseFinding,
        log_file_path: str,
        job: JobStatus,
        on_chunk: Optional[Callable[[str], Any]],
        on_complete: Optional[Callable[[], Any]],
    ) -> None:
        start_time = asyncio.get_event_loop().time()
        cwd = self.get_cwd(str(action.session_id))
        clean_env = sanitize_subprocess_env(self.user_env)

        # Log file header
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

        await self._emit_event(
            action.action_id,
            ExecutionStarted(
                action_id=action.action_id,
                tool_name=action.tool_name,
                command_snippet=job.command_snippet,
                log_file=log_file_path,
            ),
        )

        async def handle_stdout(text: str) -> None:
            await self._append_chunk(action.action_id, text, log_file_path, is_error=False)
            if on_chunk:
                try:
                    await on_chunk(text)
                except Exception:
                    pass

        async def handle_stderr(text: str) -> None:
            await self._append_chunk(action.action_id, text, log_file_path, is_error=True)
            if on_chunk:
                try:
                    await on_chunk(text)
                except Exception:
                    pass

        err_msg = None
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

        try:
            async for finding in self.runner.run(
                adapter=adapter,
                target=target,
                params=action.params,
                task_id=str(action.action_id),
                cwd=cwd,
                env=clean_env,
                use_shell=action.is_explicit_shell,
                shell_path=self.user_shell,
                on_output=handle_stdout,
                on_error_output=handle_stderr,
                timeout_seconds=getattr(action, "timeout_seconds", None),
            ):
                findings_count += 1
                finding_buffer.append(finding)
                now = asyncio.get_event_loop().time()
                if len(finding_buffer) >= 50 or (now - last_flush) >= 0.25:
                    await flush_findings()

            await flush_findings()
            if job.status == JobStatusEnum.RUNNING:
                job.status = JobStatusEnum.DONE
        except asyncio.CancelledError:
            err_msg = "Job cancelled"
            job.status = JobStatusEnum.FAILED
        except Exception as e:
            err_msg = str(e)
            job.status = JobStatusEnum.FAILED
        finally:
            elapsed = asyncio.get_event_loop().time() - start_time
            job.completed_at = datetime.now(UTC)

            # Record final status in disk log
            try:
                with open(log_file_path, "a", encoding="utf-8", errors="replace") as f:
                    status_str = (
                        "SUCCESS" if job.status == JobStatusEnum.DONE else f"FAILED ({err_msg})"
                    )
                    f.write(
                        f"\n\n=== Execution End: {datetime.now(UTC).isoformat()} [{status_str}] ===\n"
                    )
            except Exception:
                pass

            # Persist to database event log
            if not getattr(self.store, "_closed", False):
                try:
                    buf_output = "".join(self.get_output_history(action.action_id))
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
                        f"Ran {action.tool_name}" + (f" (failed: {err_msg})" if err_msg else ""),
                    )
                    if str(action.action_id) in self.closed_job_ids:
                        await self.store.mark_event_closed(
                            str(action.action_id), session_id=str(action.session_id)
                        )
                except Exception:
                    pass

            self._notify_status(job)

            if job.status == JobStatusEnum.DONE:
                await self._emit_event(
                    action.action_id,
                    ExecutionCompleted(
                        action_id=action.action_id,
                        status=JobStatusEnum.DONE,
                        findings_count=findings_count,
                        duration_seconds=elapsed,
                    ),
                )
            else:
                await self._emit_event(
                    action.action_id,
                    ExecutionFailed(
                        action_id=action.action_id,
                        error=err_msg or "Failed",
                        duration_seconds=elapsed,
                    ),
                )
            await self._emit_event(action.action_id, None)

            if on_complete:
                try:
                    await on_complete()
                except Exception:
                    pass

    async def kill_job(self, action_id: UUID) -> bool:
        """Cancel and terminate an active execution."""
        job = self.get_job(action_id)
        if not job or job.status != JobStatusEnum.RUNNING:
            return False

        try:
            await self.runner.stop(str(action_id))
        except Exception:
            pass
        task = self.get_running_task(action_id)
        if task and not task.done():
            task.cancel()

        job.status = JobStatusEnum.FAILED
        self._notify_status(job)
        return True

    async def shutdown(self) -> None:
        """Gracefully stop all running executions."""
        tasks = list(self._running_tasks.values())
        if tasks:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
