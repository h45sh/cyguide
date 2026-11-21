"""Nikto tool adapter."""

import re
import shlex
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.vulnerability import VulnerabilityFound
from cyguide.schemas.web import WebVulnerability


class NiktoAdapter(ToolAdapter):
    """Adapter for the nikto web scanner."""

    FINDING_PATTERN = re.compile(r"^\+ (.*)", re.MULTILINE)
    PATH_PATTERN = re.compile(r"^(/[\w\-\.\/]+):\s+(.*)")
    OSVDB_PATTERN = re.compile(r"^(OSVDB-\d+):\s+(.*)")

    def validate_install(self) -> bool:
        return self.is_binary_available("nikto")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip Nikto banners, informational headers, and run trailers."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if (
                s.startswith("- Nikto v")
                or s.startswith("+ Target IP:")
                or s.startswith("+ Target Hostname:")
                or s.startswith("+ Target Port:")
                or s.startswith("+ Start Time:")
                or s.startswith("+ End Time:")
                or "host(s) tested" in s
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        args = ["nikto"]

        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            if target.schema_type == "web.endpoint":
                target_str = target.pik.get("url", "")
            else:
                target_str = self.extract_host(target) or ""
            port_val = self.extract_port(target)
            port_str = str(port_val) if port_val else ""

            # Tokenize first to prevent argument injection from target_str or port_str
            tokens = shlex.split(raw_flags)
            resolved_tokens = []
            skip_next = False
            for i, token in enumerate(tokens):
                if skip_next:
                    skip_next = False
                    continue
                if token == "-p" and i + 1 < len(tokens) and tokens[i + 1] == "{port}":
                    if port_str:
                        resolved_tokens.extend(["-p", port_str])
                    skip_next = True
                    continue
                token = token.replace("{target}", target_str)
                token = token.replace("{port}", port_str)
                if token:
                    resolved_tokens.append(token)

            args.extend(resolved_tokens)

        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Regex parser for nikto output.

        Example line: + /admin/: Directory indexing found.
        Example line: + Server: Apache/2.4.41 (Ubuntu)
        Example line: + OSVDB-112004: /cgi-bin/test.cgi: Site appears vulnerable to the 'Shellshock' vulnerability.
        """
        # Try to extract base host/url from target or command
        base_host = self.extract_host(target) or ""
        base_url = (self.extract_url(target) or "").rstrip("/")

        for match in self.FINDING_PATTERN.finditer(raw_stdout):
            line = match.group(1).strip()

            # Skip informational headers
            if (
                line.startswith("Target IP:")
                or line.startswith("Target Hostname:")
                or line.startswith("Target Port:")
                or line.startswith("Start Time:")
                or line.startswith("End Time:")
                or "Nikto v" in line
                or "host(s) tested" in line
            ):
                continue

            osvdb_match = self.OSVDB_PATTERN.search(line)
            if osvdb_match:
                vuln_id = osvdb_match.group(1)
                desc = osvdb_match.group(2)

                # Check if it has a path
                path_match = self.PATH_PATTERN.search(desc)
                if path_match and base_url:
                    path = path_match.group(1)
                    finding = path_match.group(2)
                    yield WebVulnerability.create(
                        url=f"{base_url}{path}", vuln_type=vuln_id, description=finding
                    )
                elif base_host:
                    yield VulnerabilityFound.create(
                        host_ip=base_host, vuln_id=vuln_id, severity="unknown", description=desc
                    )
            else:
                path_match = self.PATH_PATTERN.search(line)
                if path_match and base_url:
                    path = path_match.group(1)
                    desc = path_match.group(2)
                    yield WebVulnerability.create(
                        url=f"{base_url}{path}", vuln_type="misconfiguration", description=desc
                    )
                elif path_match and base_host:
                    path = path_match.group(1)
                    desc = path_match.group(2)
                    yield VulnerabilityFound.create(
                        host_ip=base_host,
                        vuln_id="misconfiguration",
                        severity="info",
                        description=f"{path}: {desc}",
                    )
                elif base_host:
                    # Generic host/service finding
                    if "Server:" in line or "Retrieved x-powered-by" in line:
                        yield VulnerabilityFound.create(
                            host_ip=base_host,
                            vuln_id="info_disclosure",
                            severity="info",
                            description=line,
                        )
