"""CyGuide UI widgets."""

from cyguide.ui.widgets.power import (
    CommandPalette,
    EntityBrowser,
    JobQueue,
)
from cyguide.ui.widgets.resizer import ResizeHandle
from cyguide.ui.widgets.scrollbar import ThinScrollBarRender, setup_thin_scrollbars
from cyguide.ui.widgets.terminal_stream import TerminalStreamPane

__all__ = [
    "EntityBrowser",
    "JobQueue",
    "CommandPalette",
    "ResizeHandle",
    "TerminalStreamPane",
    "ThinScrollBarRender",
    "setup_thin_scrollbars",
]
