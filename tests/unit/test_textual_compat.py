"""Unit tests for Textual compatibility and resilience hardening."""

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.events import MouseDown
from textual.geometry import Offset
from textual.widgets import Markdown
from textual.widgets._markdown import MarkdownTableContent

from cyguide.ui.compat import setup_textual_compat


def test_markdown_table_content_allow_select():
    """Verify MarkdownTableContent has ALLOW_SELECT disabled to prevent container selection crash."""
    setup_textual_compat()
    assert getattr(MarkdownTableContent, "ALLOW_SELECT", True) is False


@pytest.mark.asyncio
async def test_safe_forward_event_detached_widget_resilience():
    """Verify Screen._forward_event handles NoneType region without raising AttributeError."""
    setup_textual_compat()

    table_markdown = """
| Tool | Target | Status |
| :--- | :--- | :--- |
| nmap | 127.0.0.1 | Done |
"""

    class CompatApp(App):
        def compose(self) -> ComposeResult:
            yield Markdown(table_markdown, id="test_md")

    app = CompatApp()
    async with app.run_test() as pilot:
        md = app.query_one("#test_md", Markdown)

        # Locate the table content element
        table_content = None
        for child in md.walk_children():
            if isinstance(child, MarkdownTableContent):
                table_content = child
                break

        assert table_content is not None

        # Simulate update causing old widgets to detach/unmount
        update_wait = md.update("# Updated Content Without Tables")
        await asyncio.sleep(0.01)

        # Fire a MouseDown event referencing the detached/unmounted widget
        event = MouseDown(table_content, 10, 5, 0, 0, button=1, shift=False, meta=False, ctrl=False)
        app.screen.get_widget_and_offset_at = lambda x, y: (table_content, Offset(0, 0))

        # This should execute safely without raising AttributeError: 'NoneType' object has no attribute 'region'
        app.screen._forward_event(event)

        # Complete the pending markdown update
        await update_wait
        await pilot.pause()
