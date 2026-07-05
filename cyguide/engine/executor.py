"""Asynchronous tool execution engine."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Callable, Coroutine
from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.store import GraphStore
from cyguide.schemas.base import BaseFinding

logger = logging.getLogger(__name__)

class Executor:
    """Executes tools and manages their lifecycle and output persistence."""

    def __init__(self, store: GraphStore):
        self.store = store
        self._active_processes: Dict[str, asyncio.subprocess.Process] = {}

    async def stop_task(self, task_id: str) -> None:
        """Forcefully terminate a specific running task."""
        process = self._active_processes.pop(task_id, None)
        if process:
            try:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                logger.info(f"Terminated process for task {task_id}")
            except Exception as e:
                logger.error(f"Error terminating process: {e}")

    async def stop_tool(self, session_id: str) -> None:
        """Backward compatible: stop tool by session_id."""
        await self.stop_task(session_id)

    async def shutdown(self) -> None:
        """Forcefully terminate all active tool processes."""
        tasks = list(self._active_processes.keys())
        for task_id in tasks:
            await self.stop_task(task_id)

    async def run_tool(
        self, 
        adapter: ToolAdapter, 
        target: BaseFinding, 
        params: Dict[str, Any],
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        use_shell: bool = False,
        shell_path: Optional[str] = None,
        on_milestone: Optional[Callable[[str, Dict[str, Any]], Coroutine]] = None,
        on_output: Optional[Callable[[str], Coroutine]] = None,
        on_error_output: Optional[Callable[[str], Coroutine]] = None
    ) -> AsyncIterator[BaseFinding]:
        """
        Execute a tool adapter against a target finding and yield findings.
        """
        if not adapter.validate_install():
            raise RuntimeError(f"Tool binary for {adapter.__class__.__name__} not found on system.")

        tracking_id = task_id or session_id

        command = adapter.build_command(target, params)
        cmd_str = ' '.join(command)
        
        if use_shell:
            final_cmd = [shell_path or "/bin/bash", "-c", cmd_str]
            process = await asyncio.create_subprocess_exec(
                *final_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=env
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=cwd,
                env=env
            )
        
        if tracking_id:
            self._active_processes[tracking_id] = process

        service_count = 0
        first_service_found = False

        # Internal queue to bridge stream readers and findings generator
        finding_queue = asyncio.Queue()
        parsing_context = {"params": params} # Shared context for the duration of this tool run

        async def _drain_stream(stream, callback, is_stdout=True):
            buffer = ""
            try:
                while True:
                    # Use smaller chunks for more frequent UI updates
                    chunk = await stream.read(1024)
                    if not chunk:
                        # Process any remaining text in the buffer as a final line
                        if buffer and is_stdout:
                            async for finding in adapter.parse_output(buffer, target, context=parsing_context):
                                await finding_queue.put(finding)
                        break
                    
                    raw_text = chunk.decode(errors="replace")
                    if callback:
                        await callback(raw_text)
                    elif on_output:
                        await on_output(raw_text)
                    
                    # Tool parsing only on stdout
                    if is_stdout:
                        buffer += raw_text
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            try:
                                async for finding in adapter.parse_output(line, target, context=parsing_context):
                                    await finding_queue.put(finding)
                            except Exception as parse_e:
                                logger.error(f"Error parsing line '{line}': {parse_e}")
            except Exception as e:
                logger.error(f"Error draining stream: {e}")

        # Start drain tasks
        stdout_task = asyncio.create_task(_drain_stream(process.stdout, on_output, is_stdout=True))
        stderr_task = asyncio.create_task(_drain_stream(process.stderr, on_error_output or on_output, is_stdout=False))

        try:
            # Wait for process and stream tasks to finish
            # We don't use gather directly because we want to yield as findings arrive
            while not (stdout_task.done() and stderr_task.done() and process.returncode is not None):
                try:
                    # Wait for finding or a small timeout to check process state
                    finding = await asyncio.wait_for(finding_queue.get(), timeout=0.1)
                    
                    if session_id:
                        try:
                            await self.store.upsert_finding(session_id, finding)
                        except Exception as upsert_e:
                            logger.error(f"Failed to upsert finding: {upsert_e}")
                            if on_output:
                                await on_output(f"\n[INTERNAL ERROR] Failed to save entity: {upsert_e}\n")
                            raise # Re-raise to ensure job fails but we see the cause
                    
                    if finding.schema_type == "network.service":
                        service_count += 1
                        if not first_service_found:
                            first_service_found = True
                            if on_milestone:
                                await on_milestone("first_service", finding.data)
                    
                    yield finding
                except asyncio.TimeoutError:
                    # Just checking if process finished
                    if process.returncode is None:
                        # Check if process actually finished while we were waiting
                        # but it might still have data in pipes
                        pass
                
                # Check process return code
                if process.returncode is None:
                    try:
                        # Non-blocking wait
                        await asyncio.wait_for(process.wait(), timeout=0.01)
                    except asyncio.TimeoutError:
                        pass

            # Final check of the queue for any remaining findings
            while not finding_queue.empty():
                finding = finding_queue.get_nowait()
                if session_id:
                    try:
                        await self.store.upsert_finding(session_id, finding)
                    except Exception as upsert_e:
                        logger.error(f"Failed to upsert finding: {upsert_e}")
                        if on_output:
                            await on_output(f"\n[INTERNAL ERROR] Failed to save entity: {upsert_e}\n")
                        raise
                if finding.schema_type == "network.service":
                    service_count += 1
                    if not first_service_found:
                        first_service_found = True
                        if on_milestone:
                            await on_milestone("first_service", finding.data)
                yield finding

        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
            raise
        finally:
            if tracking_id:
                self._active_processes.pop(tracking_id, None)
            
            # Ensure readers are cleaned up
            stdout_task.cancel()
            stderr_task.cancel()
            
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except:
                    pass
            
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        if process.returncode != 0:
            logger.error(f"Command failed with exit code {process.returncode}")
            if process.returncode == 127:
                raise RuntimeError(f"Tool not found: {command[0]}")
        
        if process.returncode == 0:
            if on_milestone:
                target_ip = target.pik.get("ip") or target.pik.get("domain", "target")
                await on_milestone("scan_complete", {
                    "target_ip": target_ip,
                    "service_count": service_count
                })
