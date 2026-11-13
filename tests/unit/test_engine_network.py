"""Unit tests for the cyguide.engine.network module and LHOST interface resolution."""

from unittest.mock import MagicMock, patch

import pytest

from cyguide.engine.network import get_lhost_info
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore


def test_get_lhost_info_vpn_priority():
    mock_ip_out = """lo UNKNOWN 127.0.0.1/8 ::1/128
eth0 UP 192.168.1.100/24 fe80::1/64
tun0 UNKNOWN 10.10.14.33/23 fe80::2/64
"""
    with patch("cyguide.engine.network.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_ip_out)
        ip, iface = get_lhost_info(ttl=0.0, force_refresh=True)
        assert ip == "10.10.14.33"
        assert iface == "tun0"


def test_get_lhost_info_regular_up():
    mock_ip_out = """lo UNKNOWN 127.0.0.1/8
eth0 UP 192.168.1.45/24
wlan0 DOWN 192.168.1.99/24
"""
    with patch("cyguide.engine.network.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_ip_out)
        ip, iface = get_lhost_info(ttl=0.0, force_refresh=True)
        assert ip == "192.168.1.45"
        assert iface == "eth0"


def test_get_lhost_info_socket_fallback():
    with patch("cyguide.engine.network.subprocess.run", side_effect=OSError("no ip command")):
        with patch("cyguide.engine.network.socket.socket") as mock_socket_cls:
            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("172.16.0.22", 54321)
            mock_socket_cls.return_value = mock_sock
            ip, iface = get_lhost_info(ttl=0.0, force_refresh=True)
            assert ip == "172.16.0.22"
            assert iface == "default"


def test_get_lhost_info_loopback_fallback():
    with patch("cyguide.engine.network.subprocess.run", side_effect=OSError("fail")):
        with patch("cyguide.engine.network.socket.socket", side_effect=OSError("fail")):
            ip, iface = get_lhost_info(ttl=0.0, force_refresh=True)
            assert ip == "127.0.0.1"
            assert iface == "lo"


@pytest.mark.asyncio
async def test_facade_resolves_lhost():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()
    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "TestSess")

    with patch("cyguide.engine.power_facade.get_lhost_info", return_value=("10.10.14.5", "tun0")):
        ctx = await facade.get_context(sess_id)
        assert "LHOST" in ctx.resolved_vars
        assert ctx.resolved_vars["LHOST"] == "10.10.14.5"

    await store.close()
