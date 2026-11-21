"""SQLMap tool adapter."""

import re
import shlex
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.wordlists import substitute_wordlist_macros
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.web import WebVulnerability


class SqlmapAdapter(ToolAdapter):
    """Adapter for the sqlmap automated SQL injection tool."""

    PARAM_RE = re.compile(r"Parameter:\s*([^\s\(]+)(?:\s*\(([^)]+)\))?", re.IGNORECASE)
    TYPE_RE = re.compile(r"Type:\s*(.+)", re.IGNORECASE)
    TITLE_RE = re.compile(r"Title:\s*(.+)", re.IGNORECASE)
    PAYLOAD_RE = re.compile(r"Payload:\s*(.+)", re.IGNORECASE)
    DBMS_RE = re.compile(r"(?:back-end DBMS:\s*|the back-end DBMS is\s*)([^\r\n]+)", re.IGNORECASE)
    TECH_RE = re.compile(r"web application technology:\s*(.+)", re.IGNORECASE)
    CRED_RE = re.compile(
        r"\[\*\]\s*([^\s:\[]+)\s*(?:\[\d+\])?:\s*[\r\n]+\s*(?:password hash:\s*|clear-text password:\s*)([^\r\n]+)",
        re.IGNORECASE,
    )

    def validate_install(self) -> bool:
        """Check if sqlmap executable is in system PATH."""
        return self.is_binary_available("sqlmap")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip SQLMap ASCII art logo, disclaimer, and progress counters."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            # Filter figlet banners, URLs, legal disclaimers, or noise lines
            if (
                s.startswith("___")
                or s.startswith("|_")
                or s.startswith("__H__")
                or "sqlmap.org" in s
                or "[*] starting @" in s
                or "[*] ending @" in s
                or s.startswith("[!] legal disclaimer")
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct the sqlmap CLI execution command."""
        url = self.extract_url(target)

        raw_flags = params.get("raw_flags", "").strip()
        raw_flags, _ = substitute_wordlist_macros(raw_flags)
        flag_args = shlex.split(raw_flags) if raw_flags else []

        args = ["sqlmap"]

        # 1. Enforce non-interactive batch mode to avoid stdin blocking
        if "--batch" not in flag_args and "-b" not in flag_args:
            args.append("--batch")

        # 2. Enforce target URL
        has_u = any(flag_args[i] in ("-u", "--url") for i in range(len(flag_args)))
        if not has_u:
            if not url:
                raise ValueError(
                    f"Target finding {target.schema_type} has no valid URL or host identifier, and no -u flag provided."
                )
            args.extend(["-u", url])

        args.extend(flag_args)
        return args

    def _extract_url(self, target: BaseFinding) -> Optional[str]:
        return self.extract_url(target)

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse SQLMap stdout to extract identified SQLi vulnerabilities and dumped credentials."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        target_url = self.extract_url(target) or "http://target"
        host_ip = (
            target.pik.get("host_ip")
            or target.pik.get("ip")
            or target.data.get("host_ip")
            or target.data.get("ip")
        )

        # 1. Extract DBMS and technology fingerprints
        dbms = None
        dbms_match = self.DBMS_RE.search(cleaned)
        if dbms_match:
            dbms = dbms_match.group(1).strip()

        tech = None
        tech_match = self.TECH_RE.search(cleaned)
        if tech_match:
            tech = tech_match.group(1).strip()

        # 2. Extract injection points
        # Split by sections or parse iteratively
        current_param = None
        current_type = None
        current_title = None
        current_payload = None

        seen_params = set()

        for line in cleaned.splitlines():
            line_str = line.strip()

            param_match = self.PARAM_RE.search(line_str)
            if param_match:
                # If we had a previous finding assembled, yield it
                if current_param and (current_type or current_payload):
                    key = (target_url, current_param, current_type)
                    if key not in seen_params:
                        seen_params.add(key)
                        yield WebVulnerability.create(
                            url=target_url,
                            vuln_type="SQL Injection",
                            parameter=current_param,
                            technique=current_type or "Unknown",
                            title=current_title or "SQL Injection",
                            payload=current_payload or "",
                            dbms=dbms,
                            technology=tech,
                            severity="high",
                            description=(
                                f"SQL injection detected on parameter '{current_param}' "
                                f"using technique '{current_type or 'Unknown'}'. DBMS: {dbms or 'Unknown'}."
                            ),
                        )

                current_param = param_match.group(1)
                current_type = None
                current_title = None
                current_payload = None
                continue

            type_match = self.TYPE_RE.search(line_str)
            if type_match:
                current_type = type_match.group(1).strip()
                continue

            title_match = self.TITLE_RE.search(line_str)
            if title_match:
                current_title = title_match.group(1).strip()
                continue

            payload_match = self.PAYLOAD_RE.search(line_str)
            if payload_match:
                current_payload = payload_match.group(1).strip()
                # Once we have param + type + payload, yield finding
                if current_param:
                    key = (target_url, current_param, current_type)
                    if key not in seen_params:
                        seen_params.add(key)
                        yield WebVulnerability.create(
                            url=target_url,
                            vuln_type="SQL Injection",
                            parameter=current_param,
                            technique=current_type or "Unknown",
                            title=current_title or "SQL Injection",
                            payload=current_payload or "",
                            dbms=dbms,
                            technology=tech,
                            severity="high",
                            description=(
                                f"SQL injection detected on parameter '{current_param}' "
                                f"using technique '{current_type or 'Unknown'}'. DBMS: {dbms or 'Unknown'}."
                            ),
                        )

        # Catch any trailing parameter finding
        if current_param and (current_type or current_payload):
            key = (target_url, current_param, current_type)
            if key not in seen_params:
                seen_params.add(key)
                yield WebVulnerability.create(
                    url=target_url,
                    vuln_type="SQL Injection",
                    parameter=current_param,
                    technique=current_type or "Unknown",
                    title=current_title or "SQL Injection",
                    payload=current_payload or "",
                    dbms=dbms,
                    technology=tech,
                    severity="high",
                    description=(
                        f"SQL injection detected on parameter '{current_param}' "
                        f"using technique '{current_type or 'Unknown'}'. DBMS: {dbms or 'Unknown'}."
                    ),
                )

        # 3. Extract dumped database user credentials
        for cred_match in self.CRED_RE.finditer(cleaned):
            username = cred_match.group(1).strip()
            password_hash = cred_match.group(2).strip()
            if username and password_hash:
                yield CredentialFound.create(
                    context=f"db://{dbms or 'database'}",
                    username=username,
                    password=password_hash,
                    host_ip=host_ip,
                    credential_type="hash",
                )
