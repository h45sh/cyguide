"""SearchSploit Exploit-DB tool adapter."""

import json
import re
import shlex
import shutil
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.vulnerability import ExploitReference


class SearchSploitAdapter(ToolAdapter):
    """Adapter for the searchsploit local exploit query utility."""

    def validate_install(self) -> bool:
        """Verify searchsploit binary is present in system PATH."""
        return shutil.which("searchsploit") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct the searchsploit command line arguments."""
        args = ["searchsploit", "--json"]

        raw_flags = params.get("raw_flags", "").strip()
        flag_args = shlex.split(raw_flags) if raw_flags else []

        # If user explicitly provided flags, incorporate them
        for f in flag_args:
            if f != "--json" and f not in args:
                args.append(f)

        # Derive target query if not explicitly passed in raw flags
        if not raw_flags or not any(not flag.startswith("-") for flag in flag_args):
            query_parts = self._extract_query_parts(target)
            if not query_parts:
                raise ValueError(
                    f"Target finding {target.schema_type} does not contain recognizable service or CVE metadata."
                )
            args.extend(query_parts)

        return args

    def _extract_query_parts(self, target: BaseFinding) -> List[str]:
        if target.schema_type == "network.service":
            sname = target.data.get("service_name") or target.pik.get("service_name") or ""
            version = target.data.get("version") or ""
            query = f"{sname} {version}".strip()
            return [query] if query else []

        if target.schema_type == "vulnerability.found":
            vuln_id = target.pik.get("vuln_id") or target.data.get("vuln_id") or ""
            if vuln_id.upper().startswith("CVE-"):
                return ["--cve", vuln_id]
            return [vuln_id] if vuln_id else []

        if target.schema_type == "network.host":
            hostname = target.data.get("hostname")
            return [hostname] if hostname else []

        return []

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse searchsploit JSON results into ExploitReference finding models."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Handle possible non-JSON headers before the main JSON payload
            start_bracket = cleaned.find("{")
            end_bracket = cleaned.rfind("}")
            if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                try:
                    data = json.loads(cleaned[start_bracket : end_bracket + 1])
                except json.JSONDecodeError:
                    return
            else:
                return

        if not isinstance(data, dict):
            return

        results = data.get("RESULTS_EXPLOIT", [])
        if not isinstance(results, list):
            return

        # Contextual connection metadata from target
        host_ip = target.pik.get("host_ip") or target.pik.get("ip") or target.data.get("host_ip")
        port = target.pik.get("port") or target.data.get("port")
        vuln_id = target.pik.get("vuln_id") or target.data.get("vuln_id")

        for item in results:
            if not isinstance(item, dict):
                continue

            edb_id = str(item.get("EDB-ID", "")).strip()
            title = str(item.get("Title", "")).strip()
            if not edb_id or not title:
                continue

            exploit_id = f"EDB-{edb_id}"
            platform = item.get("Platform")
            exploit_type = item.get("Type")
            file_path = item.get("Path")
            verified_val = str(item.get("Verified", "0")).strip().lower()
            verified = verified_val in ("1", "true", "yes")

            # Extract primary CVE code if present in "Codes" field
            codes = str(item.get("Codes", ""))
            cve_match = re.search(r"CVE-\d{4}-\d+", codes, re.IGNORECASE)
            cve_id = cve_match.group(0).upper() if cve_match else None

            yield ExploitReference.create(
                exploit_id=exploit_id,
                title=title,
                cve_id=cve_id,
                platform=platform,
                exploit_type=exploit_type,
                verified=verified,
                file_path=file_path,
                host_ip=host_ip,
                port=port,
                vuln_id=vuln_id,
            )
