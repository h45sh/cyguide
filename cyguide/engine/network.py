"""Network interface and local host (LHOST) discovery utilities for CyGuide."""

import socket
import subprocess
import time
from typing import Optional, Tuple

_cached_lhost: Optional[Tuple[float, Tuple[str, str]]] = None


def get_lhost_info(ttl: float = 10.0, force_refresh: bool = False) -> Tuple[str, str]:
    """Discover the local host IP and interface name, prioritizing VPN/tunnel interfaces.

    Returns:
        Tuple of (ip_address, interface_name), e.g. ("10.10.14.5", "tun0") or ("192.168.1.50", "eth0").
    """
    global _cached_lhost
    now = time.time()
    if not force_refresh and _cached_lhost is not None and (now - _cached_lhost[0] < ttl):
        return _cached_lhost[1]

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
                _cached_lhost = (now, vpn_candidates[0])
                return vpn_candidates[0]
            if regular_candidates:
                _cached_lhost = (now, regular_candidates[0])
                return regular_candidates[0]
    except Exception:
        pass

    # 2. Socket routing query fallback (determines default route egress IP)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        _cached_lhost = (now, (ip, "default"))
        return _cached_lhost[1]
    except Exception:
        pass

    # 3. Ultimate loopback fallback
    fallback = ("127.0.0.1", "lo")
    _cached_lhost = (now, fallback)
    return fallback
