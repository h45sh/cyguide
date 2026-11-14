"""Configuration modal dialog and Command Palette providers for CyGuide."""

import asyncio
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from textual import events, work
from textual.app import ComposeResult
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Switch, Tab, TabbedContent, TabPane, Tabs

from cyguide.engine.explainer import is_placeholder_key
from cyguide.paths import get_default_db_path, get_default_exports_dir, get_default_reports_dir

PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-20241022",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-1.5-pro",
    },
}


def normalize_and_validate_db_path(
    raw_path: str, data_dir: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """Normalize SQLite DB path and check directory / permission edge cases.

    Returns:
        Tuple of (normalized_path, error_message_or_None)
    """
    raw = (raw_path or "").strip()
    if not raw:
        return get_default_db_path(data_dir), None
    if raw == ":memory:":
        return ":memory:", None

    expanded = os.path.abspath(os.path.expanduser(raw))
    # If the user supplied a directory path, automatically place cyguide.db inside it
    if os.path.isdir(expanded) or raw.endswith("/") or raw.endswith("\\"):
        resolved = os.path.join(raw.rstrip("/\\"), "cyguide.db")
        expanded = os.path.abspath(os.path.expanduser(resolved))
    else:
        resolved = raw

    parent_dir = os.path.dirname(expanded)
    try:
        os.makedirs(parent_dir, exist_ok=True)
        if not os.access(parent_dir, os.W_OK):
            return resolved, f"Directory is not writable: {parent_dir}"
    except Exception as e:
        return resolved, f"Invalid database directory: {e}"

    return resolved, None


def normalize_and_validate_tools_dir(
    raw_path: str, create_if_missing: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize and validate custom tools directory path.

    Returns:
        Tuple of (tools_dir_or_None, error_message_or_None)
    """
    raw = (raw_path or "").strip()
    if not raw:
        return None, None
    expanded = os.path.abspath(os.path.expanduser(raw))
    if os.path.exists(expanded) and not os.path.isdir(expanded):
        return raw, f"Tools path is not a directory: {raw}"
    if not os.path.exists(expanded):
        if create_if_missing:
            try:
                os.makedirs(expanded, exist_ok=True)
            except Exception as e:
                return raw, f"Cannot create tools directory: {e}"
        else:
            return raw, f"Tools directory does not exist: {raw}"
    return raw, None


def normalize_and_validate_export_dir(
    raw_path: str, create_if_missing: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize and validate session exports directory path.

    Returns:
        Tuple of (exports_dir_or_None, error_message_or_None)
    """
    raw = (raw_path or "").strip()
    if not raw:
        return None, None
    expanded = os.path.abspath(os.path.expanduser(raw))
    if os.path.exists(expanded) and not os.path.isdir(expanded):
        return raw, f"Exports path is not a directory: {raw}"
    if not os.path.exists(expanded):
        if create_if_missing:
            try:
                os.makedirs(expanded, mode=0o700, exist_ok=True)
            except Exception as e:
                return raw, f"Cannot create exports directory: {e}"
        else:
            return raw, f"Exports directory does not exist: {raw}"
    return expanded, None


def normalize_and_validate_report_dir(
    raw_path: str, create_if_missing: bool = False
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize and validate markdown reports directory path.

    Returns:
        Tuple of (reports_dir_or_None, error_message_or_None)
    """
    raw = (raw_path or "").strip()
    if not raw:
        return None, None
    expanded = os.path.abspath(os.path.expanduser(raw))
    if os.path.exists(expanded) and not os.path.isdir(expanded):
        return raw, f"Reports path is not a directory: {raw}"
    if not os.path.exists(expanded):
        if create_if_missing:
            try:
                os.makedirs(expanded, mode=0o700, exist_ok=True)
            except Exception as e:
                return raw, f"Cannot create reports directory: {e}"
        else:
            return raw, f"Reports directory does not exist: {raw}"
    return expanded, None


def normalize_ollama_url(raw_url: str) -> str:
    """Normalize Ollama base URL ensuring protocol and stripped trailing slashes."""
    url = (raw_url or "http://localhost:11434").strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}"
    return url


async def check_ollama_status(base_url: str, model: str) -> Tuple[bool, str]:
    """Probe Ollama server tags endpoint to verify connectivity and model readiness."""
    clean_url = normalize_ollama_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{clean_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "").split(":")[0].lower() for m in data.get("models", [])]
                installed_full = [m.get("name", "").lower() for m in data.get("models", [])]
                target = (model or "gemma").strip().lower()
                target_base = target.split(":")[0]
                if (
                    target in installed_full
                    or target_base in models
                    or any(target_base in m for m in models)
                ):
                    return True, f"● Ollama Online · Model '{model}' ready"
                else:
                    available = ", ".join(models[:4]) if models else "none"
                    return True, f"▲ Ollama Online · '{model}' not found (Installed: {available})"
            else:
                return False, f"▲ Ollama returned HTTP {resp.status_code}"
    except Exception:
        return False, f"▲ Ollama Offline (Cannot connect to {clean_url})"


class ConfigProvider(Provider):
    """Command Palette provider for CyGuide Configuration.

    Provides direct access to open the full configuration panel or focused settings.
    """

    @property
    def category_commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        use_ollama = getattr(app, "use_ollama", False)
        ollama_status = "[bold green]● ON[/bold green]" if use_ollama else "[dim]⊘ OFF[/dim]"
        settings = getattr(app, "settings", {}) or {}
        has_key = bool(
            any(k.get("api_key") for k in getattr(app, "cloud_keys", []))
            or os.environ.get("CYGUIDE_API_KEY")
        )
        api_status = "[bold green]● Configured[/bold green]" if has_key else "[dim]— Not set[/dim]"

        return [
            (
                "Open Full Configuration Panel  ⚙",
                lambda: app.action_show_config(),
            ),
            (
                f"Ollama (Local LLM)  {ollama_status}",
                lambda: app.action_show_config(focus_target="ollama"),
            ),
            (
                f"API Keys & Cloud AI  {api_status}",
                lambda: app.action_show_config(focus_target="api_key"),
            ),
            (
                "Database Settings",
                lambda: app.action_show_config(focus_target="db_path"),
            ),
            (
                "Tools Directory",
                lambda: app.action_show_config(focus_target="tools_dir"),
            ),
            (
                "Reset Configuration to Defaults",
                lambda: app.action_reset_config_defaults(),
            ),
        ]

    @property
    def deep_search_commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        ollama_model = getattr(app, "ollama_model", "gemma") or "gemma"
        settings = getattr(app, "settings", {}) or {}
        api_model = settings.get("api_model") or os.environ.get("CYGUIDE_API_MODEL", "gpt-4o")
        db_path = getattr(app, "db_path", None) or get_default_db_path()
        tools_dir = getattr(app, "tools_dir", None) or "bundled tools/"
        exports_dir = getattr(app, "exports_dir", None) or (
            app.get_exports_dir() if hasattr(app, "get_exports_dir") else get_default_exports_dir()
        )
        reports_dir = getattr(app, "reports_dir", None) or (
            app.get_reports_dir() if hasattr(app, "get_reports_dir") else get_default_reports_dir()
        )

        return [
            *self.category_commands,
            (
                f"Ollama Model: {ollama_model}",
                lambda: app.action_show_config(focus_target="ollama_model"),
            ),
            (
                f"Cloud API Model: {api_model}",
                lambda: app.action_show_config(focus_target="api_model"),
            ),
            (f"Database Path: {db_path}", lambda: app.action_show_config(focus_target="db_path")),
            (
                f"Session Exports Directory: {exports_dir}",
                lambda: app.action_show_config(focus_target="exports_dir"),
            ),
            (
                f"Markdown Reports Directory: {reports_dir}",
                lambda: app.action_show_config(focus_target="reports_dir"),
            ),
            (
                f"Tools Directory: {tools_dir}",
                lambda: app.action_show_config(focus_target="tools_dir"),
            ),
        ]

    async def discover(self) -> Hits:
        for name, callback in self.category_commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.deep_search_commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)


class OllamaConfigProvider(Provider):
    """Sub-palette provider for local Ollama configuration."""

    @property
    def commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        use_ollama = getattr(app, "use_ollama", False)
        ollama_status = "[bold green]● ON[/bold green]" if use_ollama else "[dim]⊘ OFF[/dim]"
        ollama_model = getattr(app, "ollama_model", "gemma") or "gemma"
        settings = getattr(app, "settings", {}) or {}
        ollama_base_url = settings.get("ollama_base_url", "http://localhost:11434")

        return [
            (
                f"Toggle Local LLM  {ollama_status}",
                lambda: app.action_toggle_ollama(),
            ),
            (
                f"Ollama Model  [cyan]{ollama_model}[/cyan]",
                lambda: app.action_show_config(focus_target="ollama_model"),
            ),
            (
                f"Ollama Base URL  [dim]{ollama_base_url}[/dim]",
                lambda: app.action_show_config(focus_target="ollama_base_url"),
            ),
            (
                "Open Configuration Panel  ⚙",
                lambda: app.action_show_config(focus_target="ollama"),
            ),
        ]

    async def discover(self) -> Hits:
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)


class CloudAPIConfigProvider(Provider):
    """Sub-palette provider for Cloud AI and API key configuration."""

    @property
    def commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        settings = getattr(app, "settings", {}) or {}
        api_type = settings.get("api_type") or os.environ.get("CYGUIDE_API_TYPE", "openai")
        raw_key = (
            settings.get("api_key")
            or os.environ.get("CYGUIDE_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or ""
        )
        masked_key = (
            f"{raw_key[:4]}...{raw_key[-4:]}"
            if len(raw_key) > 8
            else ("Set" if raw_key else "Not set")
        )
        api_model = settings.get("api_model") or os.environ.get("CYGUIDE_API_MODEL", "gpt-4o")
        api_base = settings.get("api_base") or os.environ.get(
            "CYGUIDE_API_BASE", "https://api.openai.com/v1"
        )

        cmds: List[Tuple[str, Callable[[], None]]] = []

        use_cloud = getattr(app, "use_cloud_api", True)
        cloud_status = "[bold green]● ON[/bold green]" if use_cloud else "[dim]⊘ OFF[/dim]"
        cmds.append(
            (
                f"Toggle Cloud AI Access  {cloud_status}",
                lambda: app.action_toggle_cloud_api(),
            )
        )

        # If multiple keys are configured, provide quick key switching options
        cloud_keys = getattr(app, "cloud_keys", [])
        active_id = getattr(app, "active_key_id", None)
        if len(cloud_keys) > 1:
            for k in cloud_keys:
                k_id = k.get("id")
                k_name = k.get("name") or k.get("provider") or k_id
                k_model = k.get("model", "")
                is_active = k_id == active_id
                status_badge = (
                    "[bold green]● Active[/bold green]" if is_active else "[dim]▪ Switch[/dim]"
                )
                label = (
                    f"Switch Active Key: {k_name} ({k_model})  {status_badge}"
                    if k_model
                    else f"Switch Active Key: {k_name}  {status_badge}"
                )
                cmds.append((label, lambda kid=k_id: app.action_switch_active_key(kid)))

        cmds.extend(
            [
                (
                    f"API Key  [dim]{masked_key}[/dim]",
                    lambda: app.action_show_config(focus_target="api_key"),
                ),
                (
                    f"Provider Type  [cyan]{api_type}[/cyan]",
                    lambda: app.action_show_config(focus_target="api_type"),
                ),
                (
                    f"Cloud Model  [cyan]{api_model}[/cyan]",
                    lambda: app.action_show_config(focus_target="api_model"),
                ),
                (
                    f"API Base URL  [dim]{api_base}[/dim]",
                    lambda: app.action_show_config(focus_target="api_base"),
                ),
                (
                    "Open Configuration Panel  ⚙",
                    lambda: app.action_show_config(focus_target="api"),
                ),
            ]
        )
        return cmds

    async def discover(self) -> Hits:
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)


class DatabaseConfigProvider(Provider):
    """Sub-palette provider for Database configuration."""

    @property
    def commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        db_path = getattr(app, "db_path", None) or get_default_db_path()
        exports_dir = getattr(app, "exports_dir", None) or (
            app.get_exports_dir() if hasattr(app, "get_exports_dir") else get_default_exports_dir()
        )
        reports_dir = getattr(app, "reports_dir", None) or (
            app.get_reports_dir() if hasattr(app, "get_reports_dir") else get_default_reports_dir()
        )

        return [
            (
                f"Database Path  [dim]{db_path}[/dim]",
                lambda: app.action_show_config(focus_target="db_path"),
            ),
            (
                f"Session Exports Directory  [dim]{exports_dir}[/dim]",
                lambda: app.action_show_config(focus_target="exports_dir"),
            ),
            (
                f"Markdown Reports Directory  [dim]{reports_dir}[/dim]",
                lambda: app.action_show_config(focus_target="reports_dir"),
            ),
            (
                "Open Configuration Panel  ⚙",
                lambda: app.action_show_config(focus_target="db_path"),
            ),
        ]

    async def discover(self) -> Hits:
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)


class ToolsConfigProvider(Provider):
    """Sub-palette provider for Tools directory configuration."""

    @property
    def commands(self) -> List[Tuple[str, Callable[[], None]]]:
        app = self.app
        tools_dir = getattr(app, "tools_dir", None) or "bundled tools/"

        return [
            (
                f"Tools Directory Path  [dim]{tools_dir}[/dim]",
                lambda: app.action_show_config(focus_target="tools_dir"),
            ),
            (
                "Open Configuration Panel  ⚙",
                lambda: app.action_show_config(focus_target="tools_dir"),
            ),
        ]

    async def discover(self) -> Hits:
        for name, callback in self.commands:
            yield DiscoveryHit(name, callback)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback)


class ConfigModal(ModalScreen[None]):
    """Modal dialog displaying and editing all CyGuide configuration options."""

    BINDINGS = [
        ("escape", "dismiss_modal", "Close"),
        ("q", "dismiss_modal", "Close"),
        ("pageup", "prev_tab", "Prev Tab"),
        ("pagedown", "next_tab", "Next Tab"),
        ("f2", "goto_tab('tab_ollama')", "Ollama"),
        ("f3", "goto_tab('tab_cloud')", "Cloud AI"),
        ("f4", "goto_tab('tab_db')", "Database"),
        ("f5", "goto_tab('tab_tools')", "Tools"),
    ]

    def __init__(self, focus_target: Optional[str] = None):
        super().__init__()
        self.focus_target = focus_target
        self.cloud_keys: List[Dict[str, Any]] = []
        self.active_key_id: Optional[str] = None
        self.editing_profile_id: Optional[str] = None
        self.is_dirty: bool = False

    def action_dismiss_modal(self) -> None:
        self.dismiss()

    def action_prev_tab(self) -> None:
        tabs = self.query_one("#config_tabs", TabbedContent)
        tab_ids = ["tab_ollama", "tab_cloud", "tab_db", "tab_tools"]
        curr = tabs.active
        if curr in tab_ids:
            idx = tab_ids.index(curr)
            tabs.active = tab_ids[(idx - 1) % len(tab_ids)]
            self._update_test_button_label(tabs.active)

    def action_next_tab(self) -> None:
        tabs = self.query_one("#config_tabs", TabbedContent)
        tab_ids = ["tab_ollama", "tab_cloud", "tab_db", "tab_tools"]
        curr = tabs.active
        if curr in tab_ids:
            idx = tab_ids.index(curr)
            tabs.active = tab_ids[(idx + 1) % len(tab_ids)]
            self._update_test_button_label(tabs.active)

    def action_goto_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#config_tabs", TabbedContent)
        tabs.active = tab_id
        self._update_test_button_label(tab_id)

    def _get_active_profile_dict(self) -> Optional[Dict[str, Any]]:
        if not self.cloud_keys:
            return None
        for k in self.cloud_keys:
            if k.get("id") == self.active_key_id:
                return k
        return self.cloud_keys[0]

    def _get_editing_profile_dict(self) -> Optional[Dict[str, Any]]:
        if not self.cloud_keys:
            return None
        if self.editing_profile_id:
            for k in self.cloud_keys:
                if k.get("id") == self.editing_profile_id:
                    return k
        return self._get_active_profile_dict()

    def _build_key_card(self, k: Dict[str, Any]) -> Vertical:
        kid = k.get("id", "")
        kname = k.get("name") or k.get("provider") or kid
        kprov = k.get("provider") or "custom"
        kmodel = k.get("model") or "default model"
        raw_key = (k.get("api_key") or "").strip().strip("\"'")
        is_active = kid == self.active_key_id
        is_editing = kid == self.editing_profile_id
        enabled = k.get("enabled", True)

        if not raw_key or is_placeholder_key(raw_key):
            status_text = "[bold yellow]▲ No Key[/bold yellow]"
        elif is_active:
            status_text = "[bold green]● Active[/bold green]"
        else:
            status_text = "[dim]▪ Standby[/dim]"

        fallback_text = (
            "[bold #38bdf8]Fallback: YES[/bold #38bdf8]"
            if enabled
            else "[dim #64748b]Fallback: NO[/dim #64748b]"
        )
        masked = (
            f"{raw_key[:4]}...{raw_key[-4:]}"
            if len(raw_key) > 8
            else ("[dim](no key)[/dim]" if not raw_key else "Configured")
        )

        card_classes = ["cfg_key_card"]
        if is_editing:
            card_classes.append("cfg_key_card_selected")
        if is_active:
            card_classes.append("cfg_key_card_active_key")

        card = Vertical(
            Horizontal(
                Label(status_text, classes="cfg_key_status_pill", id=f"cfg_pill_{kid}"),
                Label(kname, classes="cfg_key_title_text", id=f"cfg_title_{kid}"),
                Label(fallback_text, classes="cfg_key_fallback_pill", id=f"cfg_fallback_{kid}"),
                classes="cfg_key_card_row_info",
            ),
            Horizontal(
                Label(f"{kprov} · {kmodel}", classes="cfg_key_meta_text", id=f"cfg_meta_{kid}"),
                Label(masked, classes="cfg_key_masked_text", id=f"cfg_masked_{kid}"),
                classes="cfg_key_card_row_meta",
            ),
            Horizontal(
                Button(
                    "✎ Edit",
                    id=f"cfg_edit_key_{kid}",
                    classes="cfg_key_action_btn cfg_key_edit_btn",
                ),
                Button(
                    "★ Set Active",
                    id=f"cfg_activate_key_{kid}",
                    classes="cfg_key_action_btn cfg_key_activate_btn",
                    disabled=is_active,
                ),
                Button(
                    "✕ Delete",
                    id=f"cfg_delete_key_{kid}",
                    classes="cfg_key_action_btn cfg_key_delete_btn",
                ),
                classes="cfg_key_card_row_actions",
            ),
            classes=" ".join(card_classes),
            id=f"cfg_card_{kid}",
        )
        return card

    def _build_key_list_widgets(self) -> List[Any]:
        if not self.cloud_keys:
            return [
                Label(
                    "▪ No API key profiles configured yet. Click '+ Add Key Profile' to configure a cloud provider or use Local Ollama.",
                    id="cfg_empty_keys_msg",
                    classes="cfg_empty_keys_msg",
                )
            ]
        return [self._build_key_card(k) for k in self.cloud_keys]

    def _get_select_options(self) -> List[Tuple[str, str]]:
        if not self.cloud_keys:
            return [("No Key Profiles (Click + Add to create)", "__new__")]
        options = []
        for k in self.cloud_keys:
            kid = k.get("id", "")
            kname = k.get("name") or k.get("provider") or kid
            kmodel = k.get("model", "")
            raw_key = k.get("api_key", "").strip().strip("\"'")
            is_active = kid == self.active_key_id
            if not raw_key or is_placeholder_key(raw_key):
                tag = "▲ [Missing Key]"
            elif is_active:
                tag = "● [Active]"
            else:
                tag = "▪ [Standby]"
            label = f"{tag} {kname} ({kmodel})" if kmodel else f"{tag} {kname}"
            options.append((label, kid))
        return options

    def compose(self) -> ComposeResult:
        app = self.app
        settings = getattr(app, "settings", {}) or {}
        use_ollama = getattr(app, "use_ollama", False)
        ollama_model = getattr(app, "ollama_model", "gemma") or "gemma"
        ollama_base_url = settings.get("ollama_base_url", "http://localhost:11434")

        # Load cloud keys and active key
        raw_cloud_keys = getattr(app, "cloud_keys", None)
        if raw_cloud_keys is not None:
            self.cloud_keys = [dict(k) for k in raw_cloud_keys]
            for k in self.cloud_keys:
                if is_placeholder_key(k.get("api_key")):
                    k["api_key"] = ""
        else:
            self.cloud_keys = []

        self.active_key_id = getattr(app, "active_key_id", None)

        if self.cloud_keys:
            if not self.active_key_id or not any(
                k.get("id") == self.active_key_id for k in self.cloud_keys
            ):
                self.active_key_id = self.cloud_keys[0].get("id")
        else:
            self.active_key_id = None

        self.editing_profile_id = self.active_key_id or (
            self.cloud_keys[0]["id"] if self.cloud_keys else None
        )
        self._current_loaded_profile_id: Optional[str] = self.editing_profile_id
        cur_prof = self._get_editing_profile_dict()
        # By default keep fields empty if not configured!
        api_type = cur_prof.get("provider", "") if cur_prof else ""
        api_key = cur_prof.get("api_key", "") if cur_prof else ""
        api_model = cur_prof.get("model", "") if cur_prof else ""
        api_base = cur_prof.get("base_url", "") if cur_prof else ""
        key_name = cur_prof.get("name", "") if cur_prof else ""
        key_enabled = cur_prof.get("enabled", True) if cur_prof else True

        db_path = getattr(app, "db_path", None) or get_default_db_path(
            getattr(app, "data_dir", None)
        )
        default_db_placeholder = get_default_db_path(getattr(app, "data_dir", None))
        tools_dir = getattr(app, "tools_dir", "") or ""
        exports_dir = getattr(app, "exports_dir", "") or ""
        default_exports_placeholder = getattr(
            app, "get_exports_dir", lambda: get_default_exports_dir(getattr(app, "data_dir", None))
        )()
        reports_dir = getattr(app, "reports_dir", "") or ""
        default_reports_placeholder = getattr(
            app, "get_reports_dir", lambda: get_default_reports_dir(getattr(app, "data_dir", None))
        )()

        with Vertical(id="config_card"):
            with Horizontal(id="config_header_row"):
                yield Label("◆ CYGUIDE CONFIGURATION", id="config_header_title")
                yield Label("[Esc] Close  ·  [PgUp/PgDn] Tabs", id="config_nav_hint")

            yield Label(self._get_active_status_text(), id="config_status_label")
            yield Label("", id="config_feedback_banner")

            with TabbedContent(id="config_tabs"):
                with TabPane("Local LLM (Ollama)", id="tab_ollama"):
                    yield Label(
                        self._get_ollama_quick_status(ollama_base_url, ollama_model),
                        id="cfg_ollama_status_msg",
                        classes="config_tab_banner",
                    )

                    with Horizontal(classes="config_switch_row"):
                        yield Label("Enable Local Ollama:", classes="config_switch_label")
                        yield Switch(value=use_ollama, id="cfg_use_ollama")
                        badge_text = (
                            "[bold green]● ON[/bold green]" if use_ollama else "[dim]⊘ OFF[/dim]"
                        )
                        yield Label(badge_text, id="cfg_ollama_switch_badge")

                    yield Label("Model Name [--model]:", classes="config_field_label")
                    yield Input(
                        value=ollama_model,
                        placeholder="e.g. gemma, llama3, mistral",
                        id="cfg_ollama_model",
                    )

                    yield Label("Base URL:", classes="config_field_label")
                    yield Input(
                        value=ollama_base_url,
                        placeholder="http://localhost:11434",
                        id="cfg_ollama_base_url",
                    )

                with TabPane("Cloud AI", id="tab_cloud"):
                    yield Label(
                        self._get_cloud_quick_status(api_key, api_type, api_model),
                        id="cfg_cloud_status_msg",
                        classes="config_tab_banner",
                    )

                    use_cloud_api = getattr(app, "use_cloud_api", True)
                    with Horizontal(classes="config_switch_row"):
                        yield Label("Enable Cloud AI Access:", classes="config_switch_label")
                        yield Switch(value=use_cloud_api, id="cfg_use_cloud_api")
                        cloud_badge_text = (
                            "[bold green]● ON[/bold green]" if use_cloud_api else "[dim]⊘ OFF[/dim]"
                        )
                        yield Label(cloud_badge_text, id="cfg_cloud_switch_badge")

                    # View 1: Keys List View (Visible by default)
                    with Vertical(id="cfg_cloud_list_view"):
                        # Key Profiles Toolbar Header (Title + Add Key)
                        with Horizontal(classes="cfg_section_header", id="cfg_key_bar"):
                            yield Label(
                                f"Configured Keys ({len(self.cloud_keys)}):",
                                classes="cfg_section_title",
                                id="cfg_keys_title_lbl",
                            )
                            yield Button(
                                "+ Add Key", id="cfg_key_add_btn", classes="key_action_btn"
                            )

                        # List of API key profile cards
                        with Vertical(id="cfg_keys_list"):
                            for w in self._build_key_list_widgets():
                                yield w

                    # View 2: Key Editor View (Hidden by default, opened by Edit or + Add Key)
                    with Vertical(id="cfg_key_editor", classes="hidden"):
                        yield Label("✎ Edit Key Profile", id="cfg_editor_title")

                        yield Label("Profile Label / Name:", classes="config_field_label")
                        yield Input(
                            value=key_name,
                            placeholder="e.g. Primary OpenAI, Groq Backup, Claude Work",
                            id="cfg_key_name",
                        )

                        yield Label("Provider [CYGUIDE_API_TYPE]:", classes="config_field_label")
                        yield Input(
                            value=api_type,
                            placeholder="openai, groq, anthropic, openrouter (or leave blank)",
                            id="cfg_api_type",
                        )

                        yield Label("API Key [CYGUIDE_API_KEY]:", classes="config_field_label")
                        yield Input(
                            value=api_key,
                            password=True,
                            placeholder="API key (leave blank to clear / use local LLM)",
                            id="cfg_api_key",
                        )

                        yield Label("Model [CYGUIDE_API_MODEL]:", classes="config_field_label")
                        yield Input(
                            value=api_model,
                            placeholder="e.g. gpt-4o, llama-3.3-70b-versatile, claude-3-5-sonnet",
                            id="cfg_api_model",
                        )

                        yield Label("Base URL [CYGUIDE_API_BASE]:", classes="config_field_label")
                        yield Input(
                            value=api_base,
                            placeholder="e.g. https://api.openai.com/v1",
                            id="cfg_api_base",
                        )

                        with Horizontal(classes="config_switch_row", id="cfg_editor_switch_row"):
                            yield Label("Include in Fallback Chain:", classes="config_switch_label")
                            yield Switch(value=key_enabled, id="cfg_key_enabled")
                            badge_txt = (
                                "[bold green]● YES[/bold green]"
                                if key_enabled
                                else "[dim]⊘ NO[/dim]"
                            )
                            yield Label(badge_txt, id="cfg_key_enabled_badge")

                        with Horizontal(id="cfg_editor_footer_row"):
                            yield Button(
                                "✓ Save & Back",
                                id="cfg_editor_save_btn",
                                classes="key_action_btn cfg_editor_save_btn",
                            )
                            yield Button(
                                "← Back",
                                id="cfg_editor_cancel_btn",
                                classes="key_action_btn cfg_editor_cancel_btn",
                            )
                            yield Button(
                                "✕ Delete",
                                id="cfg_key_del_btn",
                                classes="key_action_btn cfg_key_delete_btn",
                            )

                with TabPane("Database", id="tab_db"):
                    yield Label(
                        self._get_db_quick_status(db_path),
                        id="cfg_db_status_msg",
                        classes="config_tab_banner",
                    )
                    yield Label("SQLite Database Path [--db]:", classes="config_field_label")
                    yield Input(value=db_path, placeholder=default_db_placeholder, id="cfg_db_path")

                    yield Label("Session Exports Directory Path:", classes="config_field_label")
                    yield Input(
                        value=exports_dir,
                        placeholder=default_exports_placeholder,
                        id="cfg_exports_dir",
                    )

                    yield Label("Markdown Reports Directory Path:", classes="config_field_label")
                    yield Input(
                        value=reports_dir,
                        placeholder=default_reports_placeholder,
                        id="cfg_reports_dir",
                    )

                with TabPane("Tools", id="tab_tools"):
                    yield Label(
                        self._get_tools_quick_status(tools_dir),
                        id="cfg_tools_status_msg",
                        classes="config_tab_banner",
                    )
                    yield Label("Custom Tools Directory [--tools]:", classes="config_field_label")
                    yield Input(
                        value=tools_dir,
                        placeholder="bundled tools/ (leave blank for default)",
                        id="cfg_tools_dir",
                    )

            with Horizontal(classes="dialog_buttons", id="config_btn_row"):
                yield Button("Save & Apply", variant="primary", id="cfg_save_btn")
                yield Button("Close", variant="default", id="cfg_close_btn")
                yield Button("Test Ollama", variant="default", id="cfg_test_btn")
                yield Button("Reset Defaults", variant="default", id="cfg_reset_btn")

    def _get_active_status_text(self) -> str:
        app = self.app
        use_ollama = getattr(app, "use_ollama", False)
        try:
            use_ollama = self.query_one("#cfg_use_ollama", Switch).value
        except Exception:
            pass

        use_cloud_api = getattr(app, "use_cloud_api", True)
        try:
            use_cloud_api = self.query_one("#cfg_use_cloud_api", Switch).value
        except Exception:
            pass

        if use_ollama:
            return "● Active Engine: Local Ollama"

        if not use_cloud_api:
            return "◆ Active Engine: Local Ollama (Cloud AI Access Disabled)"

        keys = getattr(self, "cloud_keys", None)
        if keys is None:
            keys = getattr(app, "cloud_keys", [])

        valid_keys = [
            k for k in keys if k.get("api_key") and not is_placeholder_key(k.get("api_key"))
        ]
        if valid_keys:
            return "● Active Engine: Cloud AI"

        return "◆ Active Engine: Local Ollama (No Cloud API Key Configured)"

    def _get_ollama_quick_status(self, url: str, model: str) -> str:
        norm_url = normalize_ollama_url(url)
        return f"Endpoint: {norm_url} (target: {model})"

    def _get_cloud_quick_status(self, key: str, provider: str, model: str) -> str:
        if not key or is_placeholder_key(key):
            prof_name = ""
            if getattr(self, "editing_profile_id", None):
                target = next(
                    (
                        k
                        for k in getattr(self, "cloud_keys", [])
                        if k.get("id") == self.editing_profile_id
                    ),
                    None,
                )
                if target:
                    prof_name = target.get("name") or target.get("id")
            if prof_name:
                short_name = prof_name[:20] + "..." if len(prof_name) > 23 else prof_name
                return f"▲ Profile '{short_name}' has no API key · [Credential Missing]"
            return "◆ No Cloud API Key set · Fields empty by default (Local Ollama / Fallback available)"
        masked = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "Configured"
        valid_keys = [
            k
            for k in getattr(self, "cloud_keys", [])
            if k.get("api_key") and not is_placeholder_key(k.get("api_key"))
        ]
        num_keys = len(valid_keys)
        extra = (
            f" (+{num_keys - 1} fallback{'s' if num_keys - 1 > 1 else ''})" if num_keys > 1 else ""
        )
        short_prov = provider[:18] + "..." if len(provider) > 20 else provider
        short_mod = model[:24] + "..." if len(model) > 26 else model
        prov_str = f" · {short_prov}" if short_prov else ""
        mod_str = f" / {short_mod}" if short_mod else ""
        return f"● Key configured ({masked}){prov_str}{mod_str}{extra}"

    def _get_db_quick_status(self, path: str) -> str:
        if path == ":memory:":
            return "● In-Memory Database (:memory:)"
        expanded = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(expanded):
            try:
                size_kb = os.path.getsize(expanded) / 1024
                return f"● Database file exists ({size_kb:.1f} KB)"
            except Exception:
                return "● Database file exists"
        return "◆ Database file will be created on first use"

    def _get_tools_quick_status(self, path: str) -> str:
        reg = getattr(self.app, "registry", None)
        count = len(reg.tools) if reg and hasattr(reg, "tools") else 0
        if not path:
            return f"● Bundled tools active ({count} tools loaded)"
        expanded = os.path.abspath(os.path.expanduser(path))
        if os.path.isdir(expanded):
            return f"● Custom tools folder ({count} tools loaded from {os.path.basename(expanded)})"
        if not os.path.exists(expanded):
            return f"▲ Directory does not exist: {expanded}"
        return f"▲ Path is not a directory: {expanded}"

    def on_mount(self) -> None:
        def apply_focus():
            tabs_map = {
                "ollama": ("tab_ollama", "#cfg_use_ollama"),
                "use_ollama": ("tab_ollama", "#cfg_use_ollama"),
                "ollama_model": ("tab_ollama", "#cfg_ollama_model"),
                "model": (
                    "tab_ollama" if getattr(self.app, "use_ollama", False) else "tab_cloud",
                    "#cfg_ollama_model"
                    if getattr(self.app, "use_ollama", False)
                    else "#cfg_api_model",
                ),
                "ollama_base_url": ("tab_ollama", "#cfg_ollama_base_url"),
                "cloud": ("tab_cloud", "#cfg_use_cloud_api"),
                "use_cloud_api": ("tab_cloud", "#cfg_use_cloud_api"),
                "api": ("tab_cloud", "#cfg_api_key"),
                "api_key": ("tab_cloud", "#cfg_api_key"),
                "api_type": ("tab_cloud", "#cfg_api_type"),
                "api_model": ("tab_cloud", "#cfg_api_model"),
                "api_base": ("tab_cloud", "#cfg_api_base"),
                "db": ("tab_db", "#cfg_db_path"),
                "db_path": ("tab_db", "#cfg_db_path"),
                "exports": ("tab_db", "#cfg_exports_dir"),
                "exports_dir": ("tab_db", "#cfg_exports_dir"),
                "reports": ("tab_db", "#cfg_reports_dir"),
                "reports_dir": ("tab_db", "#cfg_reports_dir"),
                "tools": ("tab_tools", "#cfg_tools_dir"),
                "tools_dir": ("tab_tools", "#cfg_tools_dir"),
            }
            target = tabs_map.get(self.focus_target or "")
            if target:
                tab_id, input_id = target
                try:
                    tabs = self.query_one("#config_tabs", TabbedContent)
                    tabs.active = tab_id
                    if input_id in (
                        "#cfg_api_key",
                        "#cfg_api_type",
                        "#cfg_api_model",
                        "#cfg_api_base",
                        "#cfg_key_name",
                    ):
                        self.switch_cloud_view_sync("editor")
                    self.query_one(input_id).focus()
                    return
                except Exception:
                    pass
            try:
                self.query_one("#cfg_save_btn", Button).focus()
            except Exception:
                pass
            self._update_test_button_label()

        self.call_after_refresh(apply_focus)
        self.run_worker(self.probe_status_async())

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self._update_test_button_label(event.tabbed_content.active)

    def _update_test_button_label(self, active_tab: Optional[str] = None) -> None:
        try:
            if not active_tab:
                tabs = self.query_one("#config_tabs", TabbedContent)
                active_tab = tabs.active
            btn = self.query_one("#cfg_test_btn", Button)
            labels = {
                "tab_ollama": "Test Ollama",
                "tab_cloud": "Test Cloud API",
                "tab_db": "Test Database",
                "tab_tools": "Test Tools Dir",
            }
            btn.label = labels.get(active_tab, "Test Status")
        except Exception:
            pass

    async def probe_status_async(self) -> None:
        """Asynchronously probe live Ollama connection and update UI labels."""
        try:
            url = self.query_one("#cfg_ollama_base_url", Input).value
            model = self.query_one("#cfg_ollama_model", Input).value
            online, msg = await check_ollama_status(url, model)
            lbl = self.query_one("#cfg_ollama_status_msg", Label)
            lbl.update(msg)
            if online and "ready" in msg:
                lbl.remove_class("status_error", "status_warn")
                lbl.add_class("status_ok")
            elif online:
                lbl.remove_class("status_error", "status_ok")
                lbl.add_class("status_warn")
            else:
                lbl.remove_class("status_ok", "status_warn")
                lbl.add_class("status_error")
        except Exception:
            pass

    @work(exclusive=True, group="config_diagnostics")
    async def run_diagnostics(self, target_tab: Optional[str] = None) -> None:
        """Test configuration specific to the currently active tab asynchronously without freezing UI."""
        banner = self.query_one("#config_feedback_banner", Label)
        test_btn = None
        try:
            test_btn = self.query_one("#cfg_test_btn", Button)
            test_btn.loading = True
        except Exception:
            pass

        try:
            if not target_tab:
                try:
                    tabs = self.query_one("#config_tabs", TabbedContent)
                    target_tab = tabs.active
                except Exception:
                    target_tab = "tab_ollama"

            banner.remove_class("banner_error", "banner_ok", "banner_warn")

            if target_tab == "tab_ollama":
                banner.update("Testing Ollama connectivity and model...")
                banner.add_class("banner_info")
                url = self.query_one("#cfg_ollama_base_url", Input).value
                model = self.query_one("#cfg_ollama_model", Input).value
                online, msg = await check_ollama_status(url, model)
                lbl = self.query_one("#cfg_ollama_status_msg", Label)
                lbl.update(msg)
                if online and "ready" in msg:
                    lbl.remove_class("status_error", "status_warn")
                    lbl.add_class("status_ok")
                    banner.update(f"● Ollama online: {msg}")
                    banner.remove_class("banner_info", "banner_error", "banner_warn")
                    banner.add_class("banner_ok")
                elif online:
                    lbl.remove_class("status_error", "status_ok")
                    lbl.add_class("status_warn")
                    banner.update(f"▲ Ready with notice: {msg}")
                    banner.remove_class("banner_info", "banner_error", "banner_ok")
                    banner.add_class("banner_warn")
                else:
                    lbl.remove_class("status_ok", "status_warn")
                    lbl.add_class("status_error")
                    banner.update(f"▲ Issues detected: {msg}")
                    banner.remove_class("banner_info", "banner_ok", "banner_warn")
                    banner.add_class("banner_error")

            elif target_tab == "tab_cloud":
                banner.update("Testing Cloud AI credentials and endpoint...")
                banner.add_class("banner_info")
                active_prof = next(
                    (k for k in self.cloud_keys if k.get("id") == self.active_key_id), None
                )
                is_editor_hidden = False
                try:
                    is_editor_hidden = self.query_one("#cfg_key_editor").has_class("hidden")
                except Exception:
                    pass

                if is_editor_hidden and active_prof:
                    api_key = active_prof.get("api_key", "")
                    api_type = active_prof.get("provider", "")
                    api_model = active_prof.get("model", "")
                    api_base = active_prof.get("base_url", "")
                else:
                    api_key = self.query_one("#cfg_api_key", Input).value
                    api_type = self.query_one("#cfg_api_type", Input).value
                    api_model = self.query_one("#cfg_api_model", Input).value
                    api_base = self.query_one("#cfg_api_base", Input).value
                lbl = self.query_one("#cfg_cloud_status_msg", Label)

                if not api_key:
                    err_msg = "No API key entered. Cloud AI requires an API key or CYGUIDE_API_KEY environment variable."
                    lbl.update(f"▲ {err_msg}")
                    lbl.remove_class("status_ok")
                    lbl.add_class("status_warn")
                    banner.update(f"▲ Ready with notice: {err_msg}")
                    banner.remove_class("banner_info", "banner_error", "banner_ok")
                    banner.add_class("banner_warn")
                else:
                    ok, msg = await self._test_cloud_api(api_key, api_type, api_model, api_base)
                    lbl.update(msg)
                    if ok:
                        lbl.remove_class("status_error", "status_warn")
                        lbl.add_class("status_ok")
                        banner.update(f"● {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_ok")
                    else:
                        lbl.remove_class("status_ok", "status_warn")
                        lbl.add_class("status_error")
                        banner.update(f"▲ Issues detected: {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_error")

            elif target_tab == "tab_db":
                banner.update("Testing Database, exports, and reports paths...")
                banner.add_class("banner_info")
                raw_db = self.query_one("#cfg_db_path", Input).value
                norm_db, db_err = normalize_and_validate_db_path(
                    raw_db, getattr(self.app, "data_dir", None)
                )
                raw_exports = self.query_one("#cfg_exports_dir", Input).value
                norm_exports, exp_err = normalize_and_validate_export_dir(raw_exports)
                raw_reports = self.query_one("#cfg_reports_dir", Input).value
                norm_reports, rep_err = normalize_and_validate_report_dir(raw_reports)
                lbl = self.query_one("#cfg_db_status_msg", Label)
                errs = [e for e in (db_err, exp_err, rep_err) if e]
                if errs:
                    msg = "; ".join(errs)
                    lbl.update(f"▲ {msg}")
                    lbl.remove_class("status_ok", "status_warn")
                    lbl.add_class("status_error")
                    banner.update(f"▲ Issues detected: {msg}")
                    banner.remove_class("banner_info", "banner_error", "banner_warn")
                    banner.add_class("banner_error")
                else:
                    ok, msg = await asyncio.to_thread(self._test_db_writable, norm_db)
                    if ok:
                        lbl.update(msg)
                        lbl.remove_class("status_error", "status_warn")
                        lbl.add_class("status_ok")
                        banner.update(f"● {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_ok")
                    else:
                        lbl.update(f"▲ {msg}")
                        lbl.remove_class("status_ok", "status_warn")
                        lbl.add_class("status_error")
                        banner.update(f"▲ Issues detected: {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_error")

            elif target_tab == "tab_tools":
                banner.update("Testing Custom Tools directory...")
                banner.add_class("banner_info")
                raw_tools = self.query_one("#cfg_tools_dir", Input).value
                norm_tools, tools_err = normalize_and_validate_tools_dir(raw_tools)
                lbl = self.query_one("#cfg_tools_status_msg", Label)
                if tools_err:
                    lbl.update(f"▲ {tools_err}")
                    lbl.remove_class("status_ok", "status_warn")
                    lbl.add_class("status_error")
                    banner.update(f"▲ Issues detected: {tools_err}")
                    banner.remove_class("banner_info", "banner_error", "banner_warn")
                    banner.add_class("banner_error")
                else:
                    ok, msg = await asyncio.to_thread(self._test_tools_directory, norm_tools or "")
                    if ok:
                        lbl.update(msg)
                        lbl.remove_class("status_error", "status_warn")
                        lbl.add_class("status_ok")
                        banner.update(f"● {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_ok")
                    else:
                        lbl.update(f"▲ {msg}")
                        lbl.remove_class("status_ok", "status_warn")
                        lbl.add_class("status_error")
                        banner.update(f"▲ Issues detected: {msg}")
                        banner.remove_class("banner_info", "banner_error", "banner_warn")
                        banner.add_class("banner_error")
        finally:
            if test_btn is not None:
                try:
                    test_btn.loading = False
                    test_btn.disabled = False
                except Exception:
                    pass

    def _test_db_writable(self, path: str) -> Tuple[bool, str]:
        if path == ":memory:":
            return True, "In-memory database (:memory:) is valid and ready."
        expanded = os.path.abspath(os.path.expanduser(path))
        parent = os.path.dirname(expanded)
        if parent and not os.path.exists(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create database directory {parent}: {e}"
        try:
            # Test writability cleanly without untracked schema mutation
            if os.path.exists(expanded):
                with open(expanded, "a+b"):
                    pass
            else:
                with open(expanded, "wb"):
                    pass
            import sqlite3

            conn = sqlite3.connect(expanded)
            conn.execute("PRAGMA quick_check;")
            conn.close()
            size_kb = os.path.getsize(expanded) / 1024
            return True, f"Database path valid & writable ({size_kb:.1f} KB at {expanded})"
        except Exception as e:
            return False, f"Database test failed: {e}"

    def _test_tools_directory(self, path: str) -> Tuple[bool, str]:
        if not path or not path.strip():
            count = (
                len(getattr(self.app.registry, "tools", {}))
                if hasattr(self.app, "registry") and self.app.registry
                else 0
            )
            return True, f"Using bundled CyGuide tools ({count} tools available)."
        expanded = os.path.abspath(os.path.expanduser(path.strip()))
        if not os.path.exists(expanded):
            return False, f"Tools directory does not exist: {expanded}"
        if not os.path.isdir(expanded):
            return False, f"Tools path is a file, not a directory: {expanded}"
        try:
            files = [
                f
                for f in os.listdir(expanded)
                if f.endswith((".py", ".sh", ".json")) or os.path.isdir(os.path.join(expanded, f))
            ]
            return (
                True,
                f"Custom tools directory verified ({len(files)} files/folders in {os.path.basename(expanded)}).",
            )
        except Exception as e:
            return False, f"Cannot read tools directory: {e}"

    async def _test_cloud_api(
        self, api_key: str, api_type: str, api_model: str, api_base: str
    ) -> Tuple[bool, str]:
        import time

        import httpx

        clean_key = api_key.strip().strip("'\"")
        api_type_clean = (api_type or "openai").lower().strip()
        base_url = (
            (
                api_base
                or (
                    "https://api.anthropic.com/v1"
                    if api_type_clean == "anthropic"
                    else "https://api.openai.com/v1"
                )
            )
            .strip()
            .rstrip("/")
        )
        probe_url = f"{base_url}/models" if not base_url.endswith("/models") else base_url
        headers = {
            "User-Agent": "CyGuide/1.0",
        }
        if api_type_clean == "anthropic":
            headers["x-api-key"] = clean_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {clean_key}"

        start_t = time.time()
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                resp = await client.get(probe_url, headers=headers)
                elapsed_ms = int((time.time() - start_t) * 1000)
                if resp.status_code == 200:
                    return (
                        True,
                        f"Cloud API authenticated ({elapsed_ms}ms) · {api_type} / {api_model}",
                    )
                elif resp.status_code in (401, 403):
                    return (
                        False,
                        f"Authentication failed (HTTP {resp.status_code}: Invalid API key for {api_type})",
                    )
                elif resp.status_code == 429:
                    return False, f"Rate limit reached (HTTP 429: Quota exceeded for {api_type})"
                elif resp.status_code == 404:
                    return True, f"Cloud API host reachable at {base_url} ({elapsed_ms}ms)"
                return False, f"Cloud API returned HTTP {resp.status_code}: {resp.reason_phrase}"
        except httpx.ConnectError:
            return False, f"Cannot reach Cloud endpoint {base_url}: Connection failed"
        except httpx.TimeoutException:
            return False, f"Cloud endpoint {base_url} timed out (3s limit)"
        except Exception as e:
            return False, f"Cloud test failed: {e}"

    def _sync_inputs_to_profile(self, profile_id: Optional[str]) -> None:
        if not profile_id or profile_id == "__new__":
            return
        target = next((k for k in self.cloud_keys if k.get("id") == profile_id), None)
        if not target:
            return
        try:
            target["name"] = self.query_one("#cfg_key_name", Input).value.strip()
            target["provider"] = self.query_one("#cfg_api_type", Input).value.strip()
            target["api_key"] = self.query_one("#cfg_api_key", Input).value.strip()
            target["model"] = self.query_one("#cfg_api_model", Input).value.strip()
            target["base_url"] = self.query_one("#cfg_api_base", Input).value.strip()
            target["enabled"] = self.query_one("#cfg_key_enabled", Switch).value
        except Exception:
            pass

    def _load_profile_to_inputs(self, profile_id: Optional[str]) -> None:
        target = next((k for k in self.cloud_keys if k.get("id") == profile_id), None)
        self._is_loading_inputs = True
        try:
            self.query_one("#cfg_key_name", Input).value = target.get("name", "") if target else ""
            self.query_one("#cfg_api_type", Input).value = (
                target.get("provider", "") if target else ""
            )
            self.query_one("#cfg_api_key", Input).value = (
                target.get("api_key", "") if target else ""
            )
            self.query_one("#cfg_api_model", Input).value = (
                target.get("model", "") if target else ""
            )
            self.query_one("#cfg_api_base", Input).value = (
                target.get("base_url", "") if target else ""
            )
            enabled = target.get("enabled", True) if target else True
            self.query_one("#cfg_key_enabled", Switch).value = enabled
            badge = self.query_one("#cfg_key_enabled_badge", Label)
            badge.update("[bold green]● YES[/bold green]" if enabled else "[dim]⊘ NO[/dim]")
        except Exception:
            pass
        finally:
            self._is_loading_inputs = False

    async def _switch_cloud_view(self, mode: str, save: bool = True) -> None:
        """Switch between Keys List View ('list') and Key Editor View ('editor')."""
        try:
            list_view = self.query_one("#cfg_cloud_list_view", Vertical)
            editor_view = self.query_one("#cfg_key_editor", Vertical)
            if mode == "editor":
                list_view.add_class("hidden")
                editor_view.remove_class("hidden")
                try:
                    self.query_one("#cfg_key_name", Input).focus()
                except Exception:
                    pass
            else:
                if save and self.editing_profile_id:
                    self._sync_inputs_to_profile(self.editing_profile_id)
                editor_view.add_class("hidden")
                list_view.remove_class("hidden")
                await self._rebuild_keys_list()
            try:
                self.query_one("#tab_cloud").scroll_home(animate=False)
            except Exception:
                pass
        except Exception:
            pass

    def switch_cloud_view_sync(self, mode: str, save: bool = True) -> None:
        """Synchronous wrapper for view switching."""
        try:
            list_view = self.query_one("#cfg_cloud_list_view", Vertical)
            editor_view = self.query_one("#cfg_key_editor", Vertical)
            if mode == "editor":
                list_view.add_class("hidden")
                editor_view.remove_class("hidden")
                try:
                    self.query_one("#cfg_key_name", Input).focus()
                except Exception:
                    pass
            else:
                if save and self.editing_profile_id:
                    self._sync_inputs_to_profile(self.editing_profile_id)
                editor_view.add_class("hidden")
                list_view.remove_class("hidden")
                self.run_worker(self._rebuild_keys_list())
            try:
                self.query_one("#tab_cloud").scroll_home(animate=False)
            except Exception:
                pass
        except Exception:
            pass

    async def _rebuild_keys_list(self) -> None:
        try:
            keys_list = self.query_one("#cfg_keys_list", Vertical)
            await keys_list.remove_children()
            widgets = self._build_key_list_widgets()
            await keys_list.mount_all(widgets)
            count_lbl = self.query_one("#cfg_keys_title_lbl", Label)
            count_lbl.update(f"Configured Keys ({len(self.cloud_keys)}):")
        except Exception:
            pass

    def _select_key_for_editing(self, kid: Optional[str]) -> None:
        if self.editing_profile_id and self.editing_profile_id != kid:
            self._sync_inputs_to_profile(self.editing_profile_id)

        self.editing_profile_id = kid
        self._load_profile_to_inputs(kid)
        target = next((k for k in self.cloud_keys if k.get("id") == kid), None)
        self._profile_before_edit = dict(target) if target else None
        self._new_profile_id = None

        for k in self.cloud_keys:
            cid = k.get("id")
            try:
                card = self.query_one(f"#cfg_card_{cid}", Vertical)
                if cid == kid:
                    card.add_class("cfg_key_card_selected")
                else:
                    card.remove_class("cfg_key_card_selected")
            except Exception:
                pass

        target = next((k for k in self.cloud_keys if k.get("id") == kid), None)
        target_name = (target.get("name") or target.get("id") or "") if target else ""
        short_name = (
            f": {target_name[:20]}..."
            if len(target_name) > 22
            else (f": {target_name}" if target_name else "")
        )
        title_text = f"✎ Edit Key Profile{short_name}"
        try:
            self.query_one("#cfg_editor_title", Label).update(title_text)
        except Exception:
            pass

        if target:
            try:
                self.query_one("#cfg_cloud_status_msg", Label).update(
                    self._get_cloud_quick_status(
                        target.get("api_key", ""),
                        target.get("provider", ""),
                        target.get("model", ""),
                    )
                )
            except Exception:
                pass
        else:
            try:
                self.query_one("#cfg_cloud_status_msg", Label).update(
                    self._get_cloud_quick_status("", "", "")
                )
            except Exception:
                pass

    def _set_active_key_profile(self, kid: str) -> None:
        if self.editing_profile_id and self.editing_profile_id != kid:
            self._sync_inputs_to_profile(self.editing_profile_id)
        self.active_key_id = kid
        self.is_dirty = True

        for k in self.cloud_keys:
            cid = k.get("id")
            raw_key = (k.get("api_key") or "").strip().strip("\"'")
            is_active = cid == kid
            try:
                card = self.query_one(f"#cfg_card_{cid}", Vertical)
                if is_active:
                    card.add_class("cfg_key_card_active_key")
                else:
                    card.remove_class("cfg_key_card_active_key")

                pill = self.query_one(f"#cfg_pill_{cid}", Label)
                if not raw_key or is_placeholder_key(raw_key):
                    pill.update("[bold yellow]▲ No Key[/bold yellow]")
                elif is_active:
                    pill.update("[bold green]● Active[/bold green]")
                else:
                    pill.update("[dim]▪ Standby[/dim]")

                act_btn = self.query_one(f"#cfg_activate_key_{cid}", Button)
                act_btn.disabled = is_active
            except Exception:
                pass

        try:
            self.query_one("#config_status_label", Label).update(self._get_active_status_text())
        except Exception:
            pass

        prof = next((k for k in self.cloud_keys if k.get("id") == kid), None)
        name = prof.get("name") or prof.get("provider") or kid if prof else kid
        self.app.notify(f"Set '{name}' as the active AI engine", title="Active Key Set")

    async def _delete_key_profile(self, kid: str) -> None:
        deleted_name = kid
        for k in self.cloud_keys:
            if k.get("id") == kid:
                deleted_name = k.get("name") or k.get("provider") or kid
                break

        self.cloud_keys = [k for k in self.cloud_keys if k.get("id") != kid]
        if self.active_key_id == kid:
            self.active_key_id = self.cloud_keys[0]["id"] if self.cloud_keys else None
        if self.editing_profile_id == kid:
            self.editing_profile_id = self.active_key_id or (
                self.cloud_keys[0]["id"] if self.cloud_keys else None
            )

        await self._rebuild_keys_list()
        if self.editing_profile_id:
            self._load_profile_to_inputs(self.editing_profile_id)
        else:
            self._load_profile_to_inputs(None)

        target = next((k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None)
        title_text = (
            f"✎ Edit Key Profile: {target.get('name') or target.get('id')}"
            if target
            else "✎ Key Profile Settings"
        )
        try:
            self.query_one("#cfg_editor_title", Label).update(title_text)
            self.query_one("#config_status_label", Label).update(self._get_active_status_text())
            if target:
                self.query_one("#cfg_cloud_status_msg", Label).update(
                    self._get_cloud_quick_status(
                        target.get("api_key", ""),
                        target.get("provider", ""),
                        target.get("model", ""),
                    )
                )
            else:
                self.query_one("#cfg_cloud_status_msg", Label).update(
                    self._get_cloud_quick_status("", "", "")
                )
        except Exception:
            pass

        self.is_dirty = True
        self.app.notify(f"Deleted key profile '{deleted_name}'", title="Key Removed")

    async def _add_new_key_profile(self) -> None:
        import time

        if self.editing_profile_id:
            self._sync_inputs_to_profile(self.editing_profile_id)

        new_id = f"key_{len(self.cloud_keys) + 1}_{int(time.time() * 1000) % 10000}"
        new_name = f"Key {len(self.cloud_keys) + 1}"
        new_prof = {
            "id": new_id,
            "name": new_name,
            "provider": "",
            "api_key": "",
            "model": "",
            "base_url": "",
            "enabled": True,
        }
        self.cloud_keys.append(new_prof)
        self.editing_profile_id = new_id
        self._new_profile_id = new_id
        self._profile_before_edit = None
        if not self.active_key_id:
            self.active_key_id = new_id

        await self._rebuild_keys_list()
        self._load_profile_to_inputs(new_id)

        try:
            self.query_one("#cfg_editor_title", Label).update(f"✎ Edit Key Profile: {new_name}")
            self.query_one("#cfg_cloud_status_msg", Label).update(
                self._get_cloud_quick_status("", "", "")
            )
        except Exception:
            pass

        await self._switch_cloud_view("editor")
        self.is_dirty = True
        self.app.notify(
            f"Created profile '{new_name}'. Enter credentials and click '✓ Save & Back'.",
            title="New Key Profile",
        )

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if getattr(self, "_is_loading_inputs", False):
            return
        self.is_dirty = True
        if event.switch.id == "cfg_use_ollama":
            try:
                badge = self.query_one("#cfg_ollama_switch_badge", Label)
                badge.update("[bold green]● ON[/bold green]" if event.value else "[dim]⊘ OFF[/dim]")
                self.query_one("#config_status_label", Label).update(self._get_active_status_text())
            except Exception:
                pass
        elif event.switch.id == "cfg_use_cloud_api":
            try:
                badge = self.query_one("#cfg_cloud_switch_badge", Label)
                badge.update("[bold green]● ON[/bold green]" if event.value else "[dim]⊘ OFF[/dim]")
                self.query_one("#config_status_label", Label).update(self._get_active_status_text())
            except Exception:
                pass
        elif event.switch.id == "cfg_key_enabled":
            try:
                badge = self.query_one("#cfg_key_enabled_badge", Label)
                badge.update("[bold green]● YES[/bold green]" if event.value else "[dim]⊘ NO[/dim]")
                if self.editing_profile_id:
                    prof = next(
                        (k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None
                    )
                    if prof:
                        prof["enabled"] = event.value
                        fb_lbl = self.query_one(f"#cfg_fallback_{self.editing_profile_id}", Label)
                        fb_lbl.update(
                            "[bold #38bdf8]Fallback: YES[/bold #38bdf8]"
                            if event.value
                            else "[dim #64748b]Fallback: NO[/dim #64748b]"
                        )
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if getattr(self, "_is_loading_inputs", False):
            return
        self.is_dirty = True
        cloud_inputs = {
            "cfg_key_name",
            "cfg_api_type",
            "cfg_api_key",
            "cfg_api_model",
            "cfg_api_base",
        }

        if event.input.id in cloud_inputs:
            # If no profile exists yet, only auto-create initial profile if user entered non-empty text
            if not self.editing_profile_id:
                if not event.value.strip():
                    return
                new_id = "key_1"
                self.cloud_keys = [
                    {
                        "id": new_id,
                        "name": "Primary Key",
                        "provider": "",
                        "api_key": "",
                        "model": "",
                        "base_url": "",
                        "enabled": True,
                    }
                ]
                self.editing_profile_id = new_id
                self.active_key_id = new_id
                self.run_worker(self._rebuild_keys_list())

            prof = next(
                (k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None
            )
            if prof:
                cid = prof["id"]
                if event.input.id == "cfg_key_name":
                    prof["name"] = event.value.strip()
                    try:
                        self.query_one(f"#cfg_title_{cid}", Label).update(
                            prof["name"] or "Untitled Profile"
                        )
                        self.query_one("#cfg_editor_title", Label).update(
                            f"✎ Edit Key Profile: {prof['name'] or 'Untitled'}"
                        )
                    except Exception:
                        pass
                elif event.input.id == "cfg_api_type":
                    prof["provider"] = event.value.strip().lower()
                    val = (event.value or "").strip().lower()
                    if val in PROVIDER_PRESETS:
                        preset = PROVIDER_PRESETS[val]
                        base_input = self.query_one("#cfg_api_base", Input)
                        model_input = self.query_one("#cfg_api_model", Input)
                        self._is_loading_inputs = True
                        try:
                            if not base_input.value.strip():
                                base_input.value = preset["base_url"]
                                prof["base_url"] = preset["base_url"]
                            if not model_input.value.strip():
                                model_input.value = preset["model"]
                                prof["model"] = preset["model"]
                        finally:
                            self._is_loading_inputs = False
                    try:
                        self.query_one(f"#cfg_meta_{cid}", Label).update(
                            f"{prof.get('provider') or 'custom'} · {prof.get('model') or 'default model'}"
                        )
                    except Exception:
                        pass
                elif event.input.id == "cfg_api_key":
                    prof["api_key"] = event.value.strip().strip("\"'")
                    raw = prof["api_key"]
                    masked = (
                        f"{raw[:4]}...{raw[-4:]}"
                        if len(raw) > 8
                        else ("(no key)" if not raw else "Configured")
                    )
                    try:
                        self.query_one(f"#cfg_masked_{cid}", Label).update(masked)
                        pill = self.query_one(f"#cfg_pill_{cid}", Label)
                        if not raw or is_placeholder_key(raw):
                            pill.update("[bold yellow]▲ No Key[/bold yellow]")
                        elif cid == self.active_key_id:
                            pill.update("[bold green]● Active[/bold green]")
                        else:
                            pill.update("[dim]▪ Standby[/dim]")
                    except Exception:
                        pass
                elif event.input.id == "cfg_api_model":
                    prof["model"] = event.value.strip().strip("\"'")
                    try:
                        self.query_one(f"#cfg_meta_{cid}", Label).update(
                            f"{prof.get('provider') or 'custom'} · {prof.get('model') or 'default model'}"
                        )
                    except Exception:
                        pass
                elif event.input.id == "cfg_api_base":
                    prof["base_url"] = event.value.strip().strip("\"'")

                try:
                    status_lbl = self.query_one("#cfg_cloud_status_msg", Label)
                    status_lbl.update(
                        self._get_cloud_quick_status(
                            prof.get("api_key", ""), prof.get("provider", ""), prof.get("model", "")
                        )
                    )
                    self.query_one("#config_status_label", Label).update(
                        self._get_active_status_text()
                    )
                except Exception:
                    pass

        try:
            banner = self.query_one("#config_feedback_banner", Label)
            banner.update("● Unsaved changes · Click 'Save & Apply' to commit")
            banner.remove_class("banner_ok", "banner_error", "banner_info")
            banner.add_class("banner_warn")
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        focused = self.focused
        if isinstance(focused, (Tab, Tabs)) or (focused and "Tab" in type(focused).__name__):
            return
        if isinstance(focused, Input):
            return
        if event.key == "left":
            event.stop()
            self.dismiss()
            self.app.last_palette_highlight = "Config"
            self.app.action_command_palette(preserve_highlight=True)
        elif event.key == "escape":
            event.stop()
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "cfg_save_btn":
            self.save_and_apply()
        elif btn_id == "cfg_test_btn":
            self.run_diagnostics()
        elif btn_id == "cfg_reset_btn":
            self.reset_to_defaults()
        elif btn_id in ("cfg_close_btn", "cfg_cancel_btn"):
            self.dismiss()
        elif btn_id == "cfg_key_add_btn":
            await self._add_new_key_profile()
        elif btn_id == "cfg_key_set_active_btn":
            if self.editing_profile_id:
                self._set_active_key_profile(self.editing_profile_id)
        elif btn_id in ("cfg_editor_save_btn", "cfg_editor_back_btn", "cfg_editor_done_btn"):
            if self.editing_profile_id:
                self._sync_inputs_to_profile(self.editing_profile_id)
                prof = next(
                    (k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None
                )
                prof_name = prof.get("name") or prof.get("id") if prof else "Key Profile"
                self.app.notify(
                    f"Updated profile '{prof_name}'. Click 'Save & Apply' to persist.",
                    title="Profile Updated",
                )
            self._new_profile_id = None
            self._profile_before_edit = None
            await self._switch_cloud_view("list", save=True)
        elif btn_id in ("cfg_editor_cancel_btn", "cfg_editor_just_back_btn"):
            if (
                getattr(self, "_new_profile_id", None)
                and self._new_profile_id == self.editing_profile_id
            ):
                self.cloud_keys = [
                    k for k in self.cloud_keys if k.get("id") != self._new_profile_id
                ]
                if self.active_key_id == self._new_profile_id:
                    self.active_key_id = self.cloud_keys[0]["id"] if self.cloud_keys else None
                self.editing_profile_id = self.active_key_id or (
                    self.cloud_keys[0]["id"] if self.cloud_keys else None
                )
            elif getattr(self, "_profile_before_edit", None) and self.editing_profile_id:
                target = next(
                    (k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None
                )
                if target:
                    target.clear()
                    target.update(self._profile_before_edit)
                self._load_profile_to_inputs(self.editing_profile_id)
            self._new_profile_id = None
            self._profile_before_edit = None
            await self._switch_cloud_view("list", save=False)
        elif btn_id == "cfg_key_del_btn":
            if self.editing_profile_id:
                await self._delete_key_profile(self.editing_profile_id)
            self._new_profile_id = None
            self._profile_before_edit = None
            await self._switch_cloud_view("list", save=False)
        elif btn_id.startswith("cfg_edit_key_"):
            kid = btn_id[len("cfg_edit_key_") :]
            self._select_key_for_editing(kid)
            await self._switch_cloud_view("editor")
        elif btn_id.startswith("cfg_activate_key_"):
            kid = btn_id[len("cfg_activate_key_") :]
            self._set_active_key_profile(kid)
        elif btn_id.startswith("cfg_delete_key_"):
            kid = btn_id[len("cfg_delete_key_") :]
            await self._delete_key_profile(kid)

    @work(exclusive=True, group="config_save")
    async def save_and_apply(self) -> None:
        """Validate, persist settings, rebind engines, report status, and remain open."""
        save_btn = None
        try:
            save_btn = self.query_one("#cfg_save_btn", Button)
            save_btn.loading = True
        except Exception:
            pass

        banner = self.query_one("#config_feedback_banner", Label)
        try:
            # 1. Validate DB path
            raw_db = self.query_one("#cfg_db_path", Input).value.strip()
            norm_db, db_err = normalize_and_validate_db_path(
                raw_db, getattr(self.app, "data_dir", None)
            )
            if db_err:
                banner.update(f"▲ Cannot save: {db_err}")
                banner.remove_class("banner_info", "banner_ok", "banner_warn")
                banner.add_class("banner_error")
                self.app.notify(db_err, title="Database Error", severity="error")
                return

            # 2. Validate Tools directory
            raw_tools = self.query_one("#cfg_tools_dir", Input).value.strip()
            norm_tools, tools_err = normalize_and_validate_tools_dir(
                raw_tools, create_if_missing=True
            )
            if tools_err:
                banner.update(f"▲ Cannot save: {tools_err}")
                banner.remove_class("banner_info", "banner_ok", "banner_warn")
                banner.add_class("banner_error")
                self.app.notify(tools_err, title="Tools Directory Error", severity="error")
                return

            # Validate Exports directory
            raw_exports = self.query_one("#cfg_exports_dir", Input).value.strip()
            norm_exports, exports_err = normalize_and_validate_export_dir(
                raw_exports, create_if_missing=True
            )
            if exports_err:
                banner.update(f"▲ Cannot save: {exports_err}")
                banner.remove_class("banner_info", "banner_ok", "banner_warn")
                banner.add_class("banner_error")
                self.app.notify(exports_err, title="Exports Directory Error", severity="error")
                return

            # Validate Reports directory
            raw_reports = self.query_one("#cfg_reports_dir", Input).value.strip()
            norm_reports, reports_err = normalize_and_validate_report_dir(
                raw_reports, create_if_missing=True
            )
            if reports_err:
                banner.update(f"▲ Cannot save: {reports_err}")
                banner.remove_class("banner_info", "banner_ok", "banner_warn")
                banner.add_class("banner_error")
                self.app.notify(reports_err, title="Reports Directory Error", severity="error")
                return

            # 3. Normalize Ollama & Cloud AI settings
            use_ollama = self.query_one("#cfg_use_ollama", Switch).value
            use_cloud_api = self.query_one("#cfg_use_cloud_api", Switch).value
            ollama_model = self.query_one("#cfg_ollama_model", Input).value.strip() or "gemma"
            raw_ollama_url = (
                self.query_one("#cfg_ollama_base_url", Input).value.strip()
                or "http://localhost:11434"
            )
            ollama_base_url = normalize_ollama_url(raw_ollama_url)

            # 4. Sync editing profile
            if self.editing_profile_id and self.editing_profile_id != "__new__":
                self._sync_inputs_to_profile(self.editing_profile_id)

            # Security validation: Ensure each API key is unique across non-empty profiles
            seen_keys: Dict[str, str] = {}
            for prof in self.cloud_keys:
                raw_k = prof.get("api_key", "").strip().strip("\"'")
                if not raw_k or is_placeholder_key(raw_k):
                    continue
                if raw_k in seen_keys:
                    first_name = seen_keys[raw_k]
                    this_name = prof.get("name") or prof.get("id")
                    err_msg = f"Duplicate API key in '{this_name}' matches '{first_name}'. Each profile must use a unique API key."
                    banner.update(f"▲ Security alert: {err_msg}")
                    banner.remove_class("banner_info", "banner_ok", "banner_warn")
                    banner.add_class("banner_error")
                    self.app.notify(err_msg, title="Duplicate Key Security Error", severity="error")
                    return
                seen_keys[raw_k] = prof.get("name") or prof.get("id")

            # Check active key ID
            if self.cloud_keys:
                if not self.active_key_id or not any(
                    k.get("id") == self.active_key_id for k in self.cloud_keys
                ):
                    self.active_key_id = self.cloud_keys[0]["id"]
            else:
                self.active_key_id = None

            active_prof = next(
                (k for k in self.cloud_keys if k.get("id") == self.active_key_id), None
            )
            api_key = active_prof.get("api_key", "") if active_prof else ""
            api_type = active_prof.get("provider", "") if active_prof else ""
            api_model = active_prof.get("model", "") if active_prof else ""
            api_base = active_prof.get("base_url", "") if active_prof else ""

            # Apply defaults only if provider was chosen but endpoints left blank
            if api_type and not api_base:
                if api_type == "groq":
                    api_base = "https://api.groq.com/openai/v1"
                elif api_type == "anthropic":
                    api_base = "https://api.anthropic.com/v1"
                else:
                    api_base = "https://api.openai.com/v1"

            if api_type and not api_model:
                if api_type == "groq":
                    api_model = "llama-3.3-70b-versatile"
                elif api_type == "anthropic":
                    api_model = "claude-3-5-sonnet-20241022"
                else:
                    api_model = "gpt-4o"

            app = self.app

            # 5. Switch Database if changed
            if norm_db != getattr(app, "db_path", None):
                try:
                    await app.switch_database(norm_db)
                except Exception as e:
                    banner.update(f"▲ Failed to connect to database: {e}")
                    banner.remove_class("banner_info", "banner_ok", "banner_warn")
                    banner.add_class("banner_error")
                    app.notify(f"Database error: {e}", title="Error", severity="error")
                    return
            else:
                app.db_path = norm_db

            # 6. Apply App & Environment properties
            app.use_ollama = use_ollama
            app.use_cloud_api = use_cloud_api
            app.ollama_model = ollama_model
            app.tools_dir = norm_tools
            app.exports_dir = norm_exports
            app.reports_dir = norm_reports
            app.cloud_keys = list(self.cloud_keys)
            app.active_key_id = self.active_key_id

            if api_key and not is_placeholder_key(api_key):
                os.environ["CYGUIDE_API_KEY"] = api_key
            elif "CYGUIDE_API_KEY" in os.environ and not api_key:
                os.environ.pop("CYGUIDE_API_KEY", None)

            if api_type:
                os.environ["CYGUIDE_API_TYPE"] = api_type
            else:
                os.environ.pop("CYGUIDE_API_TYPE", None)

            if api_model:
                os.environ["CYGUIDE_API_MODEL"] = api_model
            else:
                os.environ.pop("CYGUIDE_API_MODEL", None)

            if api_base:
                os.environ["CYGUIDE_API_BASE"] = api_base
            else:
                os.environ.pop("CYGUIDE_API_BASE", None)

            # 7. Persist settings
            updates = {
                "use_ollama": use_ollama,
                "use_cloud_api": use_cloud_api,
                "ollama_model": ollama_model,
                "ollama_base_url": ollama_base_url,
                "api_type": api_type,
                "api_key": api_key,
                "api_model": api_model,
                "api_base": api_base,
                "cloud_keys": self.cloud_keys,
                "active_key_id": self.active_key_id,
                "db_path": norm_db,
                "tools_dir": norm_tools,
                "exports_dir": norm_exports,
                "reports_dir": norm_reports,
            }
            if hasattr(app, "save_settings"):
                await asyncio.to_thread(app.save_settings, updates)

            # 8. Reload Explainer
            if hasattr(app, "reload_explainer"):
                await asyncio.to_thread(app.reload_explainer)

            # 9. Reload Tool Registry & check for errors
            tool_issues = ""
            if hasattr(app, "reload_registry"):
                await asyncio.to_thread(app.reload_registry)
                if hasattr(app.registry, "load_errors") and app.registry.load_errors:
                    tool_issues = f" ({len(app.registry.load_errors)} tool loading error{'s' if len(app.registry.load_errors) > 1 else ''})"

            # 10. Update UI state in-place (DO NOT DISMISS!)
            self.is_dirty = False
            try:
                sel = self.query_one("#cfg_key_select", Select)
                sel.set_options(self._get_select_options())
                if self.editing_profile_id:
                    sel.value = self.editing_profile_id
                self.query_one("#config_status_label", Label).update(self._get_active_status_text())
                if active_prof:
                    self.query_one("#cfg_cloud_status_msg", Label).update(
                        self._get_cloud_quick_status(
                            active_prof.get("api_key", ""),
                            active_prof.get("provider", ""),
                            active_prof.get("model", ""),
                        )
                    )
            except Exception:
                pass

            # Inform user if credentials missing or valid
            if use_cloud_api and (not api_key or is_placeholder_key(api_key)):
                prof_title = active_prof.get("name") if active_prof else "None"
                warn_msg = f"✓ Settings saved. ⚠️ Profile '{prof_title}' is missing an API key (Local Ollama will be used)."
                banner.update(warn_msg)
                banner.remove_class("banner_info", "banner_error", "banner_ok")
                banner.add_class("banner_warn")
            else:
                banner.update(f"✓ Configuration saved and applied successfully!{tool_issues}")
                banner.remove_class("banner_info", "banner_error", "banner_warn")
                banner.add_class("banner_ok")

            notice = f"Configuration saved and applied!{tool_issues}"
            app.notify(
                notice, title="Config Saved", severity="warning" if tool_issues else "information"
            )
        except Exception as e:
            banner.update(f"▲ Error saving settings: {e}")
            banner.remove_class("banner_info", "banner_ok", "banner_warn")
            banner.add_class("banner_error")
            self.app.notify(f"Failed to save settings: {e}", title="Error", severity="error")
        finally:
            if save_btn is not None:
                try:
                    save_btn.loading = False
                    save_btn.disabled = False
                except Exception:
                    pass

    def reset_to_defaults(self) -> None:
        """Reset form fields to standard CLI defaults while safely preserving configured API keys."""
        try:
            self._is_loading_inputs = True
            try:
                default_db = get_default_db_path(getattr(self.app, "data_dir", None))
                self.query_one("#cfg_use_ollama", Switch).value = False
                self.query_one("#cfg_use_cloud_api", Switch).value = True
                try:
                    self.query_one("#cfg_cloud_switch_badge", Label).update(
                        "[bold green]● ON[/bold green]"
                    )
                except Exception:
                    pass
                self.query_one("#cfg_ollama_model", Input).value = "gemma"
                self.query_one("#cfg_ollama_base_url", Input).value = "http://localhost:11434"
                self.query_one("#cfg_db_path", Input).value = default_db
                self.query_one("#cfg_tools_dir", Input).value = ""
                self.query_one("#cfg_exports_dir", Input).value = ""
                self.query_one("#cfg_reports_dir", Input).value = ""

                # DO NOT wipe self.cloud_keys! Keep user API keys safe.
                # Reset endpoints / models of current profile to provider defaults if applicable
                if self.editing_profile_id:
                    prof = next(
                        (k for k in self.cloud_keys if k.get("id") == self.editing_profile_id), None
                    )
                    if prof:
                        prov = prof.get("provider", "").lower()
                        if prov in PROVIDER_PRESETS:
                            preset = PROVIDER_PRESETS[prov]
                            prof["base_url"] = preset["base_url"]
                            prof["model"] = preset["model"]
                            try:
                                self.query_one("#cfg_api_base", Input).value = preset["base_url"]
                                self.query_one("#cfg_api_model", Input).value = preset["model"]
                            except Exception:
                                pass
            finally:
                self._is_loading_inputs = False

            self.is_dirty = True
            banner = self.query_one("#config_feedback_banner", Label)
            banner.update(
                "● Standard defaults loaded (saved API keys preserved). Click 'Save & Apply' to commit."
            )
            banner.remove_class("banner_error", "banner_ok", "banner_info")
            banner.add_class("banner_warn")
            self.app.notify(
                "Standard defaults loaded (API keys preserved). Click 'Save & Apply' to commit.",
                title="Defaults Loaded",
            )
        except Exception as e:
            self.app.notify(f"Error resetting fields: {e}", severity="warning")
