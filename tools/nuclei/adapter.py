"""Nuclei vulnerability scanner adapter."""

import json
import shlex
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.vulnerability import AuditMisconfig, VulnerabilityFound
from cyguide.schemas.web import WebTechnology


class NucleiAdapter(ToolAdapter):
    """Adapter for ProjectDiscovery Nuclei vulnerability scanner."""

    def validate_install(self) -> bool:
        """Verify nuclei binary is available on system PATH."""
        return self.is_binary_available("nuclei")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Filter verbose nuclei loading stats, update notices, and template clusters."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if any(
                s.startswith(p)
                for p in (
                    "[INF] Current nuclei version",
                    "[INF] New templates",
                    "[INF] Loading templates",
                    "[INF] Templates cluster",
                    "[INF] Using",
                )
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct nuclei execution command with streaming JSONL output."""
        url = self.extract_url(target)

        raw_flags = params.get("raw_flags", "").strip()
        flag_args = shlex.split(raw_flags) if raw_flags else []

        args = ["nuclei"]

        has_target = any(
            flag_args[i] in ("-u", "-target", "-list", "-l") for i in range(len(flag_args))
        )
        if not has_target:
            if not url:
                raise ValueError(
                    f"Target finding {target.schema_type} does not specify a valid URL or host."
                )
            args.extend(["-u", url])

        if "-jsonl" not in flag_args and "-j" not in flag_args:
            args.append("-jsonl")

        # Disable interactive animations and update checks during programmatic execution
        if "-silent" not in flag_args and "-s" not in flag_args:
            args.append("-silent")

        args.extend(flag_args)
        return args

    def _extract_url(self, target: BaseFinding) -> Optional[str]:
        return self.extract_url(target)

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse Nuclei JSONL stream into typed findings."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        fallback_ip = (
            target.pik.get("host_ip") or target.pik.get("ip") or target.data.get("host_ip")
        )

        for line in cleaned.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(item, dict):
                continue

            template_id = str(item.get("template-id", "")).strip()
            info = item.get("info", {})
            if not isinstance(info, dict):
                info = {}

            name = str(info.get("name") or template_id or "Nuclei Finding").strip()
            severity = str(info.get("severity", "info")).lower().strip()
            tags = [str(t).lower() for t in info.get("tags", [])]
            matched_at = str(item.get("matched-at") or item.get("host") or "").strip()
            host_ip = str(item.get("ip") or fallback_ip or "").strip()
            extracted = item.get("extracted-results", [])
            description = str(info.get("description", "")).strip()
            remediation = str(info.get("remediation", "")).strip()

            # 1. Technology / Fingerprinting Finding
            if "tech" in tags or "fingerprint" in tags or template_id.startswith("tech-"):
                version = ""
                if extracted and isinstance(extracted, list):
                    version = str(extracted[0]).strip()
                yield WebTechnology.create(
                    url=matched_at or "http://unknown",
                    technology_name=name,
                    version=version,
                    categories=["server"] if "server" in tags else ["framework"],
                    confidence=1.0,
                    host_ip=host_ip or None,
                )
                continue

            # 2. Security Misconfiguration / Sensitive Exposure
            if any(
                t in tags for t in ("misconfig", "exposure", "leak", "config")
            ) or template_id.endswith("-exposure"):
                yield AuditMisconfig.create(
                    target=matched_at or host_ip or "unknown",
                    check_id=template_id,
                    title=name,
                    severity=severity
                    if severity in ("critical", "high", "medium", "low", "info")
                    else "medium",
                    host_ip=host_ip or None,
                    remediation=remediation or None,
                    description=description or None,
                )
                continue

            # 3. Known Vulnerability / CVE
            if severity in ("critical", "high", "medium", "low") or "cve" in tags:
                vuln_id = (
                    template_id.upper() if template_id.lower().startswith("cve-") else template_id
                )
                yield VulnerabilityFound.create(
                    host_ip=host_ip or "0.0.0.0",
                    vuln_id=vuln_id,
                    title=name,
                    severity=severity
                    if severity in ("critical", "high", "medium", "low", "info")
                    else "info",
                    description=description or None,
                )

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip verbose banner and template loading stats from nuclei output."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("[INF]") and any(
                k in s for k in ("Templates", "projectdiscovery.io", "Configured", "Using")
            ):
                continue
            if any(banner in s for banner in ("__     __", "   __  _")):
                continue
            lines.append(line)
        return "\n".join(lines)
