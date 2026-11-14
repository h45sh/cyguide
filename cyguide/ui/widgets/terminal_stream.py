"""High-performance virtualized terminal stream widget.

Decouples subprocess output streaming from Textual layout calculation:
- Zero allocation per chunk: writes are appended to an in-memory staging list in O(1) time.
- 30 FPS micro-batching: flushes accumulated chunks at 30 Hz without blocking the main event loop.
- Memory bounding: maintains a circular ring buffer (collections.deque(maxlen=5000)) to guarantee O(1) memory.
- Viewport virtualization: render_line() renders only the visible rows on screen.
"""

from collections import deque
from typing import List, Optional

from rich.text import Text
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.selection import Selection
from textual.strip import Strip


class TerminalStreamPane(ScrollView, can_focus=True):
    """Virtualized streaming terminal pane with 30 FPS micro-batching and constant memory footprint."""

    DEFAULT_CSS = """
    TerminalStreamPane {
        width: 100%;
        height: 100%;
        background: #0f1114;
        color: #f1f5f9;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 0 1;
    }
    """

    def __init__(self, max_lines: int = 5000, **kwargs):
        super().__init__(**kwargs)
        self.max_lines = max_lines
        self._lines: deque = deque(maxlen=max_lines)
        self._pending_chunks: List[str] = []
        self._line_buffer: str = ""
        self._max_width: int = 80
        self.auto_scroll: bool = True

    def on_mount(self) -> None:
        """Schedule 30 FPS background flush cadence."""
        self.set_interval(0.033, self.flush)

    def write(self, chunk: str) -> None:
        """Enqueue an incoming raw output chunk into staging buffer in O(1) time."""
        if chunk:
            self._pending_chunks.append(chunk)

    def update(self, text: str) -> None:
        """Clear existing buffer and replace with new text immediately."""
        self.clear()
        if text:
            self.write(text)
            self.flush()

    def clear(self) -> None:
        """Clear all buffered terminal output and reset virtual scroll size."""
        self._lines.clear()
        self._pending_chunks.clear()
        self._line_buffer = ""
        self._max_width = 80
        self.virtual_size = Size(0, 0)
        self.refresh()

    def get_text(self) -> str:
        """Return all current lines in buffer as a single concatenated string."""
        all_lines = list(self._lines)
        if self._line_buffer:
            all_lines.append(self._line_buffer)
        return "\n".join(all_lines)

    def selection_updated(self, selection: Optional[Selection]) -> None:
        """Trigger visual refresh when mouse text selection updates."""
        self.refresh()

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Extract selected text from buffer under active Selection coordinates."""
        text = self.get_text()
        return selection.extract(text), "\n"

    def flush(self) -> None:
        """Flush accumulated chunks from staging buffer to line ring buffer."""
        if not self._pending_chunks and not self._line_buffer:
            return

        if self._pending_chunks:
            incoming = "".join(self._pending_chunks)
            self._pending_chunks.clear()

            raw = self._line_buffer + incoming
            lines = raw.split("\n")
            self._line_buffer = lines.pop()

            for line in lines:
                self._lines.append(line)
                if len(line) > self._max_width:
                    self._max_width = len(line)

        total_lines = len(self._lines) + (1 if self._line_buffer else 0)
        self.virtual_size = Size(max(self._max_width, self.size.width), total_lines)

        if self.auto_scroll:
            self.scroll_end(animate=False)

        self.refresh()

    def render_line(self, y: int) -> Strip:
        """Render a single visible line strip on demand (O(viewport) rendering)."""
        scroll_x, scroll_y = self.scroll_offset
        idx = int(scroll_y) + y

        if idx < len(self._lines):
            line_str = self._lines[idx]
        elif idx == len(self._lines) and self._line_buffer:
            line_str = self._line_buffer
        else:
            return Strip.blank(self.size.width, self.rich_style)

        try:
            txt = Text.from_ansi(line_str)
            selection = self.text_selection
            if selection is not None:
                if (select_span := selection.get_span(idx)) is not None:
                    start, end = select_span
                    if end == -1:
                        end = len(txt)
                    try:
                        selection_style = self.screen.get_component_rich_style("screen--selection")
                    except Exception:
                        selection_style = "reverse"
                    txt.stylize(selection_style, start, end)

            strip = Strip(txt.render(self.app.console))
            return strip.crop_extend(scroll_x, scroll_x + self.size.width, self.rich_style)
        except Exception:
            return Strip.blank(self.size.width, self.rich_style)
