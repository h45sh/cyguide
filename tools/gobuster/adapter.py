"""Gobuster tool adapter."""

import re
import shlex
from typing import Any, AsyncIterator, Dict, List

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.wordlists import resolve_wordlist, substitute_wordlist_macros
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.web import WebEndpoint


class GobusterAdapter(ToolAdapter):
    """Adapter for the gobuster directory brute-forcing tool."""

    URL_FLAG_RE = re.compile(r"-u\s+([^\s]+)")
    STATUS_PATTERN = re.compile(r"(\S+)\s+\(Status:\s+(\d+)\)")

    def validate_install(self) -> bool:
        return self.is_binary_available("gobuster")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip Gobuster ASCII banners, progress lines, and separator lines."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if (
                s.startswith("==")
                or s.startswith("by OJ Reeves")
                or s.startswith("Gobuster v")
                or "[+] " in s
                or s == "Finished"
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        args = ["gobuster"]

        raw_flags = params.get("raw_flags", "")
        if raw_flags:
            url = self.extract_url(target) or ""
            # Substitute centralized wordlist macros
            raw_flags, _ = substitute_wordlist_macros(raw_flags)
            if "{wordlist}" in raw_flags:
                default_wl = resolve_wordlist("common_dirs")
                raw_flags = raw_flags.replace("{wordlist}", str(default_wl))

            tokens = shlex.split(raw_flags)
            resolved_tokens = []
            for token in tokens:
                if "{url}" in token:
                    token = token.replace("{url}", url)
                resolved_tokens.append(token)

            args.extend(resolved_tokens)

        return args

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Regex parser for gobuster output.

        Example line: /admin (Status: 200) [Size: 1234]
        """
        context = context or {}

        # Base URL to construct full URLs
        base_url = (self.extract_url(target) or "").rstrip("/")

        # Try to extract base url from command params if not available
        if not base_url:
            raw_flags = context.get("params", {}).get("raw_flags", "")
            url_match = self.URL_FLAG_RE.search(raw_flags)
            if url_match:
                base_url = url_match.group(1).rstrip("/")

        for line in raw_stdout.splitlines():
            clean_line = self.strip_ansi(line)

            match = self.STATUS_PATTERN.search(clean_line)
            if match:
                path = match.group(1)
                status_code = int(match.group(2))

                full_url = f"{base_url}{path}" if base_url else path

                yield WebEndpoint.create(url=full_url, method="GET", status_code=status_code)
