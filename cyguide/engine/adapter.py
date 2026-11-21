"""Abstract base class for all tool plugins."""

import functools
import shutil
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.common import strip_ansi as _strip_ansi
from cyguide.schemas.base import BaseFinding


@functools.lru_cache(maxsize=128)
def is_binary_available(binary: str) -> bool:
    """Cached check for binary existence in PATH to avoid repeated filesystem stats."""
    return shutil.which(binary) is not None


def clear_binary_cache() -> None:
    """Clear cached binary lookup table for fresh filesystem validation."""
    is_binary_available.cache_clear()


class ToolAdapter(ABC):
    """Contract for tool contributors.

    Every tool in tools/ must implement this in adapter.py.
    """

    @staticmethod
    def is_binary_available(binary: str) -> bool:
        """Cached check for whether a tool binary exists in PATH."""
        return is_binary_available(binary)

    @abstractmethod
    def validate_install(self) -> bool:
        """Check if the tool binary is available on the system."""
        pass

    @abstractmethod
    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Build the command line arguments for the tool.

        Args:
            target: The finding being scanned (e.g. a network.host)
            params: User-provided flags or options from the TUI
        """
        pass

    @abstractmethod
    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse tool output and yield standardized findings.

        Args:
            raw_stdout: The raw output string from the tool
            target: The original target finding (for context/parenting)
            context: Optional dictionary for tracking state across lines (e.g. current host)
        """
        pass

    @staticmethod
    def strip_ansi(text: str) -> str:
        """Strip ANSI color and cursor control sequences from terminal output."""
        return _strip_ansi(text)

    def extract_url(self, target: Optional[BaseFinding]) -> Optional[str]:
        """Resolve a full HTTP/HTTPS URL from a target finding."""
        if not target:
            return None
        st = getattr(target, "schema_type", "")
        pik = getattr(target, "pik", {}) or {}
        data = getattr(target, "data", {}) or {}

        if st in ("web.endpoint", "web.resource", "web.vulnerability"):
            return pik.get("url") or data.get("url")
        if st == "network.service":
            port = pik.get("port")
            ip = pik.get("host_ip") or data.get("host_ip") or pik.get("ip")
            if ip and port:
                scheme = "https" if int(port) in (443, 8443) else "http"
                return f"{scheme}://{ip}:{port}"
        if st == "network.host":
            ip = pik.get("ip") or pik.get("host_ip") or data.get("ip")
            return f"http://{ip}" if ip else None
        if st in ("domain.info", "dns.record"):
            domain = pik.get("domain") or data.get("domain") or data.get("value")
            return f"http://{domain}" if domain else None
        return None

    def extract_host(self, target: Optional[BaseFinding]) -> Optional[str]:
        """Resolve target IP or hostname from a finding."""
        if not target:
            return None
        st = getattr(target, "schema_type", "")
        pik = getattr(target, "pik", {}) or {}
        data = getattr(target, "data", {}) or {}

        if st == "network.host":
            return pik.get("ip") or pik.get("host_ip") or data.get("ip")
        if st == "network.service":
            return pik.get("host_ip") or data.get("host_ip") or pik.get("ip")
        if st in ("domain.info", "dns.record"):
            return pik.get("domain") or data.get("domain") or data.get("value")
        if st.startswith("web."):
            url = pik.get("url") or data.get("url")
            if url:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                return parsed.hostname or url
        return pik.get("ip") or pik.get("host_ip") or pik.get("domain")

    def extract_domain(self, target: Optional[BaseFinding]) -> Optional[str]:
        """Resolve target domain identifier from a finding."""
        if not target:
            return None
        st = getattr(target, "schema_type", "")
        pik = getattr(target, "pik", {}) or {}
        data = getattr(target, "data", {}) or {}

        if st in ("domain.info", "dns.record"):
            return pik.get("domain") or data.get("domain") or data.get("value")
        if st.startswith("web."):
            url = pik.get("url") or data.get("url")
            if url:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                return parsed.hostname or url
        return pik.get("domain")

    def extract_port(self, target: Optional[BaseFinding]) -> Optional[int]:
        """Resolve target port from a finding."""
        if not target:
            return None
        pik = getattr(target, "pik", {}) or {}
        data = getattr(target, "data", {}) or {}
        port = pik.get("port") or data.get("port")
        if port is not None:
            try:
                return int(port)
            except (ValueError, TypeError):
                pass
        return None

    def sanitize_output(self, raw_stdout: str) -> str:
        """Optional tool-specific output sanitization before LLM prompting.

        Strip tool-specific ASCII banners, progress bars, or noisy separator lines.
        Default implementation returns raw_stdout untouched.
        """
        return raw_stdout
