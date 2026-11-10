"""Main CyGuide TUI Application."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from textual import events, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import (
    CommandInput,
    CommandList,
    CommandPalette,
    DiscoveryHit,
    Hits,
    SearchIcon,
)
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.system_commands import SystemCommandsProvider
from textual.widgets import Button, LoadingIndicator

from cyguide.engine.explainer import is_placeholder_key

# Replace default emoji search icon with clean terminal glyph
SearchIcon.icon = "›"

# Ensure thin, uniform scrollbars across all screens and widgets
from cyguide.ui.widgets.scrollbar import setup_thin_scrollbars

setup_thin_scrollbars()


class ToolHealthChanged(Message):
    """Event emitted when tool health status changes."""

    def __init__(self, health: dict) -> None:
        super().__init__()
        self.health = health



class CyGuideSystemCommandsProvider(SystemCommandsProvider):
    """Command palette provider that preserves natural menu order without alphabetical sorting."""

    async def discover(self) -> Hits:
        for name, help_text, callback, discover in self.app.get_system_commands(self.screen):
            if discover:
                yield DiscoveryHit(
                    name,
                    callback,
                    help=help_text,
                )


class CyGuideCommandInput(CommandInput):
    """Command input that delegates left/right arrow navigation to the palette."""

    def action_cursor_right(self, select: bool = False) -> None:
        if self.cursor_position >= len(self.value) and not self._suggestion:
            palette = self.screen
            if isinstance(palette, CyGuideCommandPalette):
                palette.handle_right_arrow()
                return
        super().action_cursor_right(select)

    def action_cursor_left(self, select: bool = False) -> None:
        if self.cursor_position <= 0 and not self.value:
            palette = self.screen
            if isinstance(palette, CyGuideCommandPalette):
                palette.handle_left_arrow()
                return
        super().action_cursor_left(select)


class CyGuideCommandPalette(CommandPalette):
    """Command palette with left/right arrow sub-menu navigation and highlight memory."""

    def __init__(
        self,
        providers=None,
        *,
        placeholder: str = "Search for commands…",
        is_sub_palette: bool = False,
        parent_action=None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            providers=providers,
            placeholder=placeholder,
            name=name,
            id=id,
            classes=classes,
        )
        self.is_sub_palette = is_sub_palette
        self.parent_action = parent_action

    def compose(self) -> ComposeResult:
        with Vertical(id="--container"):
            with Horizontal(id="--input"):
                yield SearchIcon()
                yield CyGuideCommandInput(placeholder=self._placeholder, select_on_focus=False)
                if not self.run_on_select:
                    yield Button("\u25b6")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()

    def _refresh_command_list(
        self, command_list: CommandList, commands: list, clear_current: bool
    ) -> None:
        CommandPalette._refresh_command_list(self, command_list, commands, clear_current)
        last = getattr(self.app, "last_palette_highlight", None)
        if last is not None and command_list.option_count > 0:
            if isinstance(last, int) and 0 <= last < command_list.option_count:
                command_list.highlighted = last
            elif isinstance(last, str):
                for i, o in enumerate(command_list.options):
                    if last.lower() in str(o.prompt).lower():
                        command_list.highlighted = i
                        break

    def handle_right_arrow(self) -> None:
        try:
            command_list = self.query_one(CommandList)
            if command_list.option_count > 0:
                if command_list.highlighted is None:
                    command_list.highlighted = 0
                opt = command_list.options[command_list.highlighted]
                prompt_str = str(opt.prompt)
                clean_title = prompt_str.split("  ")[0].strip()
                self.app.last_palette_highlight = clean_title
                self.app._navigating_sub_palette = True
                self._action_command_list("select")
        except Exception:
            pass

    def handle_left_arrow(self) -> None:
        if self.is_sub_palette:
            self.dismiss()
            if self.parent_action is not None:
                self.parent_action()
            else:
                self.app.action_command_palette(preserve_highlight=True)
        else:
            self._action_escape()

    def on_unmount(self) -> None:
        if not self.is_sub_palette and not getattr(self.app, "_navigating_sub_palette", False):
            self.app.last_palette_highlight = None

    async def on_tool_health_changed(self, event: Any) -> None:
        """Refresh command list in real time when tool health status changes."""
        try:
            cmd_input = self.query_one(CyGuideCommandInput)
            self._search_for(cmd_input.value)
        except Exception:
            pass

    async def on_cy_guide_app_tool_health_changed(self, event: Any) -> None:
        await self.on_tool_health_changed(event)

    def on_key(self, event: events.Key) -> None:
        if event.key == "right":
            event.stop()
            self.handle_right_arrow()
        elif event.key == "left":
            event.stop()
            self.handle_left_arrow()

import subprocess
from typing import Any, Dict, List, Optional

from cyguide.engine.executor import Executor
from cyguide.engine.explainer import LearningExplainer, OllamaBackend
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.modes.learning import LearningModeEngine
from cyguide.paths import (
    get_default_data_dir,
    get_default_db_path,
    get_default_exports_dir,
    get_default_reports_dir,
    get_default_scratchpad_path,
    get_default_settings_path,
)
from cyguide.ui.screens.config_modal import ConfigModal
from cyguide.ui.screens.home import DashboardScreen
from cyguide.ui.screens.learning import LearningModeScreen
from cyguide.ui.screens.power import PowerModeScreen
from cyguide.ui.screens.tool_browser import ToolBrowserScreen


class CyGuideApp(App):
    """The central orchestrator for the CyGuide TUI."""

    CSS_PATH = "ui/style.css"
    TITLE = "CyGuide"
    COMMANDS = {CyGuideSystemCommandsProvider}
    ToolHealthChanged = ToolHealthChanged

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Palette", show=False),
    ]

    # Register screens so they can be switched by name
    SCREENS = {
        "dashboard": DashboardScreen,
        "tool_browser": ToolBrowserScreen,
        "learning_mode": LearningModeScreen,
        "power_mode": PowerModeScreen,
        "config_modal": ConfigModal,
    }

    def __init__(
        self,
        db_path: Optional[str] = None,
        data_dir: Optional[str] = None,
        use_ollama: bool = False,
        ollama_model: str = "gemma",
        tools_dir: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.data_dir = data_dir or get_default_data_dir()
        self.db_path = db_path or get_default_db_path(self.data_dir)
        self.use_ollama = use_ollama
        self.ollama_model = ollama_model
        self.tools_dir = tools_dir
        self.selected_session_id: Optional[str] = None
        self.selected_workspace_id: Optional[str] = None
        self.user_env: Dict[str, str] = os.environ.copy()
        self.user_shell: str = "/bin/bash"
        self._cached_tool_health: Dict[str, Dict[str, Any]] = {}

        # Ensure the directory for the database exists
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(self.db_path))
            os.makedirs(db_dir, exist_ok=True)

        # Persistent settings
        self.settings: Dict[str, Any] = self._load_settings()
        self.animations_enabled: bool = self.settings.get("animations_enabled", True)
        if "theme" in self.settings:
            self.theme = self.settings["theme"]

        # Apply saved settings when not explicitly overridden by non-default CLI arguments
        if "use_ollama" in self.settings and not use_ollama:
            self.use_ollama = self.settings["use_ollama"]
        if "ollama_model" in self.settings and ollama_model == "gemma":
            self.ollama_model = self.settings["ollama_model"]
        if "tools_dir" in self.settings and tools_dir is None:
            self.tools_dir = self.settings["tools_dir"]
        if "db_path" in self.settings and db_path is None:
            self.db_path = self.settings["db_path"]
            if self.db_path != ":memory:":
                db_dir = os.path.dirname(os.path.abspath(self.db_path))
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
        self.exports_dir: Optional[str] = kwargs.get("exports_dir")
        if "exports_dir" in self.settings and self.exports_dir is None:
            self.exports_dir = self.settings["exports_dir"]
        self.reports_dir: Optional[str] = kwargs.get("reports_dir")
        if "reports_dir" in self.settings and self.reports_dir is None:
            self.reports_dir = self.settings["reports_dir"]

        # Multi-key profiles and active key configuration
        self.use_cloud_api: bool = self.settings.get("use_cloud_api", True)
        raw_cloud_keys = self.settings.get("cloud_keys")
        if raw_cloud_keys is not None:
            # Multi-key system already configured in settings! Keep user profiles, normalizing placeholder keys to blank
            self.cloud_keys: List[Dict[str, Any]] = []
            for k in raw_cloud_keys:
                kd = dict(k)
                if is_placeholder_key(kd.get("api_key")):
                    kd["api_key"] = ""
                self.cloud_keys.append(kd)
        else:
            # One-time migration only if 'cloud_keys' was NEVER configured in settings
            self.cloud_keys = []
            legacy_key = self.settings.get("api_key") or os.environ.get("CYGUIDE_API_KEY") or os.environ.get("GROQ_API_KEY")
            if legacy_key and not is_placeholder_key(legacy_key):
                legacy_profile = {
                    "id": "key_1",
                    "name": "Primary Key",
                    "provider": self.settings.get("api_type") or os.environ.get("CYGUIDE_API_TYPE", "openai"),
                    "api_key": legacy_key,
                    "model": self.settings.get("api_model") or os.environ.get("CYGUIDE_API_MODEL", ""),
                    "base_url": self.settings.get("api_base") or os.environ.get("CYGUIDE_API_BASE", ""),
                    "enabled": True,
                }
                self.cloud_keys = [legacy_profile]

        self.active_key_id: Optional[str] = self.settings.get("active_key_id")
        if self.cloud_keys:
            if not self.active_key_id or not any(k.get("id") == self.active_key_id for k in self.cloud_keys):
                self.active_key_id = self.cloud_keys[0]["id"]
        else:
            self.active_key_id = None

        # Apply active cloud API configuration to environment
        active_prof = self.get_active_cloud_key()
        if active_prof and active_prof.get("api_key"):
            os.environ["CYGUIDE_API_KEY"] = str(active_prof["api_key"])
            if active_prof.get("provider"):
                os.environ["CYGUIDE_API_TYPE"] = str(active_prof["provider"])
            if active_prof.get("model"):
                os.environ["CYGUIDE_API_MODEL"] = str(active_prof["model"])
            if active_prof.get("base_url"):
                os.environ["CYGUIDE_API_BASE"] = str(active_prof["base_url"])
        else:
            for env_k, set_k in (
                ("CYGUIDE_API_KEY", "api_key"),
                ("CYGUIDE_API_TYPE", "api_type"),
                ("CYGUIDE_API_BASE", "api_base"),
                ("CYGUIDE_API_MODEL", "api_model"),
            ):
                if self.settings.get(set_k):
                    os.environ[env_k] = str(self.settings[set_k])

    def get_active_cloud_key(self) -> Optional[Dict[str, Any]]:
        """Return the active cloud key profile dictionary."""
        if not hasattr(self, "cloud_keys") or not self.cloud_keys:
            return None
        for k in self.cloud_keys:
            if k.get("id") == self.active_key_id:
                return k
        return self.cloud_keys[0]

    def action_switch_active_key(self, key_id: str) -> None:
        """Switch the active cloud API key and reload the explanation engine."""
        if not hasattr(self, "cloud_keys") or not self.cloud_keys:
            return
        found = False
        target_name = key_id
        for k in self.cloud_keys:
            if k.get("id") == key_id:
                self.active_key_id = key_id
                target_name = k.get("name") or k.get("provider") or key_id
                found = True
                break
        if found:
            self._save_settings({
                "active_key_id": self.active_key_id,
                "cloud_keys": self.cloud_keys,
            })
            self.reload_explainer()
            self.notify(f"Switched active AI key to: {target_name}", title="AI Key Switcher")

    def _get_settings_path(self) -> Optional[str]:
        if self.db_path == ":memory:":
            return None
        if hasattr(self, "data_dir") and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_settings_path(self.data_dir)
        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "settings.json")

    def get_scratchpad_path(self) -> str:
        """Return the path to the operator note-taking scratchpad file."""
        if self.db_path == ":memory:":
            return ":memory:"
        if hasattr(self, "data_dir") and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_scratchpad_path(self.data_dir)
        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        return os.path.join(base_dir, "scratchpad.md")

    def get_exports_dir(self) -> str:
        """Return the directory path for exported database archives."""
        if getattr(self, "exports_dir", None):
            os.makedirs(self.exports_dir, mode=0o700, exist_ok=True)
            return self.exports_dir
        if hasattr(self, "data_dir") and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_exports_dir(self.data_dir)
        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        exports_dir = os.path.join(base_dir, "exports")
        os.makedirs(exports_dir, mode=0o700, exist_ok=True)
        return exports_dir

    def get_reports_dir(self) -> str:
        """Return the directory path for exported markdown reports."""
        if getattr(self, "reports_dir", None):
            os.makedirs(self.reports_dir, mode=0o700, exist_ok=True)
            return self.reports_dir
        if hasattr(self, "data_dir") and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_reports_dir(self.data_dir)
        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        reports_dir = os.path.join(base_dir, "reports")
        os.makedirs(reports_dir, mode=0o700, exist_ok=True)
        return reports_dir

    def _load_settings(self) -> Dict[str, Any]:
        path = self._get_settings_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_settings(self, updates: Dict[str, Any]) -> None:
        if not hasattr(self, "settings") or self.settings is None:
            self.settings = {}
        self.settings.update(updates)
        path = self._get_settings_path()
        if not path:
            return
        try:
            current = self._load_settings()
            current.update(updates)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "w", encoding="utf-8", closefd=False) as f:
                    json.dump(current, f, indent=2)
            finally:
                os.close(fd)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            pass

    def watch_theme(self, new_theme: str) -> None:
        if hasattr(self, "_save_settings"):
            self._save_settings({"theme": new_theme})

    def detect_user_shell(self) -> str:
        """Find the user's default shell."""
        return os.environ.get("SHELL", "/bin/bash")

    def get_shell_environment(self) -> Dict[str, str]:
        """Capture the full login shell environment."""
        shell = self.detect_user_shell()
        try:
            # Run a login shell to capture the fully resolved environment
            result = subprocess.run(
                [shell, "-l", "-c", "env"],
                capture_output=True, text=True, timeout=5
            )
            env = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    key, _, val = line.partition("=")
                    env[key] = val
            return env if env else os.environ.copy()
        except Exception:
            return os.environ.copy()

    @work(exclusive=True, group="shell_env")
    async def _async_load_shell_env(self) -> None:
        """Capture the full login shell environment in the background without blocking startup."""
        try:
            env = await asyncio.to_thread(self.get_shell_environment)
            if env:
                self.user_env = env
                if hasattr(self, "power_facade") and self.power_facade:
                    self.power_facade.user_env = env
        except Exception:
            pass

    def check_and_update_tool_health(self) -> Dict[str, Dict[str, Any]]:
        """Check current tool health against registered tools, update cache, and broadcast changes if any."""
        reg = getattr(self, "registry", None)
        if not reg:
            return getattr(self, "_cached_tool_health", {}) or {}

        # If tools directory changed on disk (e.g. tools deleted or added), reload tools
        tools_dir = getattr(reg, "tools_dir", None)
        if tools_dir and Path(tools_dir).exists():
            try:
                current_dirs = {p.name for p in Path(tools_dir).iterdir() if p.is_dir() and not p.name.startswith((".", "_"))}
                loaded_dirs = {v.get("path").name for v in reg.tools.values() if v.get("path")}
                if current_dirs != loaded_dirs:
                    reg.load_tools()
            except Exception:
                pass

        try:
            from cyguide.engine.diagnostics import check_tool_health
            new_health = check_tool_health(reg)
        except Exception:
            return getattr(self, "_cached_tool_health", {}) or {}

        old_health = getattr(self, "_cached_tool_health", {}) or {}

        changed = False
        if not old_health or len(old_health) != len(new_health):
            changed = True
        else:
            for k, v in new_health.items():
                if k not in old_health:
                    changed = True
                    break
                old_v = old_health[k]
                if (
                    old_v.get("status") != v.get("status")
                    or old_v.get("healthy") != v.get("healthy")
                    or old_v.get("binary") != v.get("binary")
                ):
                    changed = True
                    break

        self._cached_tool_health = new_health

        if changed:
            msg = ToolHealthChanged(new_health)
            for s in list(getattr(self, "screen_stack", [])):
                try:
                    s.post_message(msg)
                except Exception:
                    pass

        return new_health

    def _async_refresh_tool_health_cache(self) -> None:
        """Cache tool health diagnostics and broadcast any state changes."""
        self.check_and_update_tool_health()

    async def on_mount(self) -> None:
        """Initialize the app with core components and the dashboard."""
        self.user_shell = self.detect_user_shell()
        self.user_env = os.environ.copy()
        self._async_load_shell_env()

        self.learning_mode_tool = "nmap" # Default
        # 1. Initialize Engines
        self.registry = ToolRegistry(tools_dir=self.tools_dir)
        self.registry.load_tools()

        # Initial tool health check and start real-time periodic watcher (2s interval)
        self.check_and_update_tool_health()
        self.set_interval(2.0, self.check_and_update_tool_health, name="tool_health_watcher")

        self.store = GraphStore(self.db_path)
        await self.store.initialize()

        # Ensure singleton Learning Sandbox exists
        self.learning_ws_id, self.learning_session_id = await self.store.get_or_create_learning_sandbox()

        from cyguide.engine.recommendation import RecommendationEngine
        self.recommendation_engine = RecommendationEngine(self.store)
        self.store.on_upsert(self.recommendation_engine.handle_upsert)

        self.executor = Executor(self.store)

        # Setup Explainer
        self.reload_explainer()

        self.learning_engine = LearningModeEngine(self.registry, self.executor, self.explainer)
        self.power_facade = PowerWorkspaceFacade(self.store, self.executor, self.registry)
        self.power_facade.user_env = self.user_env
        self.power_facade.user_shell = self.user_shell

        # 2. Setup UI
        self.push_screen("dashboard")
        if not self.animations_enabled:
            self.add_class("no-animations")

    def reload_explainer(self) -> None:
        """Setup or reload explanation backend based on current settings and environment."""
        from dotenv import load_dotenv
        load_dotenv()
        ollama_base_url = self.settings.get("ollama_base_url", "http://localhost:11434")
        if self.use_ollama or not getattr(self, "use_cloud_api", True):
            self.explainer_backend = OllamaBackend(model=self.ollama_model, base_url=ollama_base_url)
        else:
            from cyguide.engine.explainer import CloudKeyProfile, MultiKeyCloudBackend
            profiles: List[CloudKeyProfile] = []
            if hasattr(self, "cloud_keys") and self.cloud_keys:
                for k in self.cloud_keys:
                    raw_k = k.get("api_key")
                    if raw_k and not is_placeholder_key(raw_k):
                        profiles.append(CloudKeyProfile.from_dict(k))

            # Only fallback to legacy if 'cloud_keys' was NEVER configured in settings
            if "cloud_keys" not in self.settings and not profiles:
                api_key = self.settings.get("api_key") or os.environ.get("CYGUIDE_API_KEY") or os.environ.get("GROQ_API_KEY")
                if api_key and not is_placeholder_key(api_key):
                    api_type = self.settings.get("api_type") or os.environ.get("CYGUIDE_API_TYPE", "openai")
                    if (os.environ.get("GROQ_API_KEY") or api_type == "groq") and not (self.settings.get("api_base") or os.environ.get("CYGUIDE_API_BASE")):
                        api_base = "https://api.groq.com/openai/v1"
                        api_model = self.settings.get("api_model") or os.environ.get("CYGUIDE_API_MODEL", "llama-3.3-70b-versatile")
                    else:
                        api_base = self.settings.get("api_base") or os.environ.get("CYGUIDE_API_BASE", "https://api.openai.com/v1")
                        api_model = self.settings.get("api_model") or os.environ.get("CYGUIDE_API_MODEL", "gpt-4o")

                    profiles.append(CloudKeyProfile(
                        id="key_1",
                        name="Primary Key",
                        provider=api_type,
                        api_key=api_key,
                        model=api_model,
                        base_url=api_base,
                        enabled=True,
                    ))

            if profiles:
                ollama_fallback = OllamaBackend(model=self.ollama_model, base_url=ollama_base_url)
                self.explainer_backend = MultiKeyCloudBackend(
                    profiles=profiles,
                    active_key_id=getattr(self, "active_key_id", None),
                    fallback_to_ollama=True,
                    ollama_backend=ollama_fallback,
                )
            else:
                self.explainer_backend = OllamaBackend(model=self.ollama_model, base_url=ollama_base_url)

        self.explainer = LearningExplainer(self.explainer_backend)
        if hasattr(self, "learning_engine") and self.learning_engine is not None:
            self.learning_engine.explainer = self.explainer

    def reload_registry(self) -> None:
        """Reload the tool registry if tools_dir changed."""
        self.registry = ToolRegistry(tools_dir=self.tools_dir)
        self.registry.load_tools()
        if hasattr(self, "learning_engine") and self.learning_engine is not None:
            self.learning_engine.registry = self.registry
        if hasattr(self, "power_facade") and self.power_facade is not None:
            self.power_facade.registry = self.registry
        self._async_refresh_tool_health_cache()

    async def on_unmount(self) -> None:
        """Cleanup resources before exit."""
        if hasattr(self, "power_facade") and self.power_facade is not None:
            await self.power_facade.shutdown()
        if hasattr(self, "executor") and self.executor is not None:
            await self.executor.shutdown()
        if hasattr(self, "store") and self.store is not None:
            await self.store.close()

    def action_toggle_animations(self) -> None:
        """Toggle UI animations on or off via the command palette."""
        self.animations_enabled = not self.animations_enabled
        self._save_settings({"animations_enabled": self.animations_enabled})
        if self.animations_enabled:
            self.remove_class("no-animations")
            self.notify("Animations Enabled")
        else:
            self.add_class("no-animations")
            self.notify("Animations Disabled")

    def action_command_palette(self, preserve_highlight: bool = False) -> None:
        """Show the custom CyGuide command palette with left/right arrow sub-menu navigation."""
        self.check_and_update_tool_health()
        self._navigating_sub_palette = False
        if not preserve_highlight:
            self.last_palette_highlight = None
        if self.use_command_palette and not CyGuideCommandPalette.is_open(self):
            self.push_screen(CyGuideCommandPalette(id="--command-palette"))

    def action_show_tool_health(self) -> None:
        """Open the Tool Health & System Status modal."""
        from cyguide.ui.screens.tool_health_modal import ToolHealthModal
        self.last_palette_highlight = None
        self._navigating_sub_palette = False
        self.push_screen(ToolHealthModal())

    def action_show_config(self, focus_target: Optional[str] = None) -> None:
        """Open the Configuration modal dialog."""
        from cyguide.ui.screens.config_modal import ConfigModal
        self.last_palette_highlight = None
        self._navigating_sub_palette = False
        self.push_screen(ConfigModal(focus_target=focus_target))

    async def switch_database(self, new_db_path: str) -> None:
        """Safely switch to a new database file, migrating schemas and rebinding engines."""
        if not new_db_path:
            return
        if getattr(self, "db_path", None) == new_db_path and getattr(self, "store", None) is not None:
            return

        old_path = getattr(self, "db_path", None)
        old_store = getattr(self, "store", None)

        try:
            if new_db_path != ":memory:":
                db_dir = os.path.dirname(os.path.abspath(new_db_path))
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)

            new_store = GraphStore(new_db_path)
            await new_store.initialize()
            new_ws_id, new_session_id = await new_store.get_or_create_learning_sandbox()

            if old_store:
                try:
                    await old_store.close()
                except Exception:
                    pass

            self.db_path = new_db_path
            self.store = new_store
            self.learning_ws_id = new_ws_id
            self.learning_session_id = new_session_id

            if hasattr(self, "recommendation_engine") and self.recommendation_engine:
                self.recommendation_engine.store = self.store
                self.store.on_upsert(self.recommendation_engine.handle_upsert)

            if hasattr(self, "executor") and self.executor:
                self.executor.store = self.store

            if hasattr(self, "power_facade") and self.power_facade:
                self.power_facade.store = self.store

            self._save_settings({"db_path": new_db_path})
        except Exception as e:
            if old_store:
                self.store = old_store
                self.db_path = old_path
            raise e

    def action_show_config_palette(self) -> None:
        """Open the Configuration modal dialog directly."""
        self.action_show_config()

    def action_show_ollama_palette(self) -> None:
        """Open the Configuration modal dialog focused on Ollama."""
        self.action_show_config(focus_target="ollama")

    def action_show_cloud_api_palette(self) -> None:
        """Open the Configuration modal dialog focused on Cloud API."""
        self.action_show_config(focus_target="api_key")

    def action_show_database_palette(self) -> None:
        """Open the Configuration modal dialog focused on Database."""
        self.action_show_config(focus_target="db_path")

    def action_show_exports_palette(self) -> None:
        """Open the Configuration modal dialog focused on Session Exports Directory."""
        self.action_show_config(focus_target="exports_dir")

    def action_show_reports_palette(self) -> None:
        """Open the Configuration modal dialog focused on Markdown Reports Directory."""
        self.action_show_config(focus_target="reports_dir")

    def action_show_tools_palette(self) -> None:
        """Open the Configuration modal dialog focused on Tools."""
        self.action_show_config(focus_target="tools_dir")

    def action_toggle_ollama(self) -> None:
        """Toggle local Ollama LLM mode on or off."""
        self.use_ollama = not self.use_ollama
        self._save_settings({"use_ollama": self.use_ollama})
        self.reload_explainer()
        status = "Enabled" if self.use_ollama else "Disabled (Cloud API / Fallback)"
        self.notify(f"Ollama Mode {status}", title="Ollama Config")

    def action_toggle_cloud_api(self) -> None:
        """Toggle cloud AI access on or off."""
        self.use_cloud_api = not getattr(self, "use_cloud_api", True)
        self._save_settings({"use_cloud_api": self.use_cloud_api})
        self.reload_explainer()
        status = "Enabled" if self.use_cloud_api else "Disabled (Local Ollama Only)"
        self.notify(f"Cloud AI Access {status}", title="Cloud AI Config")

    def action_reset_config_defaults(self) -> None:
        """Reset configuration to initial defaults while preserving saved Cloud AI keys."""
        self.use_ollama = False
        self.use_cloud_api = True
        self.ollama_model = "gemma"
        default_db = get_default_db_path(getattr(self, "data_dir", None))
        self.db_path = default_db
        self.tools_dir = None
        self.exports_dir = None
        self.reports_dir = None
        # Preserve user's configured cloud keys
        existing_keys = list(self.cloud_keys) if hasattr(self, "cloud_keys") and self.cloud_keys is not None else []
        existing_active = self.active_key_id
        self._save_settings({
            "use_ollama": False,
            "use_cloud_api": True,
            "ollama_model": "gemma",
            "ollama_base_url": "http://localhost:11434",
            "cloud_keys": existing_keys,
            "active_key_id": existing_active,
            "db_path": default_db,
            "tools_dir": None,
            "exports_dir": None,
            "reports_dir": None,
        })
        self.reload_explainer()
        self.reload_registry()
        self.notify("Configuration reset to CLI defaults (API keys preserved)", title="Config Reset")

    def search_themes(self) -> None:
        """Show the theme selection palette with unified left/right arrow navigation."""
        from textual.theme import ThemeProvider
        self.last_palette_highlight = "Theme"
        self.push_screen(
            CyGuideCommandPalette(
                providers=[ThemeProvider],
                placeholder="Search for themes…",
                is_sub_palette=True,
                id="--command-palette-theme",
            )
        )

    def action_show_hotkeys(self) -> None:
        """Open the F1 Shortcuts / Help dialog."""
        from cyguide.ui.screens.power import ShortcutsDialog
        self.push_screen(ShortcutsDialog())

    def action_show_help_panel(self) -> None:
        """Override Textual's default half-screen help panel with CyGuide's polished F1 Shortcuts dialog."""
        self.action_show_hotkeys()

    def get_system_commands(self, screen):
        """Add custom commands to the Command Palette (Ctrl+P) in conventional menu order."""

        # Collect base system commands from super()
        base_cmds = {}
        for cmd in super().get_system_commands(screen):
            base_cmds[cmd.title.lower()] = cmd

        # 1. Screen / View Toggles
        anim_badge = "[bold green]● ON[/bold green]" if self.animations_enabled else "[dim]⊘ OFF[/dim]"
        yield SystemCommand(
            f"Toggle Animations  {anim_badge}",
            "",
            self.action_toggle_animations
        )

        # 2. Tool Diagnostics / Health
        health = self.check_and_update_tool_health()
        total = len(health)
        issues = [info for info in health.values() if not info.get("healthy", False)]
        ok_count = total - len(issues)
        if total == 0:
            health_badge = "[#34d399]● Ready[/]"
        elif not issues:
            health_badge = f"[bold green]● Healthy ({ok_count}/{total})[/bold green]"
        else:
            health_badge = f"[bold red]▲ {len(issues)} Issue{'s' if len(issues) > 1 else ''}[/bold red]"

        yield SystemCommand(
            f"Tool Health  {health_badge}",
            "",
            self.action_show_tool_health
        )

        # 3. Settings & Configuration (opens full config panel directly)
        yield SystemCommand(
            "Config",
            "",
            self.action_show_config,
        )

        # 4. Theme
        if "theme" in base_cmds:
            cmd = base_cmds["theme"]
            yield SystemCommand(cmd.title, "", cmd.callback, cmd.discover)

        # 5. Hotkeys
        yield SystemCommand(
            "Hotkeys",
            "",
            self.action_show_hotkeys
        )

        # 6. Utilities
        if "screenshot" in base_cmds:
            cmd = base_cmds["screenshot"]
            yield SystemCommand(cmd.title, "", cmd.callback, cmd.discover)

        # 7. Exit (Conventional menu order: Quit is always the last option)
        if "quit" in base_cmds:
            cmd = base_cmds["quit"]
            yield SystemCommand(cmd.title, "", cmd.callback, cmd.discover)
        else:
            yield SystemCommand("Quit", "", self.action_quit)

if __name__ == "__main__":
    app = CyGuideApp()
    app.run()
