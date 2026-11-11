"""Textual compatibility and resilience hardening.

Protects against upstream Textual runtime issues, notably:
1. AttributeError ('NoneType' object has no attribute 'region') in Screen._forward_event
   when widgets (such as Markdown tables or rapidly updating elements) are unmounted or
   detached while mouse clicks/drags are in flight.
2. MarkdownTableContent grid container erroneously accepting selection hits without
   a valid parent container.
"""

from __future__ import annotations

import logging

from textual.events import Event
from textual.screen import Screen

logger = logging.getLogger(__name__)

_COMPAT_INITIALIZED = False


def setup_textual_compat() -> None:
    """Apply defensive hardening to Textual runtime."""
    global _COMPAT_INITIALIZED
    if _COMPAT_INITIALIZED:
        return
    _COMPAT_INITIALIZED = True

    # 1. Prevent MarkdownTableContent grid container from triggering selection calculation
    try:
        from textual.widgets._markdown import MarkdownTableContent

        MarkdownTableContent.ALLOW_SELECT = False
    except (ImportError, AttributeError):
        pass

    # 2. Defensively wrap Screen._forward_event against NoneType container/region crashes
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
