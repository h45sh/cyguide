"""Thin and consistent scrollbar renderer for CyGuide TUI.

Provides a unified, sleek, low-profile scrollbar rendering across both vertical
and horizontal scrollbars, matching visual thickness (~4px) on terminal grids.
"""

from __future__ import annotations

from typing import ClassVar

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.scrollbar import ScrollBar, ScrollBarRender


class ThinScrollBarRender(ScrollBarRender):
    """Sleek, thin scrollbar renderer for Textual."""

    HORIZONTAL_THUMB: ClassVar[str] = "▂"  # Lower 1/4 block: ~4.5px high
    VERTICAL_THUMB: ClassVar[str] = "▌"  # Left 1/2 block: ~4.0px wide
    BLANK_GLYPH: ClassVar[str] = " "

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color | None = None,
        bar_color: Color | None = None,
    ) -> Segments:
        """Render a thin, uniform scrollbar."""
        back = back_color if back_color is not None else Color.parse("#14161b")
        bar = bar_color if bar_color is not None else Color.parse("#38bdf8")
        _Segment = Segment
        _Style = Style
        blank = cls.BLANK_GLYPH * thickness

        foreground_meta = {"@mouse.down": "grab"}
        upper = {"@mouse.down": "scroll_up"}
        lower = {"@mouse.down": "scroll_down"}

        if not (
            window_size
            and size
            and virtual_size
            and size != virtual_size
            and window_size < virtual_size
        ):
            style = _Style(bgcolor=back)
            segments = [_Segment(blank, style=style)] * int(size)
            if vertical:
                return Segments(segments, new_lines=True)
            else:
                return Segments((segments + [_Segment.line()]) * thickness, new_lines=False)

        bar_ratio = virtual_size / size
        thumb_size = max(1.0, window_size / bar_ratio)
        position_ratio = position / (virtual_size - window_size)
        pos = (size - thumb_size) * position_ratio

        start_index = max(0, int(pos))
        end_index = min(size, start_index + max(1, int(round(thumb_size))))

        upper_back = _Segment(blank, _Style(bgcolor=back, meta=upper))
        lower_back = _Segment(blank, _Style(bgcolor=back, meta=lower))

        segments = [upper_back] * int(size)
        segments[end_index:] = [lower_back] * (size - end_index)

        thumb_char = cls.VERTICAL_THUMB if vertical else cls.HORIZONTAL_THUMB
        thumb_str = thumb_char * thickness
        thumb_seg = _Segment(thumb_str, _Style(color=bar, bgcolor=back, meta=foreground_meta))
        segments[start_index:end_index] = [thumb_seg] * (end_index - start_index)

        if vertical:
            return Segments(segments, new_lines=True)
        else:
            return Segments((segments + [_Segment.line()]) * thickness, new_lines=False)


def setup_thin_scrollbars() -> None:
    """Register ThinScrollBarRender as Textual's global ScrollBar renderer."""
    ScrollBar.renderer = ThinScrollBarRender


# Auto-apply when imported
setup_thin_scrollbars()
