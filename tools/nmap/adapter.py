"""Nmap tool adapter."""

import shutil
import re
from typing import AsyncIterator, List, Dict, Any
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.network import NetworkService


class NmapAdapter(ToolAdapter):
    """Adapter for the nmap port scanner."""

    def validate_install(self) -> bool:
        return shutil.which("nmap") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # target is expected to be a network.host
        ip = target.pik.get("ip")
        if not ip:
            raise ValueError("Target finding must have an IP address.")
        
        args = ["nmap"]
        
        # Handle manual raw flags from UI
        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            # Simple split by space; in a real app, use shlex.split for safety
            import shlex
            args.extend(shlex.split(raw_flags))
            
        args.append(ip)
        return args

    async def parse_output(self, raw_stdout: str, target: BaseFinding) -> AsyncIterator[BaseFinding]:
        """
        Simple regex parser for nmap output.
        Example line: 80/tcp open  http
        """
        host_ip = target.pik.get("ip")
        
        # Regex to match: PORT/PROTO STATE SERVICE
        pattern = re.compile(r"(\d+)/(tcp|udp)\s+open\s+(\S+)")
        
        for line in raw_stdout.splitlines():
            match = pattern.search(line)
            if match:
                port = int(match.group(1))
                protocol = match.group(2)
                service = match.group(3)
                
                yield NetworkService.create(
                    host_ip=host_ip,
                    port=port,
                    protocol=protocol,
                    service_name=service
                )
