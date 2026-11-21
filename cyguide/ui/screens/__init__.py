"""CyGuide UI screens (lazy-loaded to minimize application startup latency)."""

__all__ = [
    "DashboardScreen",
    "LearningModeScreen",
    "PowerModeScreen",
    "ToolBrowserScreen",
    "ToolHealthModal",
    "PreflightModal",
    "PreflightModalResult",
    "ConfigModal",
    "ConfigProvider",
    "BaseConfigCommandProvider",
    "OllamaConfigProvider",
    "CloudAPIConfigProvider",
    "DatabaseConfigProvider",
    "ToolsConfigProvider",
]

_SCREEN_MAP = {
    "DashboardScreen": ("cyguide.ui.screens.home", "DashboardScreen"),
    "LearningModeScreen": ("cyguide.ui.screens.learning", "LearningModeScreen"),
    "PowerModeScreen": ("cyguide.ui.screens.power", "PowerModeScreen"),
    "ToolBrowserScreen": ("cyguide.ui.screens.tool_browser", "ToolBrowserScreen"),
    "ToolHealthModal": ("cyguide.ui.screens.tool_health_modal", "ToolHealthModal"),
    "PreflightModal": ("cyguide.ui.screens.preflight_modal", "PreflightModal"),
    "PreflightModalResult": ("cyguide.ui.screens.preflight_modal", "PreflightModalResult"),
    "ConfigModal": ("cyguide.ui.screens.config_modal", "ConfigModal"),
    "ConfigProvider": ("cyguide.ui.screens.config_modal", "ConfigProvider"),
    "BaseConfigCommandProvider": ("cyguide.ui.screens.config_modal", "BaseConfigCommandProvider"),
    "OllamaConfigProvider": ("cyguide.ui.screens.config_modal", "OllamaConfigProvider"),
    "CloudAPIConfigProvider": ("cyguide.ui.screens.config_modal", "CloudAPIConfigProvider"),
    "DatabaseConfigProvider": ("cyguide.ui.screens.config_modal", "DatabaseConfigProvider"),
    "ToolsConfigProvider": ("cyguide.ui.screens.config_modal", "ToolsConfigProvider"),
}


def __getattr__(name: str):
    if name in _SCREEN_MAP:
        mod_name, attr_name = _SCREEN_MAP[name]
        mod = __import__(mod_name, fromlist=[attr_name])
        val = getattr(mod, attr_name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
