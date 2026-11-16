"""Lazy loader factories for non-initial screens to minimize startup latency."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def load_tool_browser() -> Any:
    """Lazy load ToolBrowserScreen on first navigation."""
    from cyguide.ui.screens.tool_browser import ToolBrowserScreen

    return ToolBrowserScreen()


def load_learning_mode() -> Any:
    """Lazy load LearningModeScreen on first navigation."""
    from cyguide.ui.screens.learning import LearningModeScreen

    return LearningModeScreen()


def load_power_mode() -> Any:
    """Lazy load PowerModeScreen on first navigation."""
    from cyguide.ui.screens.power import PowerModeScreen

    return PowerModeScreen()


def load_config_modal() -> Any:
    """Lazy load ConfigModal on first navigation."""
    from cyguide.ui.screens.config_modal import ConfigModal

    return ConfigModal()
