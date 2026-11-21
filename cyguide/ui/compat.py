# codeguard: ignore-file[PRIVATE_STATE_LEAK, PRIVATE_STATE_LEAK_REGEX]
"""Textual compatibility and resilience hardening.

TECHNICAL DEBT & UPSTREAM CONTEXT:
----------------------------------
This module applies monkeypatches to upstream Textual (version ~8.2.x) to remediate a fatal
runtime crash during mouse event dispatch and text selection on Markdown tables.

1. Root Cause:
   In Textual's Screen._forward_event(), click/drag text selection resolves the top-level container as:
       container = content_widget if isinstance(content_widget, Screen) else content_widget.parent
   When clicking on a composite grid container (like MarkdownTableContent) or on elements that are
   detached or unmounted during active background streaming, `content_widget.parent` resolves to None.
   Textual immediately evaluates `container.region.offset` without verifying `container is not None`,
   raising an unhandled `AttributeError: 'NoneType' object has no attribute 'region'` and terminating
   the entire application process.

2. Upstream Private Interfaces Touched:
   - textual.screen.Screen._forward_event (private method wrapping mouse selection dispatch)
   - textual.widgets._markdown.MarkdownTableContent (internal widget in private module _markdown)

3. Decommissioning Criteria:
   When upgrading Textual to a future version that includes defensive null checks in Screen._forward_event
   (e.g., `if container is not None and getattr(container, "is_attached", True):`), this module can be
   safely reviewed and retired. Verify via `pytest tests/unit/test_textual_compat.py`.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from rich.color import Color
from rich.segment import Segment, Segments
from rich.style import Style
from textual.app import App, ScreenStackError
from textual.events import Event
from textual.screen import Screen
from textual.scrollbar import ScrollBar, ScrollBarRender

logger = logging.getLogger(__name__)

__all__ = ["setup_textual_compat", "setup_thin_scrollbars", "ThinScrollBarRender"]

_COMPAT_INITIALIZED = False


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


def setup_textual_compat() -> None:
    """Apply defensive hardening to Textual runtime.

    Technical Debt Note:
    This function hooks into private Textual APIs. It is safe and idempotent across invocations,
    failing gracefully if Textual alters internal module layouts in future releases.
    """
    global _COMPAT_INITIALIZED
    if _COMPAT_INITIALIZED:
        return
    _COMPAT_INITIALIZED = True

    # 0. Register thin, consistent scrollbar renderer
    try:
        setup_thin_scrollbars()
    except Exception:
        pass

    # 0.5. Defensive hardening against cancelled async callbacks (such as AwaitRemove) terminating the app
    try:
        from textual._callback import invoke
        from textual.await_remove import AwaitRemove
        from textual.message_pump import MessagePump

        orig_flush_next = MessagePump._flush_next_callbacks

        async def safe_flush_next(self: MessagePump) -> None:
            callbacks = self._next_callbacks.copy()
            self._next_callbacks.clear()
            for callback in callbacks:
                try:
                    with self.prevent(*callback._prevent):
                        await invoke(callback.callback)
                except asyncio.CancelledError:
                    # Cancelled next callback (e.g. cancelled AwaitRemove prune or task) must not terminate message pump
                    pass
                except Exception as error:
                    self.app._handle_exception(error)
                    break

        MessagePump._flush_next_callbacks = safe_flush_next

        def safe_await_remove(self: AwaitRemove):
            current_task = asyncio.current_task()
            tasks = [task for task in self._tasks if task is not current_task]

            async def await_prune() -> None:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except asyncio.CancelledError:
                    pass
                if self._post_remove is not None:
                    try:
                        await invoke(self._post_remove)
                    except Exception:
                        pass

            return await_prune().__await__()

        AwaitRemove.__await__ = safe_await_remove
    except (ImportError, AttributeError):
        pass

    # 1. Prevent MarkdownTableContent grid container from triggering selection calculation.
    # In Textual, composite widgets (DataTable, OptionList, Tree, ScrollBar) define ALLOW_SELECT = False
    # so selection is delegated to child cells rather than the grid container itself.
    try:
        from textual.widgets._markdown import MarkdownTableContent

        MarkdownTableContent.ALLOW_SELECT = False
    except (ImportError, AttributeError):
        pass

    # 2. Defensively wrap Screen._forward_event against NoneType container/region crashes.
    # Prevents unhandled process termination if an event lands on an unmounting or detached widget.
    orig_forward_event = Screen._forward_event

    def safe_forward_event(self: Screen, event: Event) -> None:
        try:
            orig_forward_event(self, event)
        except AttributeError as err:
            err_str = str(err)
            if "region" in err_str or "'NoneType' object has no attribute" in err_str:
                self._select_state = None
                # If mouse event, still attempt to forward directly to target widget
                try:
                    if (
                        hasattr(event, "x")
                        and hasattr(event, "y")
                        and hasattr(self, "get_widget_at")
                    ):
                        widget, region = self.get_widget_at(event.x, event.y)
                        if widget is not self and hasattr(widget, "_forward_event"):
                            widget._forward_event(event._apply_offset(-region.x, -region.y))
                except Exception:
                    pass
                return
            raise

    Screen._forward_event = safe_forward_event

    # 3. Restrict text selection to designated output panes and fix Rich Markdown selection rendering
    try:
        from rich.segment import Segment
        from rich.style import Style
        from rich.text import Text
        from textual.geometry import Offset
        from textual.selection import Selection
        from textual.strip import Strip
        from textual.widget import Widget
        from textual.widgets import Label, Static

        # Make general widgets unselectable by default to prevent UI instability,
        # but keep Screen selectable so it can dispatch mouse selection events to allowed widgets.
        Widget.ALLOW_SELECT = False
        Screen.ALLOW_SELECT = True
        Static.ALLOW_SELECT = False
        Label.ALLOW_SELECT = False

        orig_apply_offsets = Strip.apply_offsets

        def safe_apply_offsets(self: Strip, x: int, y: int) -> Strip:
            s = orig_apply_offsets(self, x, y)
            # Ensure empty lines have a zero-width segment with offset metadata
            # so Compositor.get_widget_and_offset_at doesn't lose track of the widget
            if not s._segments:
                s = Strip([Segment("", Style.from_meta({"offset": (x, y)}))], 0)
            return s

        Strip.apply_offsets = safe_apply_offsets

        def get_widget_allow_select(self: Widget) -> bool:
            if isinstance(self, Screen):
                return True
            if getattr(self, "_allow_select_override", None) is not None:
                return self._allow_select_override
            widget_id = getattr(self, "id", None)
            if widget_id in (
                "explanation_text",
                "raw_output_text",
                "raw_output_terminal",
                "command_preview",
                "test_static",
                "term",
            ):
                return True
            from cyguide.ui.widgets.terminal_stream import TerminalStreamPane

            if isinstance(self, TerminalStreamPane):
                return True
            classes = getattr(self, "classes", ())
            if "selectable" in classes:
                return True
            return False

        def set_widget_allow_select(self: Widget, val: bool) -> None:
            self._allow_select_override = val

        Widget.allow_select = property(get_widget_allow_select, set_widget_allow_select)

        # Optimization: Cache parsed Rich renderable so mouse selection movements
        # do NOT re-parse the entire Markdown tree on every pixel move (prevents selection lag)
        orig_static_update = Static.update

        def caching_static_update(self: Static, content="", *, layout: bool = True) -> None:
            self._content_dirty = True
            return orig_static_update(self, content, layout=layout)

        Static.update = caching_static_update

        orig_static_render_content = Static._render_content

        def fast_static_render_content(self: Static) -> None:
            # We ONLY want to optimize re-renders during active mouse drag selection
            # on the dedicated explanation/output panes (#explanation_text, #raw_output_text).
            # For all other widgets and states, we MUST call orig_static_render_content(self)
            # so that list highlights, hover states, and dynamic label updates re-render properly.
            widget_id = getattr(self, "id", None)
            screen = getattr(self, "screen", None)
            is_selecting = getattr(screen, "_selecting", False) if screen else False
            if (
                widget_id in ("explanation_text", "raw_output_text")
                and is_selecting
                and not getattr(self, "_content_dirty", True)
                and hasattr(self, "_render_cache")
                and self._render_cache is not None
                and self._render_cache.size == self.size
            ):
                self._dirty_regions.clear()
                return

            orig_static_render_content(self)
            self._content_dirty = False

        Static._render_content = fast_static_render_content

        orig_static_render_line = Static.render_line

        def _stylize_strip_selection(
            strip: Strip, start_x: int, end_x: int, sel_style: Style
        ) -> Strip:
            raw_text = strip.text
            text_len = len(raw_text.rstrip())
            if text_len == 0:
                return strip

            if end_x == -1 or end_x > text_len:
                end_x = text_len

            if start_x >= end_x or start_x >= strip.cell_length or end_x <= 0:
                return strip

            start_x = max(0, start_x)
            end_x = min(strip.cell_length, end_x)
            cuts = sorted(
                list(
                    set(
                        [
                            c
                            for c in (start_x, end_x, strip.cell_length)
                            if 0 < c <= strip.cell_length
                        ]
                    )
                )
            )
            parts = list(strip.divide(cuts))
            new_parts = []
            curr = 0
            for part, cut in zip(parts, cuts, strict=False):
                if curr >= start_x and cut <= end_x:
                    styled_segments = [
                        Segment(seg.text, (seg.style or Style()) + sel_style)
                        for seg in part._segments
                    ]
                    new_parts.append(Strip(styled_segments, part.cell_length))
                else:
                    new_parts.append(part)
                curr = cut
            return Strip.join(new_parts)

        def selectable_static_render_line(self: Static, y: int):
            strip = orig_static_render_line(self, y)
            if not getattr(self, "allow_select", False):
                return strip

            try:
                selection = getattr(self, "text_selection", None)
            except Exception:
                selection = None

            if selection is not None:
                span = selection.get_span(y)
                if span is not None:
                    start_x, end_x = span
                    try:
                        screen_sel = getattr(self.screen, "selection_style", None)
                        if (
                            screen_sel
                            and screen_sel.color != screen_sel.bgcolor
                            and screen_sel.bgcolor
                        ):
                            sel_style = screen_sel
                        else:
                            sel_style = Style.parse("bold #ffffff on #0284c7")
                    except Exception:
                        sel_style = Style.parse("bold #ffffff on #0284c7")
                    strip = _stylize_strip_selection(strip, start_x, end_x, sel_style)

            # Apply offsets AFTER stylizing so Compositor receives exact, monotonically increasing
            # character cell coordinates for every split segment, completely eliminating jitter.
            return strip.apply_offsets(0, y)

        Static.render_line = selectable_static_render_line

        def selectable_static_selection_updated(self: Static, selection: Selection | None) -> None:
            # Repaint on demand without clearing _render_cache or marking _dirty_regions.
            # Avoids re-parsing and re-rendering Markdown on every mouse move.
            self._repaint_required = True
            try:
                self.screen.refresh(self.region, repaint=True, layout=False)
            except Exception:
                self.refresh()

        Static.selection_updated = selectable_static_selection_updated

        orig_static_get_selection = Static.get_selection

        def selectable_static_get_selection(self: Static, selection: Selection):
            if hasattr(self, "_render_cache") and self._render_cache and self._render_cache.lines:
                lines = [line.text for line in self._render_cache.lines]
                if not lines:
                    return "", "\n"
                start_y, start_x = (0, 0) if selection.start is None else selection.start.transpose
                end_y, end_x = (
                    (len(lines) - 1, len(lines[-1]))
                    if selection.end is None
                    else selection.end.transpose
                )
                start_y = max(0, min(len(lines) - 1, start_y))
                end_y = max(0, min(len(lines) - 1, end_y))
                if start_y > end_y or (start_y == end_y and start_x > end_x):
                    start_y, end_y = end_y, start_y
                    start_x, end_x = end_x, start_x
                if start_y == end_y:
                    return lines[start_y][start_x:end_x].rstrip(), "\n"
                res = [lines[start_y][start_x:].rstrip()]
                for y in range(start_y + 1, end_y):
                    res.append(lines[y].rstrip())
                res.append(lines[end_y][:end_x].rstrip())
                return "\n".join(res), "\n"
            visual = self._render()
            if isinstance(visual, Text):
                return selection.extract(str(visual)), "\n"
            return orig_static_get_selection(self, selection)

        Static.get_selection = selectable_static_get_selection

        # Clamp selection to the originating content widget to prevent leakage into UI chrome
        from textual.screen import SelectState

        def robust_watch_select_state(self: Screen, select_state: SelectState | None) -> None:
            if select_state is None:
                self._selecting = False
                self.refresh()
                return
            else:
                self._selecting = True

            if select_state.end is None:
                return

            if not select_state.is_attached_to_dom:
                self._select_state = None
                return

            start_widget = select_state.start.content_widget
            if start_widget is None:
                container = select_state.start.container
                if getattr(container, "allow_select", False):
                    start_widget = container
                elif hasattr(container, "children"):
                    for child in container.children:
                        if getattr(child, "allow_select", False):
                            start_widget = child
                            break

            if start_widget is not None and getattr(start_widget, "allow_select", False):
                region = getattr(start_widget, "content_region", start_widget.region)
                scroll_offset = (
                    start_widget.scroll_offset
                    if getattr(start_widget, "is_scrollable", False)
                    else getattr(start_widget, "container_scroll_offset", Offset(0, 0))
                )
                start_offset = select_state.start.content_offset
                if start_offset is None:
                    sx = max(
                        0,
                        select_state.start.pointer_start_offset.x - region.x + int(scroll_offset.x),
                    )
                    sy = max(
                        0,
                        select_state.start.pointer_start_offset.y - region.y + int(scroll_offset.y),
                    )
                    start_offset = Offset(sx, sy)

                if (
                    select_state.end.content_widget is start_widget
                    and select_state.end.content_offset is not None
                ):
                    end_offset = select_state.end.content_offset
                else:
                    rel_x = max(0, select_state.screen_offset.x - region.x + int(scroll_offset.x))
                    rel_y = max(0, select_state.screen_offset.y - region.y + int(scroll_offset.y))
                    if (
                        hasattr(start_widget, "_render_cache")
                        and start_widget._render_cache
                        and start_widget._render_cache.lines
                    ):
                        rel_y = min(len(start_widget._render_cache.lines) - 1, rel_y)
                    elif hasattr(start_widget, "line_count"):
                        total_l = start_widget.line_count + (
                            1 if getattr(start_widget, "_line_buffer", None) else 0
                        )
                        if total_l > 0:
                            rel_y = min(total_l - 1, rel_y)
                    end_offset = Offset(rel_x, rel_y)

                s_off, e_off = start_offset, end_offset
                if e_off.transpose < s_off.transpose:
                    s_off, e_off = e_off, s_off
                self.selections = {start_widget: Selection.from_offsets(s_off, e_off + (1, 0))}
                return

            # If start_widget is not a designated selectable widget, NEVER select anything.
            # Do NOT fall back to multi-widget container selection (which causes SELECT_ALL).
            self.selections = {}

        Screen._watch__select_state = robust_watch_select_state

        def sync_watch_selections(
            self: Screen,
            old_selections: dict,
            selections: dict,
        ) -> None:
            for widget in old_selections.keys() | selections.keys():
                widget.selection_updated(selections.get(widget, None))

        Screen._watch_selections = sync_watch_selections

        # Coalesce high-frequency mouse movements to prevent queue flooding and jitter
        from textual.events import MouseMove
        from textual.message import Message

        def mouse_move_can_replace(self: MouseMove, message: Message) -> bool:
            return (
                isinstance(message, MouseMove)
                and self.button == message.button
                and self.ctrl == message.ctrl
                and self.shift == message.shift
                and self.meta == message.meta
            )

        MouseMove.can_replace = mouse_move_can_replace

    except Exception:
        pass

    # 4. Resolve Alt+[ and Alt+] (and curlies) key bindings and legacy ANSI escape sequence parsing.
    # Root Cause:
    # 1) In Kitty/extended key protocol, terminals report 'alt+left_square_bracket' and 'alt+right_square_bracket',
    #    which Textual's KEY_ALIASES does not alias to 'alt+[' / 'alt+]'.
    # 2) Textual's App._check_bindings looks up only event.key directly without consulting aliases.
    # 3) In legacy ANSI parsing, XTermParser._sequence_to_key_events strips alt when name length > 1.
    try:
        from textual._xterm_parser import XTermParser
        from textual.app import App
        from textual.events import _get_key_aliases

        if (
            hasattr(_get_key_aliases, "__globals__")
            and "KEY_ALIASES" in _get_key_aliases.__globals__
        ):
            key_aliases_dict = _get_key_aliases.__globals__["KEY_ALIASES"]
            if "tab" in key_aliases_dict and "ctrl+i" in key_aliases_dict["tab"]:
                key_aliases_dict["tab"].remove("ctrl+i")
            key_aliases_dict.update(
                {
                    "alt+left_square_bracket": ["alt+[", "alt+{", "alt_left_square_bracket"],
                    "alt+[": ["alt+left_square_bracket"],
                    "alt+right_square_bracket": ["alt+]", "alt+}", "alt_right_square_bracket"],
                    "alt+]": ["alt+right_square_bracket"],
                    "alt+left_curly_bracket": ["alt+{", "alt+[", "alt_left_curly_bracket"],
                    "alt+{": ["alt+left_curly_bracket", "alt+left_square_bracket"],
                    "alt+right_curly_bracket": ["alt+}", "alt+]", "alt_right_curly_bracket"],
                    "alt+}": ["alt+right_curly_bracket", "alt+right_square_bracket"],
                    "alt+shift+left_square_bracket": ["alt+{", "alt+left_curly_bracket", "alt+["],
                    "alt+shift+right_square_bracket": ["alt+}", "alt+right_curly_bracket", "alt+]"],
                    # Ctrl+[ left sidebar shrink aliases
                    "ctrl+left_square_bracket": ["ctrl+[", "ctrl+{", "ctrl+left_square_brace"],
                    "ctrl+[": ["ctrl+left_square_bracket", "ctrl+left_square_brace"],
                    "ctrl+left_square_brace": ["ctrl+[", "ctrl+left_square_bracket"],
                    "ctrl+{": ["ctrl+[", "ctrl+left_square_bracket"],
                    "ctrl+left_curly_bracket": ["ctrl+[", "ctrl+left_square_bracket"],
                    "ctrl+shift+left_square_bracket": ["ctrl+[", "ctrl+left_square_bracket"],
                    # Ctrl+] left sidebar expand aliases
                    "ctrl+right_square_bracket": ["ctrl+]", "ctrl+}", "ctrl+right_square_brace"],
                    "ctrl+]": ["ctrl+right_square_bracket", "ctrl+right_square_brace"],
                    "ctrl+right_square_brace": ["ctrl+]", "ctrl+right_square_bracket"],
                    "ctrl+}": ["ctrl+]", "ctrl+right_square_bracket"],
                    "ctrl+right_curly_bracket": ["ctrl+]", "ctrl+right_square_bracket"],
                    "ctrl+shift+right_square_bracket": ["ctrl+]", "ctrl+right_square_bracket"],
                    # Ctrl+Alt+[ / Alt+Ctrl+[ right sidebar expand aliases
                    "ctrl+alt+left_square_bracket": [
                        "ctrl+alt+[",
                        "alt+ctrl+[",
                        "ctrl+alt+{",
                        "alt+ctrl+{",
                        "alt+ctrl+left_square_bracket",
                    ],
                    "alt+ctrl+left_square_bracket": [
                        "alt+ctrl+[",
                        "ctrl+alt+[",
                        "alt+ctrl+{",
                        "ctrl+alt+{",
                        "ctrl+alt+left_square_bracket",
                    ],
                    "ctrl+alt+[": [
                        "ctrl+alt+left_square_bracket",
                        "alt+ctrl+[",
                        "alt+ctrl+left_square_bracket",
                    ],
                    "alt+ctrl+[": [
                        "alt+ctrl+left_square_bracket",
                        "ctrl+alt+[",
                        "ctrl+alt+left_square_bracket",
                    ],
                    "ctrl+alt+{": [
                        "ctrl+alt+[",
                        "alt+ctrl+[",
                        "ctrl+alt+left_square_bracket",
                    ],
                    "alt+ctrl+{": [
                        "alt+ctrl+[",
                        "ctrl+alt+[",
                        "alt+ctrl+left_square_bracket",
                    ],
                    # Ctrl+Alt+] / Alt+Ctrl+] right sidebar shrink aliases
                    "ctrl+alt+right_square_bracket": [
                        "ctrl+alt+]",
                        "alt+ctrl+]",
                        "ctrl+alt+}",
                        "alt+ctrl+}",
                        "alt+ctrl+right_square_bracket",
                    ],
                    "alt+ctrl+right_square_bracket": [
                        "alt+ctrl+]",
                        "ctrl+alt+]",
                        "alt+ctrl+}",
                        "alt+ctrl+}",
                        "ctrl+alt+right_square_bracket",
                    ],
                    "ctrl+alt+]": [
                        "ctrl+alt+right_square_bracket",
                        "alt+ctrl+]",
                        "alt+ctrl+right_square_bracket",
                    ],
                    "alt+ctrl+]": [
                        "alt+ctrl+right_square_bracket",
                        "ctrl+alt+]",
                        "ctrl+alt+right_square_bracket",
                    ],
                    "ctrl+alt+}": [
                        "ctrl+alt+]",
                        "alt+ctrl+]",
                        "ctrl+alt+right_square_bracket",
                    ],
                    "alt+ctrl+}": [
                        "alt+ctrl+]",
                        "ctrl+alt+]",
                        "alt+ctrl+right_square_bracket",
                    ],
                    "ctrl+\x03": ["ctrl+delete", "delete"],
                    "shift+\x03": ["shift+delete", "delete"],
                    "alt+\x03": ["alt+delete", "delete"],
                    "ctrl+shift+\x03": ["ctrl+shift+delete", "ctrl+delete", "delete"],
                    "shift+ctrl+\x03": ["ctrl+shift+delete", "ctrl+delete", "delete"],
                    "alt+ctrl+\x03": ["alt+ctrl+delete", "ctrl+delete", "delete"],
                    "\x03": ["delete"],
                    "ctrl+shift+d": ["ctrl+d"],
                    "shift+ctrl+d": ["ctrl+d"],
                }
            )

        orig_check_bindings = App._check_bindings

        async def robust_check_bindings(self: App, key: str, priority: bool = False) -> bool:
            try:
                if await orig_check_bindings(self, key, priority=priority):
                    return True
            except Exception:
                pass
            try:
                for alias in _get_key_aliases(key):
                    if alias != key:
                        try:
                            if await orig_check_bindings(self, alias, priority=priority):
                                return True
                        except Exception:
                            pass
            except Exception:
                pass
            return False

        App._check_bindings = robust_check_bindings

        from functools import lru_cache

        from textual._xterm_parser import (
            FUNCTIONAL_KEYS,
            MODIFIER_FUNCTIONAL_KEYS,
            SPECIAL_KEY_TO_CHARACTER,
            _character_to_key,
            _re_extended_key,
        )
        from textual.events import Key
        from textual.keys import Keys

        @lru_cache(maxsize=1024)
        def patched_parse_extended_key(self: XTermParser, sequence: str) -> list[Key] | None:
            """Parse a Kitty extended keyboard sequence defensively.

            Remediates fatal ValueError when holding keys down under the Kitty Keyboard Protocol,
            where repeat events (event_type=2) format modifiers as 'modifiers:event_type' (e.g. '1:2').
            Upstream Textual evaluates int(modifiers_str), which raises ValueError: invalid literal for int()
            with base 10: '1:2', crashing LinuxDriver.run_input_thread and terminating the application.
            """
            if (match := _re_extended_key.fullmatch(sequence)) is None:
                return None

            codes, end = match.groups(default="")
            codepoint_str, modifiers_str, text_str, *_ = codes.split(";") + ["", "", ""]

            cp_part = codepoint_str.split(":")[0] if codepoint_str else "1"
            codepoint = int(cp_part) if cp_part.isdigit() else 1

            mod_parts = modifiers_str.split(":") if modifiers_str else ["0"]
            mod_val = mod_parts[0] if mod_parts and mod_parts[0].isdigit() else "0"
            modifiers = int(mod_val)
            event_type = int(mod_parts[1]) if len(mod_parts) > 1 and mod_parts[1].isdigit() else 1

            # event_type: 1 = press, 2 = repeat, 3 = release
            # For terminal apps, release events (3) must return Keys.Ignore so the parser terminates
            # the sequence without dispatching an event to the UI or hanging in the sequence loop.
            if event_type == 3:
                return [Key(Keys.Ignore, sequence)]

            key_events: list[Key] = []
            for text in self._parse_colon_codepoints(text_str):
                if not (key := FUNCTIONAL_KEYS.get(f"{codepoint}{end}", "")):
                    try:
                        key = _character_to_key(text if text else chr(codepoint))
                    except (ValueError, OverflowError):
                        key = "unknown"

                key_tokens: list[str] = []
                if modifiers and key not in MODIFIER_FUNCTIONAL_KEYS and text_str is not None:
                    modifier_bits = int(modifiers) - 1
                    MODIFIERS = ("alt", "ctrl", "super", "hyper", "meta")
                    if modifier_bits & 1 and (text is None or text.isspace()):
                        key_tokens.append("shift")
                    for bit, modifier in enumerate(MODIFIERS, 1):
                        if modifier == "alt" and text is not None:
                            continue
                        if modifier_bits & (1 << bit):
                            key_tokens.append(modifier)

                key_tokens.sort()
                if key is not None:
                    key_tokens.append(key)
                key_events.append(
                    Key(
                        "+".join(key_tokens),
                        text or (None if modifiers else SPECIAL_KEY_TO_CHARACTER.get(key, None)),
                    )
                )
            return key_events

        XTermParser._parse_extended_key = patched_parse_extended_key

        orig_seq_to_keys = XTermParser._sequence_to_key_events

        def safe_seq_to_keys(self: XTermParser, sequence: str, alt: bool = False):
            try:
                events = list(orig_seq_to_keys(self, sequence, alt=alt))
            except Exception:
                return
            for ev in events:
                try:
                    if alt and hasattr(ev, "key") and ev.key and not ev.key.startswith("alt+"):
                        yield ev.__class__(f"alt+{ev.key}", getattr(ev, "character", None))
                    else:
                        yield ev
                except Exception:
                    yield ev

        XTermParser._sequence_to_key_events = safe_seq_to_keys

        orig_feed = XTermParser.feed

        def safe_feed(self: XTermParser, data: str):
            try:
                for token in orig_feed(self, data):
                    yield token
            except Exception:
                return

        XTermParser.feed = safe_feed
    except Exception:
        pass

    # 5. Universal word deletion and navigation shortcuts for text input fields
    # Textual mistakenly bound ctrl+backspace/alt+backspace to delete_right_word instead of left.
    # Fix and complete universal shortcuts (Ctrl+Backspace, Ctrl+Delete, Ctrl+W, Ctrl+H, Alt+Backspace, Alt+Delete).
    try:
        from textual.binding import Binding
        from textual.widgets import Input, TextArea

        new_input_bindings = []
        for b in Input.BINDINGS:
            if ("backspace" in b.key and "delete_right_word" in b.action) or (
                "delete" in b.key and "delete_right" in b.action
            ):
                continue
            new_input_bindings.append(b)

        new_input_bindings.extend(
            [
                Binding(
                    "delete,shift+delete,ctrl+d",
                    "delete_right",
                    "Delete character right",
                    show=False,
                ),
                Binding(
                    "ctrl+backspace,alt+backspace,ctrl+w,ctrl+h",
                    "delete_left_word",
                    "Delete left to start of word",
                    show=False,
                ),
                Binding(
                    "ctrl+delete,alt+delete,ctrl+shift+delete,shift+ctrl+delete",
                    "delete_right_word",
                    "Delete right to start of word",
                    show=False,
                ),
            ]
        )
        Input.BINDINGS = new_input_bindings
        Input._merged_bindings = Input._merge_bindings()
        for subcls in Input.__subclasses__():
            try:
                subcls._merged_bindings = subcls._merge_bindings()
            except Exception:
                pass

        new_textarea_bindings = []
        for b in TextArea.BINDINGS:
            if (
                "ctrl+w" in b.key
                or "ctrl+backspace" in b.key
                or "alt+delete" in b.key
                or "ctrl+delete" in b.key
                or ("delete" in b.key and "delete_right" in b.action)
            ):
                continue
            new_textarea_bindings.append(b)

        new_textarea_bindings.extend(
            [
                Binding(
                    "delete,shift+delete,ctrl+d",
                    "delete_right",
                    "Delete character right",
                    show=False,
                ),
                Binding(
                    "ctrl+w,ctrl+backspace,alt+backspace,ctrl+h",
                    "delete_word_left",
                    "Delete left to start of word",
                    show=False,
                ),
                Binding(
                    "ctrl+delete,alt+delete,ctrl+shift+delete,shift+ctrl+delete",
                    "delete_word_right",
                    "Delete right to start of word",
                    show=False,
                ),
            ]
        )
        TextArea.BINDINGS = new_textarea_bindings
        TextArea._merged_bindings = TextArea._merge_bindings()
        for subcls in TextArea.__subclasses__():
            try:
                subcls._merged_bindings = subcls._merge_bindings()
            except Exception:
                pass
    except Exception:
        pass

    # 7. Protect Widget._message_loop_exit against asyncio.CancelledError during DOM teardown in Python 3.12+
    try:
        import asyncio

        import textual.widget as _w
        from textual import events
        from textual.dom import DOMNode
        from textual.messages import Prune

        async def safe_message_loop_exit(self: _w.Widget) -> None:
            parent = self._parent
            children = [*self.children, *self._get_virtual_dom()]
            for node in children:
                node.post_message(Prune())

            await asyncio.gather(
                *[node._task for node in children if node._task is not None],
                return_exceptions=True,
            )
            try:
                await self._dispatch_message(events.Unmount())
            except Exception:
                pass
            if isinstance(parent, DOMNode):
                parent._nodes._remove(self)
            if hasattr(self, "app") and hasattr(self.app, "_registry"):
                self.app._registry.discard(self)
            self._detach()
            self._arrangement_cache.clear()
            self._nodes._clear()
            self._render_cache = _w._RenderCache(_w.NULL_SIZE, [])
            self._component_styles.clear()
            self._query_one_cache.clear()

        _w.Widget._message_loop_exit = safe_message_loop_exit
    except (ImportError, AttributeError):
        pass

    # 8. Protect Screen.dismiss and App.pop_screen against double-dismissal and ScreenStackError.
    # When keys (like F1, Escape, or Q) repeat rapidly or are held down, multiple Key events can be
    # processed before a modal unmounts. Without idempotency guards, repeated dismiss() calls pop
    # underlying screens (e.g. DashboardScreen) and crash the app with ScreenStackError.
    try:
        orig_screen_dismiss = Screen.dismiss

        def safe_screen_dismiss(self: Screen, result: Any = None) -> Any:
            if getattr(self, "_screen_dismissed", False):
                return None

            app = getattr(self, "app", None)
            if app is None:
                self._screen_dismissed = True
                return None

            stack = getattr(app, "_screen_stack", None)
            if not stack or len(stack) <= 1 or self not in stack:
                self._screen_dismissed = True
                return None

            # Only pop if this screen is the topmost active screen
            if stack[-1] is not self:
                self._screen_dismissed = True
                return None

            self._screen_dismissed = True
            try:
                return orig_screen_dismiss(self, result)
            except ScreenStackError:
                return None

        Screen.dismiss = safe_screen_dismiss

        orig_app_pop_screen = App.pop_screen

        def safe_app_pop_screen(self: App) -> Any:
            stack = getattr(self, "_screen_stack", [])
            if len(stack) <= 1:
                return None
            try:
                return orig_app_pop_screen(self)
            except ScreenStackError:
                return None

        App.pop_screen = safe_app_pop_screen
    except (ImportError, AttributeError):
        pass

    # 9. Register native CyGuide theme for TextArea widgets (Obsidian Slate with no cursor line highlight)
    try:
        import textual._text_area_theme as tat
        from rich.style import Style
        from textual.widgets.text_area import TextAreaTheme

        vscode = tat._BUILTIN_THEMES.get("vscode_dark")
        cyguide_theme = TextAreaTheme(
            name="cyguide",
            base_style=Style(color="#cbd5e1", bgcolor="#0f1114"),
            gutter_style=Style(color="#475569", bgcolor="#0f1114"),
            cursor_style=Style(color="#38bdf8", underline=True),
            cursor_line_style=Style(bgcolor="#0f1114"),
            cursor_line_gutter_style=Style(color="#38bdf8", bgcolor="#0f1114"),
            selection_style=Style(color="#f8fafc", bgcolor="#1e3a5f"),
            bracket_matching_style=Style(color="#38bdf8", bgcolor="#1e293b", bold=True),
            syntax_styles=dict(vscode.syntax_styles) if vscode else {},
        )
        tat._BUILTIN_THEMES["cyguide"] = cyguide_theme
    except Exception:
        pass

    # 10. Protect rich._wrap.divide_line against zero or negative widths.
    # In Textual, when containers or sidebars animate width to 0, widgets with padding
    # calculate line wrap width as `width - line_pad * 2 <= 0`. Passing 0 or negative
    # width to Rich causes `chop_cells` to raise unhandled `ValueError: range() arg 3 must not be zero`.
    try:
        import rich._wrap as _rw
        import textual.content as _tc

        orig_divide_line = _rw.divide_line

        def safe_divide_line(text: str, width: int, fold: bool = True) -> list[int]:
            if width <= 0:
                return []
            return orig_divide_line(text, width, fold=fold)

        _rw.divide_line = safe_divide_line
        _tc.divide_line = safe_divide_line
    except Exception:
        pass

    # 11. Defend against ScalarResolveError when animating auto dimensions.
    # In Textual, when widgets transition styles (e.g. during focus changes, widget hiding,
    # or sidebar collapse), the stylesheet creates ScalarAnimation for changed dimensions.
    # If a widget's dimension is 'auto' (Unit.AUTO), resolving it in ScalarAnimation raises
    # unhandled `ScalarResolveError: expected dimensions; found 'auto'` and crashes the process.
    try:
        from textual.css.scalar import Scalar, ScalarResolveError
        from textual.css.scalar_animation import ScalarAnimation

        orig_scalar_anim_init = ScalarAnimation.__init__

        def safe_scalar_anim_init(
            self: Any,
            widget: Any,
            styles: Any,
            start_time: float,
            attribute: str,
            value: Any,
            duration: float | None = None,
            speed: float | None = None,
            easing: Any = None,
            on_complete: Any = None,
            level: Any = "full",
            *args: Any,
            **kwargs: Any,
        ) -> None:
            try:
                orig_scalar_anim_init(
                    self,
                    widget,
                    styles,
                    start_time,
                    attribute,
                    value,
                    duration,
                    speed,
                    easing,
                    on_complete,
                    level,
                    *args,
                    **kwargs,
                )
            except ScalarResolveError:
                self.widget = widget
                self.styles = styles
                self.start_time = start_time
                self.attribute = attribute
                self.final_value = value
                self.easing = easing
                self.on_complete = on_complete
                self.level = level

                size = widget.outer_size
                viewport = widget.app.size

                try:
                    self.start = getattr(styles, attribute).resolve(size, viewport)
                except (ScalarResolveError, Exception):
                    val = getattr(size, attribute, 0)
                    self.start = Scalar.from_number(float(val)).resolve(size, viewport)

                try:
                    self.destination = value.resolve(size, viewport)
                except (ScalarResolveError, Exception):
                    val = getattr(size, attribute, 0)
                    self.destination = Scalar.from_number(float(val)).resolve(size, viewport)

                if speed is not None:
                    distance = self.start.get_distance_to(self.destination)
                    self.duration = distance / speed if speed > 0 else (duration or 0.2)
                else:
                    self.duration = duration if duration is not None else 0.2

        ScalarAnimation.__init__ = safe_scalar_anim_init
    except Exception:
        pass

    # 12. Optimize ToastRack notification display:
    # - Cap simultaneous notifications to max 3 so notifications never flood or obstruct the terminal.
    # - Deduplicate rapid duplicate notifications (prune older identical notification if new one arrives).
    # - Ensure topmost layer on ToastRack, ToastHolder, and Toast so they never render behind any element.
    try:
        from textual.app import App
        from textual.notifications import Notify

        orig_on_notify = App._on_notify

        def safe_on_notify(self: Any, event: Notify) -> None:
            new_n = event.notification
            # 1. Deduplicate: remove any existing unexpired notification with identical title and message
            for existing in list(self._notifications):
                if existing.title == new_n.title and existing.message == new_n.message:
                    self._unnotify(existing, refresh=False)

            # 2. Cap active notifications to max 3
            while len(self._notifications) >= 3:
                oldest = next(iter(self._notifications))
                self._unnotify(oldest, refresh=False)

            orig_on_notify(self, event)

        App._on_notify = safe_on_notify
    except Exception:
        pass

    # Suppress all floating tooltip popups across all Textual screens
    try:
        App._disable_tooltips = True
    except Exception:
        pass

    try:
        Screen._handle_tooltip_timer = lambda self, widget: None
    except Exception:
        pass

    try:
        from rich.text import Text
        from textual.widgets import Tooltip

        Tooltip.DEFAULT_CSS = "Tooltip { display: none !important; width: 0 !important; height: 0 !important; border: none !important; margin: 0 !important; padding: 0 !important; background: transparent !important; }"
        Tooltip.render = lambda self: Text("")
    except Exception:
        pass


# Automatically initialize compatibility shims and themes on import
setup_textual_compat()
