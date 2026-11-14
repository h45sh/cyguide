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

from textual.events import Event
from textual.screen import Screen

logger = logging.getLogger(__name__)

_COMPAT_INITIALIZED = False


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
                "command_preview",
                "test_static",
            ):
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
            if end_x == -1:
                end_x = strip.cell_length
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

            strip = strip.apply_offsets(0, y)
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
            return strip

        Static.render_line = selectable_static_render_line

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
            if start_widget is not None and getattr(start_widget, "allow_select", False):
                start_offset = select_state.start.content_offset or Offset(0, 0)
                if (
                    select_state.end.content_widget is start_widget
                    and select_state.end.content_offset is not None
                ):
                    end_offset = select_state.end.content_offset
                else:
                    region = start_widget.region
                    rel_x = max(0, min(region.width, select_state.screen_offset.x - region.x))
                    rel_y = max(0, select_state.screen_offset.y - region.y)
                    if (
                        hasattr(start_widget, "_render_cache")
                        and start_widget._render_cache
                        and start_widget._render_cache.lines
                    ):
                        rel_y = min(len(start_widget._render_cache.lines) - 1, rel_y)
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
                }
            )

        orig_check_bindings = App._check_bindings

        async def robust_check_bindings(self: App, key: str, priority: bool = False) -> bool:
            if await orig_check_bindings(self, key, priority=priority):
                return True
            for alias in _get_key_aliases(key):
                if alias != key:
                    if await orig_check_bindings(self, alias, priority=priority):
                        return True
            return False

        App._check_bindings = robust_check_bindings

        orig_seq_to_keys = XTermParser._sequence_to_key_events

        def safe_seq_to_keys(self: XTermParser, sequence: str, alt: bool = False):
            for ev in orig_seq_to_keys(self, sequence, alt=alt):
                if alt and not ev.key.startswith("alt+"):
                    yield ev.__class__(f"alt+{ev.key}", ev.character)
                else:
                    yield ev

        XTermParser._sequence_to_key_events = safe_seq_to_keys
    except Exception:
        pass
