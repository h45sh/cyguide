"""Unit tests for Textual compatibility and resilience hardening."""


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
        await pilot.pause()

        # Fire a MouseDown event referencing the detached/unmounted widget
        event = MouseDown(table_content, 10, 5, 0, 0, button=1, shift=False, meta=False, ctrl=False)
        app.screen.get_widget_and_offset_at = lambda x, y: (table_content, Offset(0, 0))

        # This should execute safely without raising AttributeError: 'NoneType' object has no attribute 'region'
        app.screen._forward_event(event)

        # Complete the pending markdown update
        await update_wait
        await pilot.pause()


@pytest.mark.asyncio
async def test_selectable_static_render_and_get_selection():
    """Verify that Static widgets format selections visually and support get_selection extraction."""
    setup_textual_compat()
    from textual.selection import Selection
    from textual.widgets import Static

    class TestStaticApp(App):
        def compose(self) -> ComposeResult:
            yield Static("Hello World\nLine Two of Text", id="test_static")

    app = TestStaticApp()
    async with app.run_test() as pilot:
        w = app.query_one("#test_static", Static)
        sel = Selection(Offset(0, 0), Offset(5, 0))
        extracted, ending = w.get_selection(sel)
        assert extracted == "Hello"
        assert ending == "\n"

        app.screen.selections = {w: sel}
        strip = w.render_line(0)
        has_selection_bg = any("0284c7" in str(seg.style) for seg in strip)
        assert has_selection_bg is True


@pytest.mark.asyncio
async def test_static_unselectable_and_markdown_selection_isolation():
    """Verify that general static widgets are unselectable and markdown selection is continuous."""
    setup_textual_compat()
    from rich.markdown import Markdown
    from textual.selection import Selection
    from textual.widgets import Label, Static

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield Static("Unselectable Title", id="title_header")
            yield Label("Unselectable Label", id="status_label")
            yield Static(
                Markdown("# Header\n\n1. First Item\n2. Second Item\n\nSummary text."),
                id="explanation_text",
            )

    app = TestApp()
    async with app.run_test() as pilot:
        title = app.query_one("#title_header", Static)
        label = app.query_one("#status_label", Label)
        exp = app.query_one("#explanation_text", Static)

        # 1. Verify standard static and label are unselectable
        assert title.allow_select is False
        assert label.allow_select is False
        assert exp.allow_select is True

        # 2. Select lines spanning empty markdown lines (e.g. line 0 to line 3)
        sel = Selection.from_offsets(Offset(0, 0), Offset(10, 3))
        app.screen.selections = {exp: sel}

        # Verify line 0 (Header), line 1 (blank line), line 2 (Item 1), line 3 are styled correctly
        strip_0 = exp.render_line(0)
        assert any("0284c7" in str(seg.style) for seg in strip_0)

        # 3. Verify get_selection extracts text cleanly without trailing padding
        extracted, _ = exp.get_selection(sel)
        assert "Header" in extracted
        assert "First Item" in extracted

        # 4. Verify ListItems and other widgets cannot be selected
        from textual.widgets import ListItem
        assert ListItem().allow_select is False

        # 5. Verify Screen.allow_select is True so mouse selection event dispatch works
        assert app.screen.allow_select is True
