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
