"""Unit tests for Textual compatibility and resilience hardening."""

import pytest
from rich.color import Color
from rich.segment import Segments
from textual.app import App, ComposeResult
from textual.events import MouseDown
from textual.geometry import Offset
from textual.scrollbar import ScrollBar
from textual.widgets import Markdown, RichLog
from textual.widgets._markdown import MarkdownTableContent

from cyguide.ui.compat import ThinScrollBarRender, setup_textual_compat, setup_thin_scrollbars
from cyguide.ui.widgets.power import EntityBrowser


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


def test_mouse_move_can_replace_coalescing():
    """Verify MouseMove coalesces consecutive events with identical button/modifier state."""
    setup_textual_compat()
    from textual.events import MouseMove

    m1 = MouseMove(None, 10, 20, 0, 0, button=0, shift=False, meta=False, ctrl=False)
    m2 = MouseMove(None, 12, 22, 0, 0, button=0, shift=False, meta=False, ctrl=False)
    m_diff_button = MouseMove(None, 15, 25, 0, 0, button=1, shift=False, meta=False, ctrl=False)

    assert m1.can_replace(m2) is True
    assert m1.can_replace(m_diff_button) is False


@pytest.mark.asyncio
async def test_universal_word_deletion_input():
    """Verify Input widget binds ctrl+backspace, alt+backspace, ctrl+w, ctrl+h to delete_left_word."""
    setup_textual_compat()
    from textual.widgets import Input

    class InputTestApp(App):
        def compose(self) -> ComposeResult:
            yield Input(value="hello security world", id="inp")

    app = InputTestApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#inp", Input)
        inp.focus()
        inp.cursor_position = len("hello security world")

        # Press ctrl+backspace to delete 'world'
        await pilot.press("ctrl+backspace")
        assert inp.value == "hello security "

        # Press ctrl+w to delete 'security'
        await pilot.press("ctrl+w")
        assert inp.value == "hello "

        # Press ctrl+h (ASCII 8 backspace) to delete 'hello'
        await pilot.press("ctrl+h")
        assert inp.value == ""


@pytest.mark.asyncio
async def test_universal_word_deletion_textarea():
    """Verify TextArea widget binds ctrl+backspace, ctrl+w, ctrl+h to delete_word_left."""
    setup_textual_compat()
    from textual.widgets import TextArea

    class TextAreaTestApp(App):
        def compose(self) -> ComposeResult:
            yield TextArea("first second third", id="ta")

    app = TextAreaTestApp()
    async with app.run_test() as pilot:
        ta = app.query_one("#ta", TextArea)
        ta.focus()
        ta.cursor_location = (0, len("first second third"))

        # Press ctrl+backspace to delete 'third'
        await pilot.press("ctrl+backspace")
        assert ta.text == "first second "

        # Press ctrl+w to delete 'second'
        await pilot.press("ctrl+w")
        assert ta.text == "first "


@pytest.mark.asyncio
async def test_selection_smoothness_and_boundary_clamping():
    """Verify selection highlight clamps to actual text without trailing padding blowout or re-render churn."""
    setup_textual_compat()
    from rich.markdown import Markdown
    from textual.geometry import Offset
    from textual.selection import Selection
    from textual.widgets import Static

    class SelectionTestApp(App):
        def compose(self) -> ComposeResult:
            yield Static(
                Markdown("- 80/tcp: http (standard protocol)\n- 443/tcp: https (secure)\n"),
                id="exp",
                classes="selectable",
            )

    app = SelectionTestApp()
    async with app.run_test(size=(100, 24)) as pilot:
        exp = app.query_one("#exp", Static)
        assert hasattr(exp, "_render_cache")

        # 1. Multi-line selection: line 1 should NOT highlight 80 columns of trailing padding
        app.screen.selections = {exp: Selection.from_offsets(Offset(0, 1), Offset(5, 2))}
        line_1 = exp.render_line(1)

        # Count styled segments
        styled_text = "".join(
            seg.text
            for seg in line_1._segments
            if "0284c7" in str(seg.style) or "reverse" in str(seg.style)
        )
        assert "80/tcp: http" in styled_text
        assert not styled_text.endswith(" " * 20), (
            "Must not highlight full-width trailing whitespace"
        )

        # 2. Selection update should NOT wipe _render_cache
        cached_lines = exp._render_cache.lines
        exp.selection_updated(Selection.from_offsets(Offset(2, 0), Offset(10, 0)))
        assert exp._render_cache.lines is cached_lines, (
            "Must preserve _render_cache during mouse selection"
        )


@pytest.mark.asyncio
async def test_selectable_static_render_line_monotonic_offsets():
    """Verify that horizontal selection on selectable Static widgets produces monotonically increasing cell offsets without jitter or collapse."""
    setup_textual_compat()
    from rich.markdown import Markdown
    from textual.geometry import Offset
    from textual.selection import Selection
    from textual.widgets import Static

    class MonotonicTestApp(App):
        def compose(self) -> ComposeResult:
            yield Static(
                Markdown("• 445/tcp: microsoft-ds (file and printer sharing, often SMB)\n"),
                id="exp",
                classes="selectable",
            )

    app = MonotonicTestApp()
    async with app.run_test(size=(100, 24)) as pilot:
        exp = app.query_one("#exp", Static)
        start_x = 0

        # Simulate horizontal dragging from column 10 to 60
        for current_x in range(10, 60):
            sel = Selection.from_offsets(Offset(start_x, 0), Offset(current_x, 0))
            app.screen.selections = {exp: sel}

            # Render line with active selection
            rendered_line = exp.render_line(0)

            # Query compositor offset at current_x
            _, detected_offset = app.screen._compositor.get_widget_and_offset_at(
                exp.region.x + current_x, exp.region.y
            )
            assert detected_offset is not None, f"Expected offset at x={current_x}"
            assert detected_offset.x == current_x, (
                f"Offset collapsed or jittered: expected {current_x}, got {detected_offset.x}"
            )


@pytest.mark.asyncio
async def test_input_and_textarea_extended_delete_shortcuts():
    """Verify Input and TextArea handle Shift+Delete, Ctrl+Delete, Alt+Delete, and Ctrl+D gracefully."""
    setup_textual_compat()
    from textual.widgets import Input, TextArea

    class EditorApp(App):
        def compose(self) -> ComposeResult:
            yield Input(id="in_test", value="alpha beta gamma")
            yield TextArea(id="ta_test", text="alpha beta gamma")

    app = EditorApp()
    async with app.run_test() as pilot:
        inp = app.query_one("#in_test", Input)
        ta = app.query_one("#ta_test", TextArea)

        # 1. Input: Ctrl+Delete deletes word right
        inp.focus()
        inp.cursor_position = 0
        await pilot.press("ctrl+delete")
        assert inp.value == "beta gamma"

        # 2. Input: Alt+Delete deletes word right
        await pilot.press("alt+delete")
        assert inp.value == "gamma"

        # 3. Input: Shift+Delete deletes single character right
        inp.cursor_position = 0
        await pilot.press("shift+delete")
        assert inp.value == "amma"

        # 4. Input: Ctrl+D deletes single character right
        inp.cursor_position = 0
        await pilot.press("ctrl+d")
        assert inp.value == "mma"

        # 5. TextArea: Ctrl+Delete deletes word right
        ta.focus()
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+delete")
        assert ta.text == " beta gamma"

        # 6. TextArea: Shift+Delete deletes single character right
        ta.cursor_location = (0, 0)
        await pilot.press("shift+delete")
        assert ta.text == "beta gamma"


@pytest.mark.asyncio
async def test_robust_check_bindings_action_exception_resilience():
    """Verify robust_check_bindings catches and swallows action exceptions gracefully without crashing."""
    setup_textual_compat()
    from textual.binding import Binding

    class ExplodingApp(App):
        BINDINGS = [
            Binding("ctrl+d", "explode", "Explode", show=False),
        ]

        def action_explode(self) -> None:
            raise RuntimeError("Intentional explosion during key shortcut")

    app = ExplodingApp()
    async with app.run_test() as pilot:
        # Pressing ctrl+d triggers action_explode which raises an exception.
        # Under robust_check_bindings, this must not tear down Textual or escape unhandled.
        await pilot.press("ctrl+d")
        assert app.is_running is True


def test_kitty_parser_extended_delete_aliases():
    """Verify extended Kitty escape sequences for delete and control combinations resolve safely."""
    setup_textual_compat()
    from textual._xterm_parser import XTermParser
    from textual.events import _get_key_aliases

    parser = XTermParser(debug=False)
    # \x1b[3;5u is Kitty's Ctrl+Delete
    res_ctrl = parser._parse_extended_key("\x1b[3;5u")
    assert res_ctrl is not None
    key_name = res_ctrl[0].key
    aliases = _get_key_aliases(key_name)
    assert "ctrl+delete" in aliases

    # \x1b[3;2u is Kitty's Shift+Delete
    res_shift = parser._parse_extended_key("\x1b[3;2u")
    assert res_shift is not None
    shift_key_name = res_shift[0].key
    shift_aliases = _get_key_aliases(shift_key_name)
    assert "shift+delete" in shift_aliases


def test_cyguide_textarea_theme_cursor_style():
    """Verify cyguide TextArea theme uses underline cursor instead of solid pipe/block."""
    setup_textual_compat()
    import textual._text_area_theme as tat

    cyguide_theme = tat._BUILTIN_THEMES.get("cyguide")
    assert cyguide_theme is not None
    assert cyguide_theme.cursor_style is not None
    assert cyguide_theme.cursor_style.underline is True
    assert cyguide_theme.cursor_style.bgcolor is None


@pytest.mark.asyncio
async def test_scalar_animation_auto_dimension_resilience():
    """Verify ScalarAnimation resolves 'auto' units without raising ScalarResolveError."""
    setup_textual_compat()
    from textual.css.scalar import Scalar
    from textual.css.scalar_animation import ScalarAnimation
    from textual.widgets import Label

    class DummyApp(App):
        def compose(self) -> ComposeResult:
            yield Label("Test Label", id="test_label")

    app = DummyApp()
    async with app.run_test() as pilot:
        lbl = app.query_one("#test_label")
        # Animate from auto width to 0
        anim = ScalarAnimation(
            lbl,
            lbl.styles,
            0.0,
            "width",
            Scalar.from_number(0.0),
            duration=0.2,
            speed=None,
            easing=lambda x: x,
        )
        assert anim.start is not None
        assert anim.destination == 0.0


@pytest.mark.asyncio
async def test_toastrack_max_visible_toasts_and_deduplication():
    """Verify ToastRack caps visible toasts to 3 and deduplicates identical notifications."""
    setup_textual_compat()
    from textual.widgets._toast import Toast, ToastHolder, ToastRack

    from cyguide.app import CyGuideApp

    app = CyGuideApp()
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        # Fire 6 distinct notifications
        for i in range(6):
            app.notify(f"Message payload {i}", title=f"Event {i}")
        await pilot.pause()

        # Must be capped to max 3 visible toasts
        visible_toasts = list(app.screen.query(Toast))
        assert len(visible_toasts) == 3, f"Expected 3 visible toasts, got {len(visible_toasts)}"
        # Oldest (0, 1, 2) must have been evicted, 3, 4, 5 remain
        titles = [t._notification.title for t in visible_toasts]
        assert "Event 0" not in titles
        assert "Event 5" in titles

        # Fire duplicate of existing notification (Event 5)
        app.notify("Message payload 5", title="Event 5")
        await pilot.pause()
        visible_after_dup = list(app.screen.query(Toast))
        assert len(visible_after_dup) <= 3
        count_event5 = sum(1 for t in visible_after_dup if t._notification.title == "Event 5")
        assert count_event5 == 1, "Duplicate notification must not spawn a second toast"

        # Verify layer: _toastrack is enforced on ToastRack, ToastHolder, and Toast
        rack = app.screen.get_child_by_type(ToastRack)
        assert rack.styles.layer == "_toastrack"
        for holder in rack.children:
            if isinstance(holder, ToastHolder):
                assert holder.styles.layer == "_toastrack"
                for toast in holder.children:
                    if isinstance(toast, Toast):
                        assert toast.styles.layer == "_toastrack"


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
    chars = "".join(s.text for s in res.segments if s.text != "\n")
    assert len(chars) == 30
    assert "▂" in chars
    assert "█" not in chars

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
        for i in range(50):
            log.write(f"Line {i:02d}: " + "x" * 120)
        await pilot.pause(0.2)

        assert log.show_vertical_scrollbar is True
        assert log.show_horizontal_scrollbar is True

        log.scroll_right(animate=False)
        await pilot.pause(0.1)
        assert log.scroll_offset.x > 0

        log.scroll_down(animate=False)
        await pilot.pause(0.1)
        assert log.scroll_offset.y > 0


@pytest.mark.asyncio
async def test_entity_browser_scrollbar_preservation():
    """Verify EntityBrowser preserves scrollbars and renders thin scrollbar on overflow."""

    class BrowserApp(App):
        CSS_PATH = "../../cyguide/ui/style.css"

        def compose(self) -> ComposeResult:
            yield EntityBrowser(id="entity_browser")

    app = BrowserApp()
    async with app.run_test(size=(34, 15)) as pilot:
        eb = app.query_one("#entity_browser", EntityBrowser)
        assert eb.styles.overflow_x == "auto"
        assert eb.styles.overflow_y == "auto"

        for i in range(25):
            eb.root.add_leaf(f"Node {i}: Very long entity title that exceeds sidebar width")
        eb.root.expand_all()
        await pilot.pause(0.2)

        assert eb.show_vertical_scrollbar is True
        assert eb.show_horizontal_scrollbar is True
        assert eb.vertical_scrollbar.thickness == 1
        assert eb.horizontal_scrollbar.thickness == 1


def test_kitty_keyboard_repeat_and_release_resilience():
    """Verify Kitty Keyboard Protocol press, repeat, and release sequences parse without crash."""
    setup_textual_compat()
    from textual._xterm_parser import XTermParser

    parser = XTermParser()

    # Down arrow: press (event_type=1)
    press_events = list(parser.feed("\x1b[1;1:1B"))
    assert len(press_events) == 1
    assert press_events[0].key == "down"

    # Down arrow: repeat (event_type=2) - caused upstream ValueError on int("1:2")
    repeat_events = list(parser.feed("\x1b[1;1:2B"))
    assert len(repeat_events) == 1
    assert repeat_events[0].key == "down"

    # Down arrow: release (event_type=3) - should be cleanly ignored without event
    release_events = list(parser.feed("\x1b[1;1:3B"))
    assert release_events == []

    # Shift+Down repeat
    shift_down = list(parser.feed("\x1b[1;2:2B"))
    assert len(shift_down) == 1
    assert shift_down[0].key == "shift+down"

    # Alt+Down repeat
    alt_down = list(parser.feed("\x1b[1;3:2B"))
    assert len(alt_down) == 1
    assert alt_down[0].key == "alt+down"

    # Ctrl+Down repeat
    ctrl_down = list(parser.feed("\x1b[1;5:2B"))
    assert len(ctrl_down) == 1
    assert ctrl_down[0].key == "ctrl+down"

    # Extended unicode key with event_type (scroll lock)
    ext_key = list(parser.feed("\x1b[57359;1:2u"))
    assert len(ext_key) == 1
    assert ext_key[0].key == "scroll_lock"


def test_xterm_parser_feed_malformed_sequence_resilience():
    """Verify XTermParser.feed safely handles corrupted escape sequences without throwing."""
    setup_textual_compat()
    from textual._xterm_parser import XTermParser

    parser = XTermParser()
    # Feed garbage sequences, unclosed escapes, null bytes, and out-of-range codepoints
    tokens = list(parser.feed("\x1b[;;;;\x1b[999999999999999999999999;foo:bar~"))
    assert isinstance(tokens, list)
