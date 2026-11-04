"""Subfinder tool adapter."""

import shutil
import re
from typing import AsyncIterator, List, Dict, Any
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DnsRecord


class SubfinderAdapter(ToolAdapter):
    """Adapter for the subfinder tool."""

    def validate_install(self) -> bool:
        return shutil.which("subfinder") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        args = ["subfinder"]
        
        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            import shlex
            
            domain = ""
            if target.schema_type == "domain.info":
                domain = target.pik.get("domain", "")
            elif target.schema_type == "dns.record":
                domain = target.pik.get("domain", "")
                
            tokens = shlex.split(raw_flags)
            resolved_tokens = [t.replace("{domain}", domain) for t in tokens if t]
            args.extend(resolved_tokens)
            
        return args

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        """
        Parser for subfinder output.
        Expects lines containing just the subdomains (if -silent is used) 
        or lines with subdomains among logging (which we filter out).
        Example line: api.example.com
        """
        # Basic regex for a domain name
        domain_pattern = re.compile(r"^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
        
        # ANSI escape sequence remover
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        for line in raw_stdout.splitlines():
            clean_line = ansi_escape.sub('', line).strip()
            
            # Skip subfinder banner/logging if not using -silent
            if not clean_line or clean_line.startswith("[") or clean_line.startswith("_"):
                continue
                
            if domain_pattern.match(clean_line):
                # We default to A record type as we just found a name, not necessarily knowing the type
                # Real DNS resolution would follow to confirm
                yield DnsRecord.create(
                    domain=clean_line,
                    record_type="A", # Assumption until resolved
                    value="unknown"  # Needs resolving
                )
