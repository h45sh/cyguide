"""Subfinder tool adapter."""

import re
import shlex
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DnsRecord


class SubfinderAdapter(ToolAdapter):
    """Adapter for the subfinder tool."""

    DOMAIN_RE = re.compile(r"^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")

    def validate_install(self) -> bool:
        return self.is_binary_available("subfinder")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip subfinder ASCII art banners, progress lines, and diagnostic logging."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if (
                s.startswith("[")
                or s.startswith("_")
                or s.startswith("::")
                or "subfinder" in s.lower()
                and ("projectdiscovery" in s.lower() or "version" in s.lower())
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        args = ["subfinder"]

        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            domain = self.extract_domain(target) or ""
            tokens = shlex.split(raw_flags)
            resolved_tokens = [t.replace("{domain}", domain) for t in tokens if t]
            args.extend(resolved_tokens)

        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parser for subfinder output.

        Expects lines containing just the subdomains (if -silent is used)
        or lines with subdomains among logging (which we filter out).
        Example line: api.example.com
        """
        for line in raw_stdout.splitlines():
            clean_line = self.strip_ansi(line).strip()

            # Skip subfinder banner/logging if not using -silent
            if not clean_line or clean_line.startswith("[") or clean_line.startswith("_"):
                continue

            if self.DOMAIN_RE.match(clean_line):
                # We default to A record type as we just found a name, not necessarily knowing the type
                # Real DNS resolution would follow to confirm
                yield DnsRecord.create(
                    domain=clean_line,
                    record_type="A",  # Assumption until resolved
                    value="unknown",  # Needs resolving
                )
