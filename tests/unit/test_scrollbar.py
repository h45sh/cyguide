"""Tests for thin, consistent scrollbar renderer and styling."""

import pytest
from rich.color import Color
from rich.segment import Segments
from textual.app import App, ComposeResult
from textual.scrollbar import ScrollBar
from textual.widgets import RichLog

from cyguide.ui.widgets.scrollbar import ThinScrollBarRender, setup_thin_scrollbars


def test_thin_scrollbar_render_horizontal():
    """Verify horizontal scrollbar renders thin lower block character."""
    back = Color.parse("#14161b")
    bar = Color.parse("#38bdf8")

    res = ThinScrollBarRender.render_bar(
        size=30,
        virtual_size=100,
        window_size=25,
        position=10,
        thickness=1,
        vertical=False,
        back_color=back,
        bar_color=bar,
    )

    assert isinstance(res, Segments)
    # Collect text segments
    chars = "".join(s.text for s in res.segments if s.text != "\n")
    assert len(chars) == 30
    assert "▂" in chars
    assert "█" not in chars

    # Verify mouse interaction metadata is present
    thumb_segs = [s for s in res.segments if "▂" in s.text]
    assert len(thumb_segs) > 0
    assert thumb_segs[0].style.meta.get("@mouse.down") == "grab"


def test_thin_scrollbar_render_vertical():
    """Verify vertical scrollbar renders thin left block character."""
    back = Color.parse("#14161b")
    bar = Color.parse("#38bdf8")

    res = ThinScrollBarRender.render_bar(
        size=20,
        virtual_size=80,
        window_size=20,
        position=15,
        thickness=1,
        vertical=True,
        back_color=back,
        bar_color=bar,
    )

    assert isinstance(res, Segments)
    chars = "".join(s.text for s in res.segments if s.text != "\n")
    assert "▌" in chars
    assert "█" not in chars

    thumb_segs = [s for s in res.segments if "▌" in s.text]
    assert len(thumb_segs) > 0
    assert thumb_segs[0].style.meta.get("@mouse.down") == "grab"


def test_thin_scrollbar_render_unscrollable():
    """Verify that when window_size >= virtual_size, no thumb is rendered."""
    res = ThinScrollBarRender.render_bar(
        size=20,
        virtual_size=10,
        window_size=20,
        position=0,
        thickness=1,
        vertical=False,
    )
    chars = "".join(s.text for s in res.segments if s.text != "\n")
    assert "▂" not in chars
    assert " " in chars


def test_scrollbar_renderer_registered():
    """Verify ThinScrollBarRender is registered as global ScrollBar renderer."""
    setup_thin_scrollbars()
    assert ScrollBar.renderer is ThinScrollBarRender


def test_css_scrollbar_rules():
    """Verify style.css includes unified thin scrollbar rules."""
    import os
    css_path = os.path.join(os.path.dirname(__file__), "../../cyguide/ui/style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "scrollbar-size: 1 1;" in content
    assert "scrollbar-size-vertical: 1;" in content
    assert "scrollbar-size-horizontal: 1;" in content
    assert "scrollbar-background: transparent;" in content
    assert "scrollbar-color: #334155;" in content
    assert "scrollbar-color-active: #38bdf8;" in content


@pytest.mark.asyncio
async def test_richlog_thin_scrollbar_scrolling():
    """Verify RichLog renders thin scrollbars and scrolls without error."""
    class ScrollApp(App):
        CSS_PATH = "../../cyguide/ui/style.css"

        def compose(self) -> ComposeResult:
            yield RichLog(id="test_log")

    app = ScrollApp()
    async with app.run_test(size=(80, 24)) as pilot:
        log = app.query_one("#test_log", RichLog)
        # Write wide and tall text to trigger both scrollbars
        for i in range(50):
            log.write(f"Line {i:02d}: " + "x" * 120)
        await pilot.pause(0.2)

        assert log.show_vertical_scrollbar is True
        assert log.show_horizontal_scrollbar is True

        # Test horizontal scrolling
        log.scroll_right(animate=False)
        await pilot.pause(0.1)
        assert log.scroll_offset.x > 0

        # Test vertical scrolling
        log.scroll_down(animate=False)
        await pilot.pause(0.1)
        assert log.scroll_offset.y > 0


@pytest.mark.asyncio
async def test_entity_browser_scrollbar_preservation():
    """Verify EntityBrowser preserves scrollbars and renders thin scrollbar on overflow."""
    from cyguide.ui.widgets.power import EntityBrowser

    class BrowserApp(App):
        CSS_PATH = "../../cyguide/ui/style.css"

        def compose(self) -> ComposeResult:
            yield EntityBrowser(id="entity_browser")

    app = BrowserApp()
    async with app.run_test(size=(34, 15)) as pilot:
        eb = app.query_one("#entity_browser", EntityBrowser)
        assert eb.styles.overflow_x == "auto"
        assert eb.styles.overflow_y == "auto"

        # Add long and multiple nodes to trigger both scrollbars
        for i in range(25):
            eb.root.add_leaf(f"Node {i}: Very long entity title that exceeds sidebar width")
        eb.root.expand_all()
        await pilot.pause(0.2)

        assert eb.show_vertical_scrollbar is True
        assert eb.show_horizontal_scrollbar is True
        assert eb.vertical_scrollbar.thickness == 1
        assert eb.horizontal_scrollbar.thickness == 1

