"""Pure-Python DNS Probe tool adapter."""

import json
import shlex
import sys
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DnsRecord


class DnsPythonAdapter(ToolAdapter):
    """Adapter for the dnspython query and zone transfer engine."""

    def validate_install(self) -> bool:
        """Dnspython is a bundled Python dependency, always valid if importable."""
        try:
            import dns.resolver  # noqa: F401

            return True
        except ImportError:
            return False

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct the CLI command using Python's module invocation."""
        query: Optional[str] = None
        if target.schema_type == "dns.record":
            query = target.pik.get("domain")
        elif target.schema_type == "network.host":
            query = target.pik.get("ip")

        raw_flags = params.get("raw_flags", "").strip()
        flag_args = shlex.split(raw_flags) if raw_flags else []

        # If user did not provide target query inside flags, attach resolved query
        args = [sys.executable, "-m", "tools.dnspython.cli"]

        if query:
            args.append(query)
        elif not flag_args:
            raise ValueError(
                f"Target finding {target.schema_type} missing query field (domain/ip), and no flags provided."
            )

        # Enforce json output for reliable programmatic parsing
        if "--json" not in flag_args:
            args.append("--json")

        args.extend(flag_args)
        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse structured JSON records into DnsRecord findings."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        try:
            records = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback in case non-JSON diagnostic messages were printed before the JSON block
            start_bracket = cleaned.find("[")
            end_bracket = cleaned.rfind("]")
            if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                try:
                    records = json.loads(cleaned[start_bracket : end_bracket + 1])
                except json.JSONDecodeError:
                    return
            else:
                return

        if not isinstance(records, list):
            records = [records]

        for item in records:
            if not isinstance(item, dict):
                continue
            # Skip error notices that did not produce a record value
            if "value" not in item or not item.get("value"):
                continue

            domain_name = item.get("name", "").rstrip(".")
            rtype = item.get("type", "A").upper()
            val = str(item["value"]).rstrip(".")
            ttl = int(item.get("ttl", 300))

            resolved_ip = val if rtype == "A" else None
            yield DnsRecord.create(
                domain=domain_name,
                record_type=rtype,
                value=val,
                resolved_ip=resolved_ip,
            )
