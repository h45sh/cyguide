"""Gobuster tool adapter."""

import os
import shutil
import shlex
import re
from typing import AsyncIterator, List, Dict, Any
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.web import WebEndpoint


class GobusterAdapter(ToolAdapter):
    """Adapter for the gobuster directory brute-forcing tool."""

    def validate_install(self) -> bool:
        return shutil.which("gobuster") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        args = ["gobuster"]
        
        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            # Replace {url} placeholder if present in recipe flags
            url = ""
            if target.schema_type == "web.endpoint":
                url = target.pik.get("url", "")
            elif target.schema_type == "network.service":
                port = target.pik.get("port")
                ip = target.pik.get("host_ip")
                scheme = "https" if port in (443, 8443) else "http"
                url = f"{scheme}://{ip}:{port}"
                
            raw_flags = raw_flags.replace("{url}", url)
            
            if "{wordlist}" in raw_flags:
                wordlist_path = os.path.join(os.path.dirname(__file__), "wordlist.txt")
                raw_flags = raw_flags.replace("{wordlist}", wordlist_path)
                
            args.extend(shlex.split(raw_flags))
            
        return args

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        """
        Regex parser for gobuster output.
        Example line: /admin (Status: 200) [Size: 1234]
        """
        context = context or {}
        
        # Base URL to construct full URLs
        base_url = ""
        if target and target.schema_type == "web.endpoint":
            base_url = target.pik.get("url", "").rstrip("/")
        elif target and target.schema_type == "network.service":
            port = target.pik.get("port")
            ip = target.pik.get("host_ip")
            scheme = "https" if port in (443, 8443) else "http"
            base_url = f"{scheme}://{ip}:{port}"
            
        # Try to extract base url from command params if not available
        if not base_url:
            raw_flags = context.get("params", {}).get("raw_flags", "")
            url_match = re.search(r"-u\s+([^\s]+)", raw_flags)
            if url_match:
                base_url = url_match.group(1).rstrip("/")
        
        # Regex to match: /path (Status: 200) ...
        # Match both colored and non-colored output by stripping ANSI later, or regex for raw string
        pattern = re.compile(r"(\S+)\s+\(Status:\s+(\d+)\)")
        
        # Helper to strip ansi codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        for line in raw_stdout.splitlines():
            clean_line = ansi_escape.sub('', line)
            
            match = pattern.search(clean_line)
            if match:
                path = match.group(1)
                status_code = int(match.group(2))
                
                full_url = f"{base_url}{path}" if base_url else path
                
                yield WebEndpoint.create(
                    url=full_url,
                    method="GET",
                    status_code=status_code
                )
