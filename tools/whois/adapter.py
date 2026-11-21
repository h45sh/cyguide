"""Whois tool adapter."""

import re
import shlex
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DomainInfo
from cyguide.schemas.network import NetworkHost, NetworkNetblock


class WhoisAdapter(ToolAdapter):
    """Adapter for the whois client."""

    REGISTRAR_PATTERN = re.compile(r"Registrar:\s*(.*)", re.IGNORECASE)
    ORG_PATTERN = re.compile(r"(?:Organization|Registrant Organization):\s*(.*)", re.IGNORECASE)
    CIDR_PATTERN = re.compile(r"(?:CIDR|NetRange):\s*(.*)", re.IGNORECASE)

    def validate_install(self) -> bool:
        return self.is_binary_available("whois")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip whois legal disclaimers, boilerplate, and comment blocks."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if s.startswith("%") or s.startswith("#") or "TERMS OF USE" in s.upper():
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        # target can be dns.record (use domain) or network.host (use ip)
        query = self.extract_domain(target) or self.extract_host(target)

        args = ["whois"]

        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            args.extend(shlex.split(raw_flags))

        if query:
            args.append(query)
        elif not raw_flags:
            raise ValueError(
                f"Target finding {target.schema_type} missing query field (domain/ip), and no flags provided."
            )

        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse whois output for registrar, organization, and IP info."""

        registrar = self._extract(raw_stdout, self.REGISTRAR_PATTERN)
        org = self._extract(raw_stdout, self.ORG_PATTERN)
        cidr = self._extract(raw_stdout, self.CIDR_PATTERN)

        # 1. If we queried a domain, emit DomainInfo
        if target.schema_type == "dns.record":
            domain = target.pik.get("domain")
            yield DomainInfo.create(domain=domain, registrar=registrar, organization=org)

        # 2. Emit Netblock info if found
        if cidr or org:
            yield NetworkNetblock.create(cidr=cidr or "Unknown", organization=org)

        # 3. Emit host enrichment finding
        if target.schema_type == "network.host":
            ip = target.pik.get("ip")
            yield NetworkHost.create(ip=ip)

    def _extract(self, text: str, pattern: Any) -> Optional[str]:
        if isinstance(pattern, str):
            match = re.search(pattern, text, re.IGNORECASE)
        else:
            match = pattern.search(text)
        return match.group(1).strip() if match else None
