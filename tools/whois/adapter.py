"""Whois tool adapter."""

import re
import shutil
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DomainInfo
from cyguide.schemas.netblock import NetworkNetblock
from cyguide.schemas.network import NetworkHost


class WhoisAdapter(ToolAdapter):
    """Adapter for the whois client."""

    def validate_install(self) -> bool:
        return shutil.which("whois") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # target can be dns.record (use domain) or network.host (use ip)
        query = None
        if target.schema_type == "dns.record":
            query = target.pik.get("domain")
        elif target.schema_type == "network.host":
            query = target.pik.get("ip")
            
        args = ["whois"]
        
        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            import shlex
            args.extend(shlex.split(raw_flags))
            
        if query:
            args.append(query)
        elif not raw_flags:
            raise ValueError(f"Target finding {target.schema_type} missing query field (domain/ip), and no flags provided.")
            
        return args

    async def parse_output(self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None) -> AsyncIterator[BaseFinding]:
        """Parse whois output for registrar, organization, and IP info."""
        
        registrar = self._extract(raw_stdout, r"Registrar:\s*(.*)")
        org = self._extract(raw_stdout, r"(?:Organization|Registrant Organization):\s*(.*)")
        cidr = self._extract(raw_stdout, r"(?:CIDR|NetRange):\s*(.*)")
        
        # 1. If we queried a domain, emit DomainInfo
        if target.schema_type == "dns.record":
            domain = target.pik.get("domain")
            yield DomainInfo.create(
                domain=domain,
                registrar=registrar,
                organization=org
            )
            
        # 2. Emit Netblock info if found
        if cidr or org:
            yield NetworkNetblock.create(cidr=cidr or "Unknown", organization=org)

        # 3. Emit host enrichment finding
        if target.schema_type == "network.host":
            ip = target.pik.get("ip")
            yield NetworkHost.create(ip=ip)

    def _extract(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None
