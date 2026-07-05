"""Nmap tool adapter."""

import shutil
import re
from typing import AsyncIterator, List, Dict, Any
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.network import NetworkService, NetworkHost


class NmapAdapter(ToolAdapter):
    """Adapter for the nmap port scanner."""

    def validate_install(self) -> bool:
        return shutil.which("nmap") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # target is expected to be a network.host, but might be dummy in manual mode
        ip = target.pik.get("ip")
        
        args = ["nmap"]
        
        # Handle manual raw flags from UI
        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            import shlex
            args.extend(shlex.split(raw_flags))
            
        if ip:
            args.append(ip)
        elif not raw_flags:
            raise ValueError("Target finding must have an IP address, or provide one in the command flags.")
            
        return args

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        """
        Simple regex parser for nmap output.
        Example line: 80/tcp open  http
        """
        context = context or {}
        
        # 1. Check if we just discovered a host report line (Nmap scan report for 127.0.0.1)
        # This is critical for manual shell scans where the target finding is dummy.
        report_pattern = re.compile(r"Nmap scan report for (?:[^\s(]+\s+)?\(?([^\s)]+)\)?")
        
        # 2. Regex to match: PORT/PROTO STATE SERVICE
        port_pattern = re.compile(r"(\d+)/(tcp|udp)\s+open\s+(\S+)")
        
        for line in raw_stdout.splitlines():
            # Host discovery
            host_match = report_pattern.search(line)
            if host_match:
                host_ip = host_match.group(1)
                context["current_host_ip"] = host_ip
                yield NetworkHost.create(ip=host_ip)
                continue

            # Port discovery
            port_match = port_pattern.search(line)
            if port_match:
                # Priority: 1. Host from output context, 2. Host from target PIK, 3. Host from raw flags
                host_ip = context.get("current_host_ip") or target.pik.get("ip")
                
                if not host_ip:
                    # Fallback: Try to find IP in raw flags if it is a manual scan
                    raw_flags = context.get("params", {}).get("raw_flags", "")
                    ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", raw_flags)
                    if ip_match:
                        host_ip = ip_match.group(1)
                        context["current_host_ip"] = host_ip

                if host_ip:
                    port = int(port_match.group(1))
                    protocol = port_match.group(2)
                    service = port_match.group(3)
                    
                    yield NetworkService.create(
                        host_ip=host_ip,
                        port=port,
                        protocol=protocol,
                        service_name=service
                    )
