import pytest
from cyguide.app import CyGuideApp

def test_app_structure():
    """Verify the app has the expected screens and title."""
    app = CyGuideApp()
    assert app.TITLE == "CyGuide"
    assert "dashboard" in app.SCREENS
    assert "learning_mode" in app.SCREENS
    assert "power_mode" in app.SCREENS
    assert "tool_browser" in app.SCREENS

@pytest.mark.asyncio
async def test_app_component_init(tmp_path):
    """Smoke test for app component setup without running the full TUI."""
    app = CyGuideApp()
    # We can't easily call on_mount because it's managed by Textual's loop,
    # but we can verify the class structure.
    assert hasattr(app, "SCREENS")

def test_format_activity():
    """Verify that format_activity formats different schemas and event types correctly."""
    from cyguide.ui.screens.home import format_activity
    import json

    # 1. System event (Ran nmap)
    line = format_activity("Session 22:40:20", "system.event", "Ran nmap")
    assert line == "[22:40:20] Run: nmap"

    # 2. network.host
    host_json = json.dumps({"pik": {"ip": "192.168.1.1"}, "data": {}})
    line = format_activity("Session 22:40:20", "network.host", "Discovered network.host", finding_json=host_json)
    assert line == "[22:40:20] Host: 192.168.1.1"

    # 3. network.service
    service_json = json.dumps({"pik": {"port": 80}, "data": {"service_name": "http"}})
    line = format_activity("Session 22:40:20", "network.service", "Discovered network.service", finding_json=service_json)
    assert line == "[22:40:20] Port: 80 (http)"

    # 4. dns.record
    dns_json = json.dumps({"pik": {"domain": "api.example.com"}})
    line = format_activity("Session 22:40:20", "dns.record", "Discovered dns.record", finding_json=dns_json)
    assert line == "[22:40:20] Domain: api.example.com"

    # 5. web.endpoint
    web_json = json.dumps({"pik": {"url": "https://example.com/admin"}})
    line = format_activity("Session 22:40:20", "web.endpoint", "Discovered web.endpoint", finding_json=web_json)
    assert line == "[22:40:20] URL: example.com/admin"

    # 6. network.netblock
    net_json = json.dumps({"pik": {"cidr": "10.0.0.0/24"}})
    line = format_activity("MyLongSessionName", "network.netblock", "Discovered network.netblock", finding_json=net_json)
    assert line == "[MyLongSe..] Netblock: 10.0.0.0/24"

@pytest.mark.asyncio
async def test_learning_screen_resume_preserves_buffer():
    """Verify that returning from expanded output view does not erase learning mode output."""
    from cyguide.ui.screens.learning import LearningModeScreen
    from textual._context import active_app
    from unittest.mock import MagicMock

    mock_app = MagicMock()
    mock_app.learning_mode_tool = "nmap"
    token = active_app.set(mock_app)

    try:
        screen = LearningModeScreen()
        screen.active_tool = "nmap"
        screen.log_buffer = ["Line 1\n", "Line 2\n"]
        screen.explanation_buffer = "Explanation content"

        # When screen resumes with same tool, update_tool_context(force=False) must not wipe buffers
        await screen.update_tool_context(force=False)
        assert screen.log_buffer == ["Line 1\n", "Line 2\n"]
        assert screen.explanation_buffer == "Explanation content"
    finally:
        active_app.reset(token)

