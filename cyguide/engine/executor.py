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

    async def stop_tool(self, session_id: str) -> None:
        """Forcefully terminate a running tool session."""
        process = self._active_processes.pop(session_id, None)
        if process:
            try:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                logger.info(f"Terminated process for session {session_id}")
            except Exception as e:
                logger.error(f"Error terminating process: {e}")


    async def shutdown(self) -> None:
        """Forcefully terminate all active tool processes."""
        sessions = list(self._active_processes.keys())
        for session_id in sessions:
            await self.stop_tool(session_id)

    async def run_tool(
        self, 
        adapter: ToolAdapter, 
        target: BaseFinding, 
        params: Dict[str, Any],
        session_id: Optional[str] = None,
        on_milestone: Optional[Callable[[str, Dict[str, Any]], Coroutine]] = None,
        on_output: Optional[Callable[[str], Coroutine]] = None
    ) -> AsyncIterator[BaseFinding]:
        """
        Execute a tool adapter against a target finding and yield findings.
        """
        if not adapter.validate_install():
            raise RuntimeError(f"Tool binary for {adapter.__class__.__name__} not found on system.")

        command = adapter.build_command(target, params)
        cmd_str = ' '.join(command)
        logger.info(f"Executing command: {cmd_str}")
        if on_output:
            await on_output(f"Executing: {cmd_str}\n\n")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        if session_id:
            self._active_processes[session_id] = process

        first_service_found = False
        service_count = 0

        async def read_stderr():
            try:
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    if on_output:
                        await on_output(line.decode())
                    await asyncio.sleep(0.01) # Yield to event loop
            except asyncio.CancelledError:
                pass

        # Start stderr reader in background
        stderr_task = asyncio.create_task(read_stderr())

        try:
            # Stream stdout line-by-line in the main loop
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                    
                raw_line = line.decode()
                if on_output:
                    await on_output(raw_line)
                
                await asyncio.sleep(0.01) # Yield to event loop
                    
                async for finding in adapter.parse_output(raw_line, target):
                    if session_id:
                        await self.store.upsert_finding(session_id, finding)
                    
                    # Milestone Detection: first_service
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
            # Safe cleanup
            self._active_processes.pop(session_id, None)
            
            stderr_task.cancel()
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except:
                    pass
            
            try:
                await stderr_task
            except asyncio.CancelledError:
                pass
        
        if process.returncode != 0:
            logger.error(f"Command failed with exit code {process.returncode}")
            if process.returncode == 127:
                raise RuntimeError(f"Tool not found: {command[0]}")
        
        if process.returncode == 0:
            if on_milestone:
                # Milestone Detection: scan_complete
                target_ip = target.pik.get("ip") or target.pik.get("domain", "target")
                await on_milestone("scan_complete", {
                    "target_ip": target_ip,
                    "service_count": service_count
                })
