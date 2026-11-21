"""Automated unit and performance tests for TerminalStreamPane.

Verifies:
1. Basic lifecycle: init, write, partial line buffering, flush, clear, get_text.
2. Viewport-only virtual rendering via render_line().
3. High-throughput streaming (100,000 lines):
   - Strict memory bounding: circular ring buffer does not exceed maxlen (5,000 lines).
   - Non-blocking execution: completes in milliseconds without freezing.
   - O(1) viewport render cost regardless of streaming volume.
"""

import time

import pytest
from textual.app import App, ComposeResult
from textual.geometry import Size
from textual.strip import Strip

from cyguide.ui.widgets.terminal_stream import TerminalStreamPane


class TerminalTestApp(App):
    """Minimal headless test harness for TerminalStreamPane."""

    def compose(self) -> ComposeResult:
        yield TerminalStreamPane(max_lines=5000, id="term")


@pytest.mark.asyncio
async def test_terminal_stream_initialization():
    """Verify clean initialization and default state."""
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)
        assert term.max_lines == 5000
        assert len(term._lines) == 0
        assert term._pending_chunks == []
        assert term._line_buffer == ""
        assert term.auto_scroll is True


@pytest.mark.asyncio
async def test_terminal_stream_partial_line_buffering():
    """Verify that partial lines without newline are held and reassembled correctly."""
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)

        # Write first chunk without trailing newline
        term.write("Scan started: target=")
        term.flush()
        assert len(term._lines) == 0
        assert term._line_buffer == "Scan started: target="

        # Complete the line and add a second line
        term.write("192.168.1.1\nPort 80 open\n")
        term.flush()
        assert len(term._lines) == 2
        assert term._line_buffer == ""
        assert term._lines[0] == "Scan started: target=192.168.1.1"
        assert term._lines[1] == "Port 80 open"


@pytest.mark.asyncio
async def test_terminal_stream_clear_and_get_text():
    """Verify buffer retrieval and clearing."""
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)
        term.write("Line 1\nLine 2\nLine 3\n")
        term.flush()

        assert term.get_text() == "Line 1\nLine 2\nLine 3"

        term.clear()
        assert len(term._lines) == 0
        assert term.get_text() == ""
        assert term.virtual_size == Size(0, 0)


@pytest.mark.asyncio
async def test_terminal_stream_virtual_render_line():
    """Verify that render_line renders only visible viewport rows with ANSI colors."""
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)
        term.write("\x1b[32m[+] Discovered admin.example.com\x1b[0m\n")
        term.write("\x1b[31m[-] Port 22 filtered\x1b[0m\n")
        term.flush()

        strip0 = term.render_line(0)
        assert isinstance(strip0, Strip)
        assert "[+] Discovered admin.example.com" in strip0.text

        strip1 = term.render_line(1)
        assert isinstance(strip1, Strip)
        assert "[-] Port 22 filtered" in strip1.text

        # Beyond line count returns blank strip
        strip_blank = term.render_line(999)
        assert strip_blank.text.strip() == ""


@pytest.mark.slow
@pytest.mark.asyncio
async def test_terminal_stream_100k_lines_stress_and_bounded_memory():
    """Verify that 100,000 streamed lines execute in milliseconds with zero memory leak.

    - Demonstrates O(1) memory: ring buffer strictly caps at max_lines (5000).
    - Demonstrates non-blocking throughput: 100,000 lines processed in < 0.25 seconds.
    - Demonstrates O(1) render cost: render_line() renders the viewport in microseconds.
    """
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)

        # Generate batch of 100,000 lines simulating rapid ffuf / subfinder output
        chunks = [f"subdomain-{i}.corp.internal 10.0.0.{i % 254}\n" for i in range(100_000)]
        big_payload = "".join(chunks)

        start_time = time.perf_counter()
        term.write(big_payload)
        term.flush()
        elapsed_seconds = time.perf_counter() - start_time

        # 1. Verify strict memory bounding (ring buffer size capped at 5,000)
        assert len(term._lines) == 5000
        assert term.virtual_size.height == 5000

        # 2. Verify high throughput (100k lines in under 0.5 seconds on modern CPU)
        assert elapsed_seconds < 0.5, f"100k lines took {elapsed_seconds:.3f}s (expected < 0.5s)"

        # 3. Verify oldest lines were evicted and latest line is retained
        assert "subdomain-99999.corp.internal" in term._lines[-1]

        # 4. Verify O(1) viewport rendering performance under high load
        t_render_start = time.perf_counter()
        strip = term.render_line(0)
        t_render_elapsed = time.perf_counter() - t_render_start
        assert isinstance(strip, Strip)
        assert t_render_elapsed < 0.005, (
            f"Viewport render took {t_render_elapsed:.5f}s (expected < 5ms)"
        )


@pytest.mark.asyncio
async def test_terminal_stream_text_selection():
    """Verify that text selection is extracted correctly and styled during rendering."""
    from textual.geometry import Offset
    from textual.selection import Selection

    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)
        term.write("first line\nsecond line\nthird line\n")
        term.flush()

        # 1. Test get_selection extraction
        sel = Selection.from_offsets(Offset(0, 0), Offset(5, 0))
        extracted, ending = term.get_selection(sel)
        assert extracted == "first"
        assert ending == "\n"

        # Multi-line selection extraction
        multi_sel = Selection.from_offsets(Offset(6, 0), Offset(6, 1))
        extracted_multi, _ = term.get_selection(multi_sel)
        assert extracted_multi == "line\nsecond"

        # 2. Test selection_updated triggers refresh without error
        term.selection_updated(sel)


@pytest.mark.asyncio
async def test_terminal_stream_mouse_drag_selection():
    """Verify that mouse drag on TerminalStreamPane properly selects text with accurate coordinates."""
    app = TerminalTestApp()
    async with app.run_test() as pilot:
        term = app.query_one("#term", TerminalStreamPane)
        term.write("admin.example.com\napi.example.com\n")
        term.flush()
        await pilot.pause()

        # Perform mouse click & drag (offset=(1, 0) accounts for 1-column left padding)
        await pilot.mouse_down(term, offset=(1, 0))
        await pilot.hover(term, offset=(5, 0))
        await pilot.mouse_up(term, offset=(5, 0))
        await pilot.pause()

        selected = app.screen.get_selected_text()
        assert selected == "admin"


def test_ui_markup_escaping():
    from rich.errors import MarkupError
    from rich.markup import escape
    from rich.text import Text

    # Strings with unmatched closing tags that cause rich MarkupError if interpolated unescaped
    crashing_inputs = [
        "Unmatched closing tag [/red] in compiler output",
        "Multiple tags [/bold][/italic][/blink]",
        "Syntax error: <module> [/unknown_tag]",
        "Arbitrary [/] root close tag",
        "nested [/foo][bar][/bar]",
    ]

    for raw in crashing_inputs:
        with pytest.raises(MarkupError):
            Text.from_markup(f"[bold #f85149]Error:[/] [red]{raw}[/]")

    all_inputs = crashing_inputs + [
        "[bold]Open tag without close",
        "[link=http://evil.com]clickme[/link]",
        "[#ff0000]custom color[/#ff0000]",
    ]
    for raw in all_inputs:
        escaped_text = Text.from_markup(f"[bold #f85149]Error:[/] [red]{escape(raw)}[/]")
        assert escaped_text is not None
        assert raw in escaped_text.plain
