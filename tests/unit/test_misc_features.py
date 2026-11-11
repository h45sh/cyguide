"""Unit tests for miscellaneous Power Mode features: LHOST detection, tab copying, flag detection, and notifications."""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyguide.engine.network import get_lhost_info
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.ui.screens.power import PowerModeScreen
from cyguide.ui.widgets.power import CommandPalette


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


def test_flag_regex_detection():
    flag_pattern = re.compile(r'(?:flag|FLAG|ctf|CTF|htb|HTB|thm|THM)\{[A-Za-z0-9_!@#$%^&*+=?.-]+\}')

    sample_output = """
    Target scanned successfully.
    Found secret text: flag{s1mpl3_fl4g_v4lu3}
    Another token: HTB{w3b_3xpl01t_succ3ss!}
    Third token: THM{try_hack_me_2026}
    Noise: some text {not_a_flag} flag{} invalid flag{has space}
    """
    matches = flag_pattern.findall(sample_output)
    assert len(matches) == 3
    assert "flag{s1mpl3_fl4g_v4lu3}" in matches
    assert "HTB{w3b_3xpl01t_succ3ss!}" in matches
    assert "THM{try_hack_me_2026}" in matches


def test_command_palette_ctrl_y():
    palette = CommandPalette()
    mock_input = MagicMock()
    mock_input.value = "> "
    palette.query_one = MagicMock(return_value=mock_input)

    posted_messages = []
    palette.post_message = lambda msg: posted_messages.append(msg)

    event = MagicMock()
    event.key = "ctrl+y"
    palette.on_key(event)

    assert any(isinstance(m, CommandPalette.CopyTabRequest) for m in posted_messages)
    assert event.stop.called
    assert event.prevent_default.called


def test_action_copy_active_tab():
    from unittest.mock import PropertyMock

    screen = PowerModeScreen()
    mock_app = MagicMock()

    mock_tabs = MagicMock()
    mock_tabs.active = "term_1"

    line1 = MagicMock()
    line1.text = "nmap -sV 10.10.10.1"
    line2 = MagicMock()
    line2.text = "Port 80/tcp open http"
    mock_log = MagicMock()
    mock_log.lines = [line1, line2]

    def mock_query_one(selector, *args, **kwargs):
        if selector == "#job_tabs":
            return mock_tabs
        if selector == "#log_term_1":
            return mock_log
        raise ValueError(f"Unknown selector: {selector}")

    screen.query_one = mock_query_one

    with patch.object(PowerModeScreen, "app", new_callable=PropertyMock) as mock_prop:
        mock_prop.return_value = mock_app
        screen.action_copy_active_tab()

    mock_app.copy_to_clipboard.assert_called_once_with("nmap -sV 10.10.10.1\nPort 80/tcp open http")


@pytest.mark.asyncio
async def test_send_desktop_notification():
    screen = PowerModeScreen()
    with patch("shutil.which", return_value="/usr/bin/notify-send"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = MagicMock()
            mock_proc.wait = AsyncMock()
            mock_exec.return_value = mock_proc

            await screen._send_desktop_notification("Job Completed", "Finished scan")
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "notify-send"
            assert "Job Completed" in args


def test_command_palette_prefix_normalization():
    palette = CommandPalette()
    mock_input = MagicMock()
    palette.query_one = MagicMock(return_value=mock_input)

    # 1. Multiple redundant prefixes like "> > whois ..." collapsed
    event = MagicMock()
    event.value = "> > whois 104.20.23.154"
    event.input = mock_input
    palette.on_input_changed(event)
    assert mock_input.value == "> whois 104.20.23.154"

    # 2. In shell locked mode, redundant collapsed to "! "
    palette.shell_locked = True
    event.value = "! ! ls -la"
    palette.on_input_changed(event)
    assert mock_input.value == "! ls -la"


def test_command_palette_submission_strips_duplicate_prefixes():
    palette = CommandPalette()
    palette.shell_locked = True
    mock_input = MagicMock()

    posted = []
    palette.post_message = lambda msg: posted.append(msg)

    # User submitted "> > whois 104.20.23.154"
    event = MagicMock()
    event.value = "> > whois 104.20.23.154"
    event.input = mock_input

    palette.on_input_submitted(event)
    assert len(posted) == 1
    sub = posted[0]
    assert sub.tool_name == "whois"
    assert sub.expanded_params == ["104.20.23.154"]
    assert sub.value == "whois 104.20.23.154"

