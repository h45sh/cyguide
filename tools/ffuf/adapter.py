"""FFUF tool adapter."""

import json
import re
import shlex
import shutil
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.wordlists import resolve_wordlist, substitute_wordlist_macros
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.vulnerability import AuditMisconfig
from cyguide.schemas.web import WebEndpoint


class FfufAdapter(ToolAdapter):
    """Adapter for the ffuf fast web fuzzer."""

    SENSITIVE_PATTERN = re.compile(
        r"(?:\.(?:env|git|bak|old|config|conf|json|yml|yaml|sql|db|sqlite|tar|gz|zip)|\b(?:admin|backup|secrets?|credentials?))\b",
        re.IGNORECASE,
    )

    def validate_install(self) -> bool:
        """Check if ffuf binary is available in PATH."""
        return shutil.which("ffuf") is not None

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct the ffuf command line execution."""
        # 1. Resolve target URL
        url = self._extract_url(target)

        # 2. Process flags and substitute macros
        raw_flags = params.get("raw_flags", "").strip()
        raw_flags, _ = substitute_wordlist_macros(raw_flags)
        flag_args = shlex.split(raw_flags) if raw_flags else []

        args = ["ffuf"]

        # Ensure -u flag is present
        has_u = any(flag_args[i] == "-u" for i in range(len(flag_args)))
        if not has_u:
            if not url:
                raise ValueError(
                    f"Target finding {target.schema_type} has no URL or host identifier, and no -u flag provided."
                )
            base_url = url.rstrip("/")
            # If FUZZ keyword is not in URL, append /FUZZ
            fuzz_url = base_url if "FUZZ" in base_url else f"{base_url}/FUZZ"
            args.extend(["-u", fuzz_url])

        # Ensure -w wordlist flag is present
        has_w = any(flag_args[i] == "-w" for i in range(len(flag_args)))
        if not has_w:
            default_wl = resolve_wordlist("common_dirs")
            args.extend(["-w", str(default_wl)])

        # Ensure JSON output is captured
        has_of = any(flag_args[i] == "-of" for i in range(len(flag_args)))
        if not has_of:
            args.extend(["-of", "json", "-o", "-"])

        # Add user-provided flags (ignoring duplicates of handled flags)
        args.extend(flag_args)
        return args

    def _extract_url(self, target: BaseFinding) -> Optional[str]:
        if target.schema_type == "web.endpoint":
            return target.pik.get("url") or target.data.get("url")
        if target.schema_type == "network.host":
            ip = target.pik.get("ip")
            return f"http://{ip}" if ip else None
        if target.schema_type == "dns.record":
            domain = (
                target.pik.get("domain") or target.data.get("domain") or target.data.get("value")
            )
            return f"http://{domain}" if domain else None
        return None

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse structured JSON results or stdout lines from ffuf."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        host_ip = target.pik.get("host_ip") or target.pik.get("ip") or target.data.get("host_ip")

        # 1. Try parsing JSON payload
        json_obj = self._parse_json(cleaned)
        if json_obj and "results" in json_obj:
            results = json_obj.get("results", [])
            for item in results:
                if not isinstance(item, dict):
                    continue

                endpoint_url = item.get("url", "").strip()
                if not endpoint_url:
                    continue

                status_code = int(item.get("status", 200))
                length = int(item.get("length", 0))
                words = int(item.get("words", 0))
                lines = int(item.get("lines", 0))
                fuzz_word = str(item.get("input", {}).get("FUZZ", ""))

                # Yield endpoint finding
                yield WebEndpoint.create(
                    url=endpoint_url,
                    host_ip=host_ip,
                    status_code=status_code,
                    content_length=length,
                    words=words,
                    lines=lines,
                )

                # Check for sensitive misconfiguration exposure
                if status_code in (200, 301, 302, 307) and self.SENSITIVE_PATTERN.search(fuzz_word):
                    yield AuditMisconfig.create(
                        target=endpoint_url,
                        check_id="exposed-sensitive-file",
                        title=f"Exposed Sensitive Resource ({fuzz_word})",
                        severity="high" if status_code == 200 else "medium",
                        host_ip=host_ip,
                        remediation="Restrict access to sensitive configuration, backup, or administrative paths.",
                    )
            return

        # 2. Fallback: Parse line-by-line CLI output
        # e.g.: "admin                   [Status: 200, Size: 1256, Words: 84, Lines: 15, Duration: 4ms]"
        line_pattern = re.compile(
            r"^(\S+)\s+\[Status:\s*(\d+),\s*Size:\s*(\d+),\s*Words:\s*(\d+),\s*Lines:\s*(\d+)",
            re.MULTILINE,
        )
        base_url = self._extract_url(target) or ""
        for match in line_pattern.finditer(cleaned):
            word, status_str, size_str, words_str, lines_str = match.groups()
            endpoint_url = f"{base_url.rstrip('/')}/{word.lstrip('/')}"
            status_code = int(status_str)

            yield WebEndpoint.create(
                url=endpoint_url,
                host_ip=host_ip,
                status_code=status_code,
                content_length=int(size_str),
                words=int(words_str),
                lines=int(lines_str),
            )

            if status_code in (200, 301, 302, 307) and self.SENSITIVE_PATTERN.search(word):
                yield AuditMisconfig.create(
                    target=endpoint_url,
                    check_id="exposed-sensitive-file",
                    title=f"Exposed Sensitive Resource ({word})",
                    severity="high" if status_code == 200 else "medium",
                    host_ip=host_ip,
                )

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None
