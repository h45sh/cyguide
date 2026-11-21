"""Network interface and local host (LHOST) discovery utilities for CyGuide."""

import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ["get_lhost_info", "clear_lhost_cache"]


@dataclass
class _LhostCacheEntry:
    timestamp: float
    ip: str
    interface: str

    @property
    def value(self) -> Tuple[str, str]:
        return (self.ip, self.interface)

    def is_valid(self, ttl: float, now: float) -> bool:
        return (now - self.timestamp) < ttl


_lhost_cache: Optional[_LhostCacheEntry] = None


def clear_lhost_cache() -> None:
    """Explicitly invalidate the cached LHOST discovery result."""
    global _lhost_cache
    _lhost_cache = None


def get_lhost_info(ttl: float = 10.0, force_refresh: bool = False) -> Tuple[str, str]:
    """Discover the local host IP and interface name, prioritizing VPN/tunnel interfaces.

    Returns:
        Tuple of (ip_address, interface_name), e.g. ("10.10.14.5", "tun0") or ("192.168.1.50", "eth0").
    """
    global _lhost_cache
    now = time.time()
    if not force_refresh and _lhost_cache is not None and _lhost_cache.is_valid(ttl, now):
        return _lhost_cache.value

    # 1. Try 'ip -brief -4 addr show' (Linux standard)
    try:
        res = subprocess.run(
            ["ip", "-brief", "-4", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res.returncode == 0:
            vpn_candidates = []
            regular_candidates = []
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    iface = parts[0]
                    status = parts[1].upper()
                    cidr = parts[2]
                    ip = cidr.split("/")[0]
                    if iface == "lo":
                        continue
                    if iface.startswith(("tun", "wg", "tap", "ppp", "utun")):
                        vpn_candidates.append((ip, iface))
                    elif status == "UP":
                        regular_candidates.append((ip, iface))

            if vpn_candidates:
                ip, iface = vpn_candidates[0]
                _lhost_cache = _LhostCacheEntry(now, ip, iface)
                return (ip, iface)
            if regular_candidates:
                ip, iface = regular_candidates[0]
                _lhost_cache = _LhostCacheEntry(now, ip, iface)
                return (ip, iface)
    except Exception:
        pass

    # 2. Socket routing query fallback (determines default route egress IP)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        _lhost_cache = _LhostCacheEntry(now, ip, "default")
        return (ip, "default")
    except Exception:
        pass

    # 3. Ultimate loopback fallback
    fallback = ("127.0.0.1", "lo")
    _lhost_cache = _LhostCacheEntry(now, fallback[0], fallback[1])
    return fallback
