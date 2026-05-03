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
