"""Learning Mode screen with redesigned Phase 2 lesson layout."""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, List, Optional

from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ListView,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
    TextArea,
)

from cyguide.engine.learning import PreflightRequiredEvent
from cyguide.paths import get_default_checkpoints_dir, get_default_exports_dir
from cyguide.ui.dialogs import ConfirmationDialog
from cyguide.ui.screens.checkpoint_modals import LoadCheckpointModal, SaveCheckpointModal
from cyguide.ui.screens.preflight_modal import PreflightModal, PreflightModalResult
from cyguide.ui.widgets import EntityBrowser, ResizeHandle, TerminalStreamPane
from cyguide.ui.widgets.flags import FlagEditor
from cyguide.ui.widgets.markdown import (
    CYGUIDE_MARKDOWN_THEME,
    CyGuideMarkdown,
    render_markdown,
)
from cyguide.ui.widgets.recipe_deck import RecipeDeck, RecipeListItem

DEFAULT_TUTOR_WELCOME_MARKDOWN = (
    "### ✦ AI Copilot Tutor Ready\n\n"
    "Ask questions about tool options, flags, or syntax in the prompt below, or run a scan to stream live explanations.\n\n"
    "#### ⌨ Quick Shortcuts\n"
    "- **`Ctrl+I`** — Focus AI Tutor prompt\n"
    "- **`Ctrl+N`** — Focus Notes scratchpad\n"
    "- **`Ctrl+Alt+E`** — Export Notes to Markdown\n"
    "- **`F1`** — View all shortcuts & hotkeys"
)


class LearningModeScreen(Screen):
    """Phase 2: The Lesson Screen."""

    AUTO_FOCUS = "#recipe_list"

    BINDINGS = [
        ("f1", "show_shortcuts", "Help"),
        ("ctrl+left", "prev_tab", "Prev Tab"),
        ("ctrl+right", "next_tab", "Next Tab"),
        Binding("ctrl+c", "copy_selection", "Copy Selection", show=False),
        Binding("ctrl+y", "copy_explanation", "Copy All", show=False),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", priority=True),
        Binding("ctrl+alt+b", "toggle_copilot", "Copilot", priority=True),
        Binding("alt+ctrl+b", "toggle_copilot", "Copilot", show=False, priority=True),
        Binding("ctrl+i", "focus_tutor", "Tutor", show=False, priority=True),
        Binding("ctrl+n", "focus_notes", "Notes", show=False, priority=True),
        Binding("ctrl+alt+e", "export_notes", "Export Notes", show=False, priority=True),
        Binding("alt+ctrl+e", "export_notes", "Export Notes", show=False, priority=True),
        ("ctrl+s", "save_checkpoint", "Save Lab"),
        ("ctrl+o", "load_checkpoint", "Load Lab"),
        Binding("ctrl+alt+r", "reset_session", "Reset Lab", priority=True),
        Binding("alt+ctrl+r", "reset_session", "Reset Lab", show=False, priority=True),
        Binding("ctrl+g", "toggle_sidebar_graph", "Graph View", priority=True),
        Binding("escape", "nav_tool_browser", "Tool Browser", show=False, priority=True),
        Binding("ctrl+[", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True),
        Binding(
            "ctrl+left_square_bracket",
            "shrink_sidebar",
            "Shrink Sidebar",
            show=False,
            priority=True,
        ),
        Binding("ctrl+{", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True),
        Binding(
            "ctrl+left_curly_bracket", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True
        ),
        Binding(
            "ctrl+shift+left_square_bracket",
            "shrink_sidebar",
            "Shrink Sidebar",
            show=False,
            priority=True,
        ),
        Binding("ctrl+]", "expand_sidebar", "Expand Sidebar", show=False, priority=True),
        Binding(
            "ctrl+right_square_bracket",
            "expand_sidebar",
            "Expand Sidebar",
            show=False,
            priority=True,
        ),
        Binding("ctrl+}", "expand_sidebar", "Expand Sidebar", show=False, priority=True),
        Binding(
            "ctrl+right_curly_bracket",
            "expand_sidebar",
            "Expand Sidebar",
            show=False,
            priority=True,
        ),
        Binding(
            "ctrl+shift+right_square_bracket",
            "expand_sidebar",
            "Expand Sidebar",
            show=False,
            priority=True,
        ),
        Binding("alt+[", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True),
        Binding(
            "alt+left_square_bracket", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True
        ),
        Binding("alt+{", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True),
        Binding(
            "alt+left_curly_bracket", "shrink_sidebar", "Shrink Sidebar", show=False, priority=True
        ),
        Binding(
            "alt+shift+left_square_bracket",
            "shrink_sidebar",
            "Shrink Sidebar",
            show=False,
            priority=True,
        ),
        Binding("alt+]", "expand_sidebar", "Expand Sidebar", show=False, priority=True),
        Binding(
            "alt+right_square_bracket",
            "expand_sidebar",
            "Expand Sidebar",
            show=False,
            priority=True,
        ),
        Binding("alt+}", "expand_sidebar", "Expand Sidebar", show=False, priority=True),
        Binding(
            "alt+right_curly_bracket", "expand_sidebar", "Expand Sidebar", show=False, priority=True
        ),
        Binding(
            "alt+shift+right_square_bracket",
            "expand_sidebar",
            "Expand Sidebar",
            show=False,
            priority=True,
        ),
        Binding("ctrl+alt+[", "expand_copilot", "Expand Copilot", show=False, priority=True),
        Binding(
            "ctrl+alt+left_square_bracket",
            "expand_copilot",
            "Expand Copilot",
            show=False,
            priority=True,
        ),
        Binding("ctrl+alt+{", "expand_copilot", "Expand Copilot", show=False, priority=True),
        Binding(
            "ctrl+alt+left_curly_bracket",
            "expand_copilot",
            "Expand Copilot",
            show=False,
            priority=True,
        ),
        Binding("alt+ctrl+[", "expand_copilot", "Expand Copilot", show=False, priority=True),
        Binding(
            "alt+ctrl+left_square_bracket",
            "expand_copilot",
            "Expand Copilot",
            show=False,
            priority=True,
        ),
        Binding("ctrl+alt+]", "shrink_copilot", "Shrink Copilot", show=False, priority=True),
        Binding(
            "ctrl+alt+right_square_bracket",
            "shrink_copilot",
            "Shrink Copilot",
            show=False,
            priority=True,
        ),
        Binding("ctrl+alt+}", "shrink_copilot", "Shrink Copilot", show=False, priority=True),
        Binding(
            "ctrl+alt+right_curly_bracket",
            "shrink_copilot",
            "Shrink Copilot",
            show=False,
            priority=True,
        ),
        Binding("alt+ctrl+]", "shrink_copilot", "Shrink Copilot", show=False, priority=True),
        Binding(
            "alt+ctrl+right_square_bracket",
            "shrink_copilot",
            "Shrink Copilot",
            show=False,
            priority=True,
        ),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self._session: Optional[Any] = None
        self.current_view = "explanation"
        self._fallback_active_tool: Optional[str] = None
        self._fallback_active_recipe_idx: Optional[int] = None
        self._fallback_log_buffer: List[str] = []
        self._fallback_scan_in_progress: bool = False
        self._fallback_explanation_buffer: str = ""
        self._fallback_run_count: int = 0
        self._fallback_ai_enabled: bool = True
        self._scratchpad_loading: bool = False
        self._scratchpad_loaded: bool = False

    def _get_app(self) -> Optional[Any]:
        try:
            return self.app
        except Exception:
            return None

    @property
    def session(self) -> Any:
        if self._session is None:
            app = self._get_app()
            self._session = getattr(app, "learning_session", None)
            if self._session is None:
                from uuid import UUID

                from cyguide.engine.learning import LearningSession

                store = getattr(app, "store", None)
                reg = getattr(app, "registry", None)
                facade = getattr(app, "power_facade", None)
                execution = getattr(facade, "execution", None) if facade else None
                explainer = getattr(app, "explainer", None)
                sess_id_raw = getattr(app, "learning_session_id", None)
                sess_id = UUID(str(sess_id_raw)) if sess_id_raw else None
                ws_id_raw = getattr(app, "learning_ws_id", None)
                ws_id = UUID(str(ws_id_raw)) if ws_id_raw else None
                self._session = LearningSession(
                    store=store,
                    registry=reg,
                    execution=execution,
                    explainer=explainer,
                    session_id=sess_id,
                    workspace_id=ws_id,
                )
                if self._fallback_active_tool is not None:
                    self._session.active_tool = self._fallback_active_tool
                if self._fallback_active_recipe_idx is not None:
                    self._session.active_recipe_idx = self._fallback_active_recipe_idx
                if self._fallback_log_buffer:
                    self._session.log_buffer = self._fallback_log_buffer
                if self._fallback_scan_in_progress:
                    self._session.scan_in_progress = self._fallback_scan_in_progress
                if self._fallback_explanation_buffer:
                    self._session.explanation_buffer = self._fallback_explanation_buffer
                if self._fallback_run_count:
                    self._session.run_count = self._fallback_run_count
                self._session.ai_enabled = self._fallback_ai_enabled
        return self._session

    @property
    def active_tool(self) -> Optional[str]:
        return self.session.active_tool

    @active_tool.setter
    def active_tool(self, val: Optional[str]) -> None:
        self._fallback_active_tool = val
        self.session.active_tool = val

    @property
    def active_recipe_idx(self) -> Optional[int]:
        return self.session.active_recipe_idx

    @active_recipe_idx.setter
    def active_recipe_idx(self, val: Optional[int]) -> None:
        self._fallback_active_recipe_idx = val
        self.session.active_recipe_idx = val

    @property
    def scan_in_progress(self) -> bool:
        return self.session.scan_in_progress

    @scan_in_progress.setter
    def scan_in_progress(self, val: bool) -> None:
        self._fallback_scan_in_progress = val
        self.session.scan_in_progress = val

    @property
    def run_count(self) -> int:
        return self.session.run_count

    @run_count.setter
    def run_count(self, val: int) -> None:
        self._fallback_run_count = val
        self.session.run_count = val

    @property
    def log_buffer(self) -> List[str]:
        return self.session.log_buffer

    @log_buffer.setter
    def log_buffer(self, val: List[str]) -> None:
        self._fallback_log_buffer = val
        self.session.log_buffer = val

    @property
    def explanation_buffer(self) -> str:
        return self.session.explanation_buffer

    @explanation_buffer.setter
    def explanation_buffer(self, val: str) -> None:
        self._fallback_explanation_buffer = val
        self.session.explanation_buffer = val

    @property
    def ai_explanations_enabled(self) -> bool:
        return self.session.ai_enabled

    @ai_explanations_enabled.setter
    def ai_explanations_enabled(self, val: bool) -> None:
        self._fallback_ai_enabled = val
        self.session.ai_enabled = val

    def compose(self) -> ComposeResult:
        with Horizontal(id="learning_layout"):
            # Left Zone: Context and Configuration
            with Vertical(id="lesson_config_pane"):
                with Vertical(id="tool_context_zone"):
                    with Horizontal(id="tool_context_header_bar"):
                        yield Label("◆ TOOL CONTEXT", id="tool_name_header", classes="pane_title")
                        with Horizontal(id="checkpoint_action_bar"):
                            yield Button(
                                "⤓ SAVE", id="save_checkpoint_btn", classes="checkpoint_btn"
                            )
                            yield Button(
                                "⤒ LOAD", id="load_checkpoint_btn", classes="checkpoint_btn"
                            )
                            yield Button("↻", id="reset_session_btn", classes="checkpoint_btn")
                    yield Static("", id="tool_summary_header")

                with Horizontal(id="sidebar_view_toggle"):
                    yield Button(
                        "◆ RECIPES",
                        id="toggle_recipes_btn",
                        classes="sidebar_toggle_btn active_view",
                    )
                    yield Button("◈ GRAPH", id="toggle_graph_btn", classes="sidebar_toggle_btn")

                with ListView(id="recipe_list"):
                    pass  # Populated in select_tool

                yield EntityBrowser(id="learning_entity_browser", classes="hidden")

                with Vertical(id="launchpad_container"):
                    yield Vertical(id="flag_editor_container")
                    with Horizontal(id="run_stop_container"):
                        yield Button("✦ ASK AI", id="sidebar_ask_btn", classes="sidebar_action_btn")
                        yield Button(
                            "▶ RUN", id="run_btn", variant="success", classes="sidebar_action_btn"
                        )
                        yield Button(
                            "■ STOP",
                            id="stop_btn",
                            variant="error",
                            classes="hidden sidebar_action_btn",
                        )

            # Resizer handle for learning sidebar
            yield ResizeHandle(
                target_id="lesson_config_pane",
                side="left",
                min_size=20,
                max_size=70,
                setting_key="learning_sidebar_width",
                id="learning_sidebar_resizer",
            )

            # Center Zone: Execution Workbench
            with Vertical(id="lesson_execution_pane"):
                with TabbedContent(id="learning_tabs", initial="tab_recipes"):
                    with TabPane("◆ RECIPES", id="tab_recipes"):
                        with RecipeDeck(id="recipes_scroll"):
                            yield Static(
                                "Select a tool to view available workflow recipes.",
                                id="recipes_empty_state",
                                classes="recipes_header_intro",
                            )

                    with TabPane("◆ RAW OUTPUT", id="tab_output"):
                        with Horizontal(classes="pane_toolbar"):
                            yield Button("COPY", id="copy_output_btn", classes="pane_action_btn")
                            yield Button("CLEAR", id="clear_output_btn", classes="pane_action_btn")
                        yield TerminalStreamPane(id="raw_output_terminal")

                    with TabPane("◆ THEORY & DEEP DIVE", id="tab_theory"):
                        with Horizontal(classes="pane_toolbar", id="theory_toolbar"):
                            yield Button("COPY", id="copy_theory_btn", classes="pane_action_btn")
                        with VerticalScroll(id="theory_scroll"):
                            yield Static(
                                render_markdown(
                                    "*Select a tool or recipe to inspect its protocol theory and wire analysis.*"
                                ),
                                id="theory_markdown_view",
                            )

            # Resizer handle for learning copilot pane
            yield ResizeHandle(
                target_id="learning_copilot_pane",
                side="right",
                min_size=26,
                max_size=80,
                setting_key="learning_copilot_width",
                id="learning_copilot_resizer",
            )

            # Right Zone: AI Copilot & Lab Notes Scratchpad
            with Vertical(id="learning_copilot_pane"):
                with TabbedContent(id="copilot_tabs", initial="copilot_tab_ai"):
                    with TabPane("✦ TUTOR", id="copilot_tab_ai"):
                        with Horizontal(classes="pane_toolbar", id="explanation_toolbar"):
                            yield Label(
                                "[dim #71717a]AI: Offline[/]",
                                id="copilot_model_badge",
                            )
                            yield Label(
                                "", id="explanation_status_label", classes="pane_status_label"
                            )
                            yield Button(
                                "COPY", id="copy_explanation_btn", classes="pane_action_btn"
                            )
                            yield Button(
                                "CLEAR", id="clear_explanation_btn", classes="pane_action_btn"
                            )
                        with VerticalScroll(id="explanation_scroll"):
                            yield Static(
                                render_markdown(DEFAULT_TUTOR_WELCOME_MARKDOWN),
                                id="explanation_text",
                            )
                        with Horizontal(id="chat_dock"):
                            yield Label("◆", id="chat_prompt_symbol")
                            yield Input(
                                placeholder="Ask AI tutor or type / for commands (/summary, /flags, /help)...",
                                id="chat_input",
                                disabled=False,
                            )
                            yield Button("ASK", id="ask_btn", variant="primary", disabled=False)

                    with TabPane("✎ NOTES", id="copilot_tab_notes"):
                        with Horizontal(classes="pane_toolbar", id="notes_toolbar"):
                            yield Button("COPY", id="copy_notes_btn", classes="pane_action_btn")
                            yield Button("EXPORT", id="export_notes_btn", classes="pane_action_btn")
                            yield Button("CLEAR", id="clear_notes_btn", classes="pane_action_btn")
                        yield TextArea(
                            id="learning_scratchpad_textarea",
                            show_line_numbers=True,
                            theme="cyguide",
                            language="markdown",
                        )

        yield Footer()

    def _restore_sidebar_width(self) -> None:
        """Restore user's saved sidebar width preference."""
        try:
            if hasattr(self.app, "settings"):
                saved_width = self.app.settings.get("learning_sidebar_width")
                if saved_width:
                    pane = self.query_one("#lesson_config_pane")
                    w = int(saved_width)
                    pane.styles.width = w
                    self._sync_sidebar_responsive_layout(w)
        except Exception:
            pass

    def _sync_sidebar_responsive_layout(self, width: int | None = None) -> None:
        """Dynamically adapt left sidebar buttons and labels based on width."""
        try:
            pane = self.query_one("#lesson_config_pane")
            if width is None:
                if pane.styles.width and pane.styles.width.value is not None:
                    width = int(pane.styles.width.value)
                elif pane.region.width > 0:
                    width = int(pane.region.width)
                else:
                    width = 32

            tier = 0 if width < 26 else (1 if width < 36 else 2)
            if getattr(self, "_current_sidebar_tier", None) == tier:
                return
            self._current_sidebar_tier = tier

            save_btn = self.query_one("#save_checkpoint_btn", Button)
            load_btn = self.query_one("#load_checkpoint_btn", Button)
            reset_btn = self.query_one("#reset_session_btn", Button)
            ask_btn = self.query_one("#sidebar_ask_btn", Button)
            run_btn = self.query_one("#run_btn", Button)
            stop_btn = self.query_one("#stop_btn", Button)

            if width < 26:
                ask_btn.label = "✦ ASK"
                run_btn.label = "▶"
                stop_btn.label = "■"
            else:
                ask_btn.label = "✦ ASK AI"
                run_btn.label = "▶ RUN"
                stop_btn.label = "■ STOP"

            # Checkpoint & reset actions in tool context header bar:
            # - width < 26: Ultra-compact icon mode (⤓, ⤒, ↻)
            # - 26 <= width < 36: Standard mode (⤓ SAVE, ⤒ LOAD, ↻)
            # - width >= 36: Full label mode (⤓ SAVE, ⤒ LOAD, ↻ RESET)
            if width < 26:
                new_save = "⤓"
                new_load = "⤒"
                new_reset = "↻"
            elif width < 36:
                new_save = "⤓ SAVE"
                new_load = "⤒ LOAD"
                new_reset = "↻"
            else:
                new_save = "⤓ SAVE"
                new_load = "⤒ LOAD"
                new_reset = "↻ RESET"

            if (
                str(save_btn.label) != new_save
                or str(load_btn.label) != new_load
                or str(reset_btn.label) != new_reset
            ):
                save_btn.label = new_save
                load_btn.label = new_load
                reset_btn.label = new_reset

                for w in (save_btn, load_btn, reset_btn):
                    w.refresh(layout=True)

                action_bar = self.query_one("#checkpoint_action_bar")
                action_bar.refresh(layout=True)

                header_bar = self.query_one("#tool_context_header_bar")
                header_bar.refresh(layout=True)
        except Exception:
            pass

    def _restore_copilot_width(self) -> None:
        """Restore user's saved copilot sidebar width preference."""
        try:
            if hasattr(self.app, "settings"):
                saved_width = self.app.settings.get("learning_copilot_width")
                if saved_width:
                    pane = self.query_one("#learning_copilot_pane")
                    w = int(saved_width)
                    pane.styles.width = w
                    self._sync_copilot_responsive_layout(w)
        except Exception:
            pass

    def _sync_copilot_responsive_layout(self, width: int | None = None) -> None:
        """Dynamically adapt copilot buttons, badges, and docks to pane width."""
        try:
            pane = self.query_one("#learning_copilot_pane")
            if width is None:
                if pane.styles.width and pane.styles.width.value is not None:
                    width = int(pane.styles.width.value)
                elif pane.region.width > 0:
                    width = int(pane.region.width)
                else:
                    width = 44

            tier = 0 if width < 36 else (1 if width < 50 else 2)
            is_on = getattr(self, "ai_explanations_enabled", True)
            tier_state = (tier, is_on)
            if getattr(self, "_current_copilot_tier_state", None) == tier_state:
                return
            self._current_copilot_tier_state = tier_state

            try:
                badge = self.query_one("#copilot_model_badge", Label)
            except Exception:
                badge = None
            try:
                btn = self.query_one("#toggle_ai_explanation_btn", Button)
            except Exception:
                btn = None
            try:
                copy_btn = self.query_one("#copy_explanation_btn", Button)
            except Exception:
                copy_btn = None
            try:
                clear_btn = self.query_one("#clear_explanation_btn", Button)
            except Exception:
                clear_btn = None
            try:
                ask_btn = self.query_one("#ask_btn", Button)
            except Exception:
                ask_btn = None
            try:
                chat_input = self.query_one("#chat_input", Input)
            except Exception:
                chat_input = None
            try:
                copy_notes = self.query_one("#copy_notes_btn", Button)
            except Exception:
                copy_notes = None
            try:
                export_notes = self.query_one("#export_notes_btn", Button)
            except Exception:
                export_notes = None
            try:
                clear_notes = self.query_one("#clear_notes_btn", Button)
            except Exception:
                clear_notes = None

            if width < 36:
                if badge:
                    badge.styles.display = "none"
                if btn:
                    btn.label = "● ON" if is_on else "○ OFF"
                if copy_btn:
                    copy_btn.label = "⎘"
                if clear_btn:
                    clear_btn.label = "⌫"
                if ask_btn:
                    ask_btn.label = "▶"
                if chat_input:
                    chat_input.placeholder = "Ask AI..."
                if copy_notes:
                    copy_notes.label = "⎘"
                if export_notes:
                    export_notes.label = "⤓"
                if clear_notes:
                    clear_notes.label = "⌫"
            elif width < 50:
                if badge:
                    badge.styles.display = "block"
                if btn:
                    btn.label = "● AI: ON" if is_on else "○ AI: OFF"
                if copy_btn:
                    copy_btn.label = "COPY"
                if clear_btn:
                    clear_btn.label = "CLEAR"
                if ask_btn:
                    ask_btn.label = "ASK"
                if chat_input:
                    chat_input.placeholder = "Ask AI tutor or / for help..."
                if copy_notes:
                    copy_notes.label = "COPY"
                if export_notes:
                    export_notes.label = "EXPORT"
                if clear_notes:
                    clear_notes.label = "CLEAR"
            else:
                if badge:
                    badge.styles.display = "block"
                if btn:
                    btn.label = "● AI: ON" if is_on else "○ AI: OFF"
                if copy_btn:
                    copy_btn.label = "COPY"
                if clear_btn:
                    clear_btn.label = "CLEAR"
                if ask_btn:
                    ask_btn.label = "ASK"
                if chat_input:
                    chat_input.placeholder = "Ask AI tutor or type / for commands..."
                if copy_notes:
                    copy_notes.label = "COPY"
                if export_notes:
                    export_notes.label = "EXPORT"
                if clear_notes:
                    clear_notes.label = "CLEAR"
        except Exception:
            pass

    def _update_model_badge(self) -> None:
        """Update active AI model indicator in copilot header."""
        try:
            badge = self.query_one("#copilot_model_badge", Label)
            explainer = getattr(self.app, "explainer", None)
            if not explainer:
                badge.update("[dim #71717a]AI: Offline[/]")
                return
            if hasattr(explainer, "is_active_model_local") and explainer.is_active_model_local():
                model = (
                    getattr(explainer.ollama_backend, "model_name", "ollama")
                    if hasattr(explainer, "ollama_backend")
                    else "ollama"
                )
                badge.update(f"[bold #34d399]● Local ({model})[/]")
            else:
                prof = (
                    explainer.get_active_profile()
                    if hasattr(explainer, "get_active_profile")
                    else None
                )
                name = prof.model_name if prof else "Cloud AI"
                badge.update(f"[bold #38bdf8]● {name}[/]")
        except Exception:
            pass

    @work(exclusive=True, group="learning_scratchpad_load")
    async def _async_load_scratchpad(self) -> None:
        self._scratchpad_loading = True
        try:
            content = await self.session.get_notes()
            try:
                self.query_one("#learning_scratchpad_textarea", TextArea).load_text(content or "")
                self._scratchpad_loaded = True
            except Exception:
                pass
        finally:
            self._scratchpad_loading = False

    def _load_scratchpad(self) -> None:
        """Load student notes from SQLite learning session into scratchpad textarea."""
        if hasattr(self, "_session") and self._session and self._session.notes:
            try:
                self.query_one("#learning_scratchpad_textarea", TextArea).load_text(
                    self._session.notes
                )
                self._scratchpad_loaded = True
            except Exception:
                pass
        self._async_load_scratchpad()

    def _save_scratchpad(self, immediate: bool = False) -> None:
        """Save scratchpad text to session memory and SQLite with debounced write."""
        if getattr(self, "_scratchpad_loading", False):
            return

        try:
            content = self.query_one("#learning_scratchpad_textarea", TextArea).text
        except Exception:
            return

        if not getattr(self, "_scratchpad_loaded", False) and not content.strip():
            return

        self.session.notes = content
        timer = getattr(self, "_scratchpad_debounce_timer", None)
        if timer:
            timer.cancel()
            self._scratchpad_debounce_timer = None

        if immediate:
            self._async_save_scratchpad(content)
        else:
            loop = asyncio.get_event_loop()
            self._scratchpad_debounce_timer = loop.call_later(
                0.3, lambda: self._async_save_scratchpad(content)
            )

    @work(exclusive=True, group="learning_scratchpad_save")
    async def _async_save_scratchpad(self, content: str) -> None:
        try:
            await self.session.save_notes(content)
        except Exception:
            pass

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "learning_scratchpad_textarea":
            if getattr(self, "_scratchpad_loading", False):
                return
            self._scratchpad_loaded = True
            self._save_scratchpad(immediate=False)

    def action_focus_tutor(self) -> None:
        """Switch copilot tab to Tutor and focus prompt on Ctrl+I."""
        try:
            copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
            copilot_tabs.active = "copilot_tab_ai"
            pane = self.query_one("#learning_copilot_pane")
            if "hidden_sidebar" in pane.classes:
                pane.remove_class("hidden_sidebar")
                self.query_one("#learning_copilot_resizer").remove_class("hidden")
            self.query_one("#chat_input", Input).focus()
        except Exception:
            pass

    def action_focus_notes(self) -> None:
        """Switch copilot tab to Notes and focus editor on Ctrl+N."""
        try:
            copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
            copilot_tabs.active = "copilot_tab_notes"
            pane = self.query_one("#learning_copilot_pane")
            if "hidden_sidebar" in pane.classes:
                pane.remove_class("hidden_sidebar")
                self.query_one("#learning_copilot_resizer").remove_class("hidden")
            self.query_one("#learning_scratchpad_textarea", TextArea).focus()
        except Exception:
            pass

    def action_toggle_copilot(self) -> None:
        """Toggle right copilot sidebar on Ctrl+B."""
        try:
            pane = self.query_one("#learning_copilot_pane")
            resizer = self.query_one("#learning_copilot_resizer")
            if "hidden_sidebar" in pane.classes:
                pane.remove_class("hidden_sidebar")
                resizer.remove_class("hidden")
            else:
                pane.add_class("hidden_sidebar")
                resizer.add_class("hidden")
        except Exception:
            pass

    def _update_theory_tab(
        self, tool_name: Optional[str] = None, recipe_idx: Optional[int] = None
    ) -> None:
        """Render recipe protocol theory, packet wire mechanics, and academic callout."""
        try:
            theory_widget = self.query_one("#theory_markdown_view", Static)
        except Exception:
            return

        tool = tool_name or self.active_tool
        if not tool or not hasattr(self.app, "registry"):
            theory_widget.update(render_markdown("*Select a tool to view its protocol theory.*"))
            return

        tool_data = self.app.registry.get_tool(tool)
        manifest = tool_data.get("manifest") if tool_data else None
        if not manifest:
            theory_widget.update(render_markdown("*No manifest theory available for this tool.*"))
            return

        idx = recipe_idx if recipe_idx is not None else self.active_recipe_idx
        recipes = (
            manifest.learning.recipes if (manifest.learning and manifest.learning.recipes) else []
        )
        active_recipe = (
            recipes[idx]
            if (idx is not None and idx < len(recipes))
            else (recipes[0] if recipes else None)
        )

        md_parts = [f"# {manifest.meta.name.upper()} — Protocol Theory & Deep Dive\n"]
        if manifest.meta.one_line_summary:
            md_parts.append(f"*{manifest.meta.one_line_summary}*\n")

        if active_recipe:
            md_parts.append(f"## Active Recipe: {active_recipe.name}")
            diff = getattr(active_recipe, "difficulty", "Standard") or "Standard"
            flags_str = (
                " ".join(active_recipe.flags) if getattr(active_recipe, "flags", None) else ""
            )
            md_parts.append(f"**Difficulty**: `{diff}` | **Flags**: `{flags_str}`\n")

            theory = getattr(active_recipe, "theory", None)
            if theory:
                if hasattr(theory, "concept") and theory.concept:
                    md_parts.append(f"### Core Concept: {theory.concept}\n")
                if hasattr(theory, "explanation") and theory.explanation:
                    md_parts.append(theory.explanation.strip() + "\n")
                if hasattr(theory, "packet_wire_summary") and theory.packet_wire_summary:
                    md_parts.append(
                        f"### Network Wire & Packet Interaction\n```text\n{theory.packet_wire_summary.strip()}\n```\n"
                    )
                if hasattr(theory, "remediation") and theory.remediation:
                    md_parts.append(
                        f"### Blue-Team Remediation & Defense\n> {theory.remediation.strip()}\n"
                    )
            elif getattr(active_recipe, "description", None):
                md_parts.append(f"### Description\n{active_recipe.description}\n")

        if getattr(manifest.meta, "theory", None):
            md_parts.append("\n---\n")
            md_parts.append(manifest.meta.theory.strip())

        # Target Selection Scope & Operational Precautions Guidance
        from cyguide.engine.preflight import get_tool_target_guidance

        guidance = get_tool_target_guidance(tool)
        if guidance:
            md_parts.append("\n---\n")
            md_parts.append(guidance)

        full_text = "\n".join(md_parts)
        self._raw_theory_content = full_text
        theory_widget.update(render_markdown(full_text))

    def _restore_ai_explanation_pref(self) -> None:
        try:
            if hasattr(self.app, "settings"):
                saved = self.app.settings.get("ai_explanations_enabled", True)
                self.ai_explanations_enabled = bool(saved)
            self._update_ai_toggle_button()
        except Exception:
            pass

    def _update_ai_toggle_button(self) -> None:
        try:
            btn = self.query_one("#toggle_ai_explanation_btn", Button)
            status_lbl = self.query_one("#explanation_status_label", Label)
            try:
                pane = self.query_one("#learning_copilot_pane")
                curr_w = int(
                    pane.styles.width.value
                    if pane.styles.width and pane.styles.width.value is not None
                    else (pane.region.width or 44)
                )
            except Exception:
                curr_w = 44

            compact = curr_w < 36
            if getattr(self, "ai_explanations_enabled", True):
                btn.label = "● ON" if compact else "● AI: ON"
                btn.remove_class("ai_toggle_off")
                btn.add_class("ai_toggle_on")
                status_lbl.update("")
            else:
                btn.label = "○ OFF" if compact else "○ AI: OFF"
                btn.remove_class("ai_toggle_on")
                btn.add_class("ai_toggle_off")
                status_lbl.update(
                    "[dim #a1a1aa]▲ AI paused[/]"
                    if compact
                    else "[dim #a1a1aa]▲ AI briefings paused[/]"
                )
        except Exception:
            pass

    def action_toggle_ai_explanation(self) -> None:
        """Toggle AI explanation generation on or off."""
        self.ai_explanations_enabled = not getattr(self, "ai_explanations_enabled", True)
        if hasattr(self.app, "settings"):
            self.app.settings["ai_explanations_enabled"] = self.ai_explanations_enabled
        if hasattr(self.app, "save_settings"):
            self.app.save_settings({"ai_explanations_enabled": self.ai_explanations_enabled})
        self._update_ai_toggle_button()
        status = "Enabled" if self.ai_explanations_enabled else "Turned Off"
        self.notify(f"AI Explanations {status}", title="AI Tutor")

    async def on_mount(self) -> None:
        """Triggered when the screen is first mounted."""
        try:
            tabs = self.query_one("#copilot_tabs Tabs", Tabs)
            controls = Horizontal(
                Button(
                    "● AI: ON",
                    id="toggle_ai_explanation_btn",
                    classes="pane_action_btn ai_toggle_btn ai_toggle_on",
                ),
                id="copilot_tab_controls",
            )
            await tabs.mount(controls)
        except Exception:
            pass
        self._restore_sidebar_width()
        self._restore_copilot_width()
        self._restore_ai_explanation_pref()
        self._update_model_badge()
        self._sync_copilot_responsive_layout()
        self._sync_sidebar_responsive_layout()
        self._load_scratchpad()
        await self.update_tool_context(force=True)
        self._update_theory_tab()

    async def on_screen_resume(self) -> None:
        """Triggered when the screen is resumed (switched back to)."""
        self._restore_sidebar_width()
        self._restore_copilot_width()
        self._restore_ai_explanation_pref()
        self._update_model_badge()
        self._sync_copilot_responsive_layout()
        self._sync_sidebar_responsive_layout()
        self._load_scratchpad()
        await self.update_tool_context(force=False)
        self._update_theory_tab()

    def on_resize(self, event: events.Resize) -> None:
        """Handle screen resize and keep copilot and sidebar responsive."""
        self._sync_copilot_responsive_layout()
        self._sync_sidebar_responsive_layout()

    def on_resize_handle_resized(self, event: ResizeHandle.Resized) -> None:
        """Handle dynamic pane resizing from drag handle."""
        if event.target_id == "learning_copilot_pane":
            self._sync_copilot_responsive_layout(event.new_size)
        elif event.target_id == "lesson_config_pane":
            self._sync_sidebar_responsive_layout(event.new_size)

    async def update_tool_context(self, force: bool = False) -> None:
        """Refresh the screen content based on the selected tool."""
        try:
            selected_tool = getattr(self.app, "learning_mode_tool", None)
        except Exception:
            selected_tool = None

        if not selected_tool and hasattr(self.app, "registry"):
            all_tools = self.app.registry.get_all_tool_names()
            selected_tool = "nmap" if "nmap" in all_tools else (all_tools[0] if all_tools else None)

        if selected_tool and (force or selected_tool != self.active_tool):
            await self.select_tool(selected_tool)

    async def select_tool(self, tool_name: str):
        # Cache current tool configuration before switching
        if hasattr(self, "active_tool") and self.active_tool and hasattr(self, "flag_editor"):
            try:
                params, target_ip = self.flag_editor.get_command_params()
                self.session.tool_configs[self.active_tool] = {
                    "target": target_ip,
                    "flags": params.get("raw_flags", ""),
                    "recipe_idx": self.active_recipe_idx,
                }
            except Exception:
                pass

        self.active_tool = tool_name
        self.app.learning_mode_tool = tool_name
        context = self.session.select_tool(tool_name)
        if not context:
            return

        # Populate raw output with tool banner and set tutor ready message if no active buffers
        if not self.log_buffer:
            from rich.console import Console

            console = Console(
                theme=CYGUIDE_MARKDOWN_THEME,
                force_terminal=True,
                color_system="truecolor",
                width=80,
            )
            with console.capture() as capture:
                console.print(CyGuideMarkdown(context.welcome_markdown))
            banner_text = capture.get()
            self.query_one("#raw_output_terminal", TerminalStreamPane).update(banner_text)
            self._welcome_banner_active = True
        if not self.explanation_buffer:
            self.query_one("#explanation_text", Static).update(
                render_markdown(DEFAULT_TUTOR_WELCOME_MARKDOWN)
            )

        # 2. Update Header
        self.query_one("#tool_name_header", Label).update(f"◆ {context.tool_name.upper()}")
        self.query_one("#tool_summary_header", Static).update(context.summary)

        # 3. Update Recipes
        recipe_list = self.query_one("#recipe_list", ListView)
        await recipe_list.clear()

        try:
            recipes_deck = self.query_one("#recipes_scroll", RecipeDeck)
            await recipes_deck.load_tool_context(context)
        except Exception:
            pass

        for r in context.recipes:
            await recipe_list.append(RecipeListItem(r, tool_name))

        try:
            self.query_one(
                "#toggle_recipes_btn", Button
            ).label = f"◆ RECIPES ({len(context.recipes)})"
            await self.refresh_graph()
        except Exception:
            pass

        # 4. Update Flag Editor
        container = self.query_one("#flag_editor_container", Vertical)
        await container.query("*").remove()
        self.flag_editor = FlagEditor(tool_name, context.manifest)
        await container.mount(self.flag_editor)

        # 5. Restore or Set Smart Default Target for the Tool
        from cyguide.engine.preflight import DEFAULT_TOOL_TARGETS

        target_default = DEFAULT_TOOL_TARGETS.get(tool_name, "127.0.0.1")
        cached_cfg = self.session.tool_configs.get(tool_name)
        if cached_cfg:
            target_val = cached_cfg.get("target") or target_default
            self.flag_editor.set_target(target_val)
            cached_flags = cached_cfg.get("flags")
            if cached_flags:
                self.flag_editor.set_flags(cached_flags)
            if cached_cfg.get("recipe_idx") is not None:
                self.active_recipe_idx = cached_cfg["recipe_idx"]
        else:
            self.flag_editor.set_target(target_default)

        self.flag_editor.update_preview()
        self._update_theory_tab(tool_name, self.active_recipe_idx)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RecipeListItem):
            # Pre-populate flags from recipe
            self.flag_editor.set_flags(event.item.recipe.flags)
            self.notify(
                f"Loaded recipe: {event.item.recipe.name}", title="Recipe Loaded", timeout=2.0
            )
            try:
                recipe_list = self.query_one("#recipe_list", ListView)
                self.active_recipe_idx = recipe_list.index
            except Exception:
                pass
            self._update_theory_tab(self.active_tool, self.active_recipe_idx)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("ask_recipe_"):
            idx_str = bid.replace("ask_recipe_", "")
            if idx_str.isdigit():
                idx = int(idx_str)
                tool_data = (
                    self.app.registry.get_tool(self.active_tool) if self.active_tool else None
                )
                manifest = tool_data.get("manifest") if tool_data else None
                if (
                    manifest
                    and manifest.learning
                    and manifest.learning.recipes
                    and idx < len(manifest.learning.recipes)
                ):
                    recipe = manifest.learning.recipes[idx]
                    flags_str = (
                        " ".join(recipe.flags)
                        if getattr(recipe, "flags", None)
                        else "(no additional flags)"
                    )
                    desc = getattr(recipe, "description", "") or "No description provided."
                    q = (
                        f"Please provide an educational security briefing on the '{recipe.name}' recipe for `{self.active_tool}` using flags `{flags_str}`. "
                        f"Description: '{desc}'. Explain when to use it, what risks it assesses, and practical audit advice."
                    )
                    try:
                        copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
                        copilot_tabs.active = "copilot_tab_ai"
                        pane = self.query_one("#learning_copilot_pane")
                        if "hidden_sidebar" in pane.classes:
                            pane.remove_class("hidden_sidebar")
                            self.query_one("#learning_copilot_resizer").remove_class("hidden")
                    except Exception:
                        pass
                    self.query_ai_tutor(
                        q, user_display=f"Explain recipe: **{recipe.name}** (`{flags_str}`)"
                    )
        elif bid.startswith("load_recipe_"):
            if self.scan_in_progress:
                await self.stop_scan()
                return
            idx_str = bid.replace("load_recipe_", "")
            if idx_str.isdigit():
                idx = int(idx_str)
                self.active_recipe_idx = idx
                tool_data = (
                    self.app.registry.get_tool(self.active_tool) if self.active_tool else None
                )
                manifest = tool_data.get("manifest") if tool_data else None
                if (
                    manifest
                    and manifest.learning
                    and manifest.learning.recipes
                    and idx < len(manifest.learning.recipes)
                ):
                    recipe = manifest.learning.recipes[idx]
                    self.flag_editor.set_flags(recipe.flags)
                    try:
                        recipe_list = self.query_one("#recipe_list", ListView)
                        if idx < len(recipe_list.children):
                            recipe_list.index = idx
                    except Exception:
                        pass
                    self.notify(f"Loaded recipe: {recipe.name}", title="Recipe Loaded", timeout=2.0)
                    self._update_theory_tab(self.active_tool, idx)
                    self.run_scan()
        elif bid == "sidebar_ask_btn":
            try:
                params, target_ip = self.flag_editor.get_command_params()
                flags_used = params.get("raw_flags", "")
                cmd_str = (
                    f"{self.active_tool or 'scanner'} {flags_used} {target_ip}".strip().replace(
                        "  ", " "
                    )
                )
                q = (
                    f"Please explain what the command `{cmd_str}` does in plain English. "
                    f"Break down each flag, its expected scanner behavior, and its cybersecurity testing purpose."
                )
                try:
                    copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
                    copilot_tabs.active = "copilot_tab_ai"
                    pane = self.query_one("#learning_copilot_pane")
                    if "hidden_sidebar" in pane.classes:
                        pane.remove_class("hidden_sidebar")
                        self.query_one("#learning_copilot_resizer").remove_class("hidden")
                except Exception:
                    pass
                self.query_ai_tutor(q, user_display=f"Explain command: `{cmd_str}`")
            except ValueError as e:
                self.notify(str(e), severity="error")
        elif bid == "run_btn":
            self.run_scan()
        elif bid == "stop_btn":
            await self.stop_scan()
        elif bid == "ask_btn":
            self.submit_chat_question()
        elif bid == "toggle_ai_explanation_btn":
            self.action_toggle_ai_explanation()
        elif bid == "clear_explanation_btn":
            self.clear_explanation()
        elif bid == "clear_notes_btn":
            try:
                self.query_one("#learning_scratchpad_textarea", TextArea).load_text("")
                self._save_scratchpad(immediate=True)
                self.notify("Notes cleared", title="Lab Notes")
            except Exception:
                pass
        elif bid == "copy_notes_btn":
            self.action_copy_notes()
        elif bid == "export_notes_btn":
            self.action_export_notes()
        elif bid == "clear_output_btn":
            self.clear_output()
        elif bid == "copy_explanation_btn":
            self.action_copy_explanation()
        elif bid == "copy_output_btn":
            self.action_copy_output()
        elif bid == "copy_theory_btn":
            self.action_copy_theory()
        elif bid == "save_checkpoint_btn":
            await self.action_save_checkpoint()
        elif bid == "load_checkpoint_btn":
            await self.action_load_checkpoint()
        elif bid == "reset_session_btn":
            await self.action_reset_session()
        elif bid == "toggle_recipes_btn":
            self.action_show_recipes_view()
        elif bid == "toggle_graph_btn":
            self.action_show_graph_view()

    def action_copy_notes(self) -> None:
        """Copy the current lab notes to system clipboard."""
        try:
            textarea = self.query_one("#learning_scratchpad_textarea", TextArea)
            text = textarea.text.strip()
        except Exception:
            text = ""
        if not text:
            self.notify("No notes to copy.", severity="warning", title="Lab Notes")
            return
        try:
            self.app.copy_to_clipboard(text)
            self.notify("Notes copied to clipboard!", title="Clipboard")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_export_notes(self) -> None:
        """Export lab notes to a markdown file in the exports directory."""
        try:
            textarea = self.query_one("#learning_scratchpad_textarea", TextArea)
            content = textarea.text.strip()
        except Exception:
            content = ""
        if not content:
            self.notify(
                "Notes are empty. Nothing to export.", severity="warning", title="Lab Notes"
            )
            return

        try:
            exports_dir = (
                self.app.get_exports_dir()
                if hasattr(self.app, "get_exports_dir")
                else get_default_exports_dir()
            )
            os.makedirs(exports_dir, mode=0o700, exist_ok=True)

            target_slug = ""
            if hasattr(self, "session") and getattr(self.session, "primary_target", None):
                target_slug = re.sub(
                    r"[^a-zA-Z0-9_\-]",
                    "_",
                    self.session.primary_target.replace("http://", "")
                    .replace("https://", "")
                    .strip("/"),
                )
            if not target_slug and hasattr(self, "flag_editor"):
                try:
                    _, target_ip = self.flag_editor.get_command_params()
                    if target_ip:
                        target_slug = re.sub(
                            r"[^a-zA-Z0-9_\-]",
                            "_",
                            target_ip.replace("http://", "").replace("https://", "").strip("/"),
                        )
                except Exception:
                    pass

            tool_name = self.active_tool or "lab"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"notes_{target_slug}_{timestamp}.md"
                if target_slug
                else f"notes_{tool_name}_{timestamp}.md"
            )
            dest_path = os.path.join(exports_dir, filename)

            # Secure atomic export via deep SessionReportService
            from cyguide.engine.reporter import SessionReportService

            SessionReportService.export_text_file(content + "\n", dest_path)

            try:
                self.app.copy_to_clipboard(content)
            except Exception:
                pass

            self.notify(
                f"Notes exported to {filename}", title="Notes Exported", severity="information"
            )
        except Exception as e:
            self.notify(f"Failed to export notes: {e}", severity="error", title="Export Failed")

    def action_copy_theory(self) -> None:
        """Copy the active protocol theory and wire analysis to clipboard."""
        text = getattr(self, "_raw_theory_content", "") or ""
        if not text.strip():
            self.notify("No theory content to copy.", severity="warning")
            return
        try:
            self.app.copy_to_clipboard(text.strip())
            self.notify("Theory notes copied to clipboard!", title="Clipboard")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_copy_explanation(self) -> None:
        """Copy the current explanation text to system clipboard."""
        text = self.explanation_buffer.strip()
        if not text:
            self.notify("No explanation text to copy.", severity="warning")
            return
        try:
            self.app.copy_to_clipboard(text)
            self.notify("Explanation copied to clipboard! (Ctrl+Y)", title="Clipboard")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_copy_output(self) -> None:
        """Copy the raw terminal output to system clipboard."""
        try:
            term = self.query_one("#raw_output_terminal", TerminalStreamPane)
            text = term.get_text().strip()
        except Exception:
            text = "".join(self.log_buffer).strip()
        if not text:
            self.notify("Raw terminal output is empty.", severity="warning")
            return
        try:
            self.app.copy_to_clipboard(text)
            self.notify("Terminal output copied to clipboard!", title="Clipboard")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_copy_selection(self) -> None:
        """Copy selected text to clipboard on Ctrl+C."""
        selected = self.get_selected_text()
        if selected and selected.strip():
            try:
                self.app.copy_to_clipboard(selected.strip())
                self.notify("Selected text copied to clipboard!", title="Clipboard")
                return
            except Exception as e:
                self.notify(f"Selection copy failed: {e}", severity="error")
                return
        self.action_copy_explanation()

    async def action_save_checkpoint(self) -> None:
        """Prompt to save current universal learning laboratory state to a .cyglab archive."""
        tool_name = self.active_tool or "lab"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        target = ""
        flags = ""
        try:
            params, target_ip = self.flag_editor.get_command_params()
            target = target_ip
            flags = params.get("raw_flags", "")
            if self.active_tool:
                self.session.tool_configs[self.active_tool] = {
                    "target": target,
                    "flags": flags,
                    "recipe_idx": self.active_recipe_idx,
                }
        except Exception:
            pass

        clean_slug = (
            re.sub(
                r"[^a-zA-Z0-9_\-]",
                "_",
                target.replace("http://", "").replace("https://", "").strip("/"),
            )
            if target
            else ""
        )
        if clean_slug:
            default_name = f"lab_{clean_slug}_{timestamp}.cyglab"
        else:
            default_name = f"lab_session_{timestamp}.cyglab"

        try:
            notes = self.query_one("#learning_scratchpad_textarea", TextArea).text
            self.session.notes = notes
        except Exception:
            notes = getattr(self.session, "notes", "")

        findings_count = 0
        if hasattr(self.session, "store") and self.session.store:
            try:
                findings_count = await self.session.store.count_nodes()
            except Exception:
                pass

        tools_used = sorted(list(self.session.tools_used))
        if self.active_tool and self.active_tool not in tools_used:
            tools_used.append(self.active_tool)

        async def _on_save_dismiss(filename: Optional[str]) -> None:
            if not filename:
                return
            checkpoints_dir = (
                self.app.get_checkpoints_dir()
                if hasattr(self.app, "get_checkpoints_dir")
                else get_default_checkpoints_dir()
            )
            checkpoint_path = os.path.join(checkpoints_dir, filename)

            model_name = ""
            try:
                badge_text = str(self.query_one("#copilot_model_badge", Label).renderable)
                model_name = badge_text.strip("[]")
            except Exception:
                pass

            try:
                await self.session.save_checkpoint(
                    checkpoint_path=checkpoint_path,
                    target=target,
                    flags=flags,
                    model_name=model_name,
                )
                self.notify(
                    f"Lab session checkpoint saved: {filename}",
                    title="Checkpoint Saved",
                    timeout=5.0,
                )
            except Exception as e:
                self.notify(f"Failed to save checkpoint: {str(e)}", severity="error", timeout=6.0)

        self.app.push_screen(
            SaveCheckpointModal(
                default_name=default_name,
                tool_name=tool_name,
                target=target,
                tools_used=tools_used,
                findings_count=findings_count,
            ),
            callback=_on_save_dismiss,
        )

    async def action_load_checkpoint(self) -> None:
        """Prompt to load a saved laboratory session from a .cyglab archive."""
        checkpoints_dir = (
            self.app.get_checkpoints_dir()
            if hasattr(self.app, "get_checkpoints_dir")
            else get_default_checkpoints_dir()
        )

        async def _on_load_dismiss(filepath: Optional[str]) -> None:
            if not filepath:
                return
            try:
                data = await self.session.load_checkpoint(filepath)
                tool_name = data.get("active_tool") or data.get("tool_name")
                if tool_name:
                    await self.select_tool(tool_name)

                recipe_idx = data.get("recipe_idx")
                if recipe_idx is not None and recipe_idx >= 0:
                    self.select_recipe(recipe_idx)

                # Restore input fields
                if data.get("target") or data.get("flags"):
                    try:
                        if hasattr(self, "flag_editor"):
                            if data.get("target"):
                                self.flag_editor.set_target(data["target"])
                            if data.get("flags"):
                                self.flag_editor.set_flags(data["flags"])
                        else:
                            self.query_one("#target_input", Input).value = data.get("target", "")
                            self.query_one("#flags_input", Input).value = data.get("flags", "")
                    except Exception:
                        pass

                # Restore notes textarea
                try:
                    notes = data.get("notes", "")
                    self.query_one("#learning_scratchpad_textarea", TextArea).load_text(notes)
                    self._save_scratchpad(immediate=True)
                except Exception:
                    pass

                # Restore stdout terminal
                log_buffer = data.get("log_buffer", [])
                self.clear_output()
                self.session.log_buffer = list(log_buffer)
                terminal = self.query_one("#raw_output_terminal", TerminalStreamPane)
                terminal.clear()
                terminal.write_lines(log_buffer)

                # Restore explanation
                exp_text = data.get("explanation_buffer", "")
                self.explanation_buffer = exp_text
                try:
                    self.query_one("#explanation_text", Static).update(
                        render_markdown(exp_text or "*No previous explanation recorded.*")
                    )
                except Exception:
                    pass

                fname = os.path.basename(filepath)
                await self.refresh_graph()
                tools_used = data.get("tools_used", [])
                tools_summary = f" ({len(tools_used)} tools)" if len(tools_used) > 1 else ""
                self.notify(
                    f"Restored lab session: {fname}{tools_summary}",
                    title="Session Loaded",
                    timeout=5.0,
                )
            except Exception as e:
                self.notify(f"Failed to load checkpoint: {str(e)}", severity="error", timeout=6.0)

        self.app.push_screen(
            LoadCheckpointModal(checkpoints_dir=checkpoints_dir),
            callback=_on_load_dismiss,
        )

    async def action_reset_session(self) -> None:
        """Prompt confirmation and reset all session state, logs, notes, AI dialogues, and graph findings."""

        async def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            await self._do_reset_session()

        self.app.push_screen(
            ConfirmationDialog(
                "Reset lab session? This will wipe all terminal logs, notes, AI dialogue, and discovered graph entities.",
                confirm_label="Reset Session",
                cancel_label="Cancel",
                is_destructive=True,
            ),
            callback=_on_confirm,
        )

    async def _do_reset_session(self) -> None:
        """Execute complete wipe and re-initialization of learning session."""
        # 1. Reset underlying engine session state and graph findings
        await self.session.reset_session()

        # 2. Reset UI state variables
        self.log_buffer = []
        self.explanation_buffer = ""
        self.active_recipe_idx = None
        self._welcome_banner_active = False

        # 3. Clear raw output terminal and re-show tool welcome banner
        output_terminal = self.query_one("#raw_output_terminal", TerminalStreamPane)
        output_terminal.clear()
        if self.active_tool:
            context = self.session.select_tool(self.active_tool)
            if context:
                from rich.console import Console

                console = Console(
                    theme=CYGUIDE_MARKDOWN_THEME,
                    force_terminal=True,
                    color_system="truecolor",
                    width=80,
                )
                with console.capture() as capture:
                    console.print(CyGuideMarkdown(context.welcome_markdown))
                output_terminal.update(capture.get())
                self._welcome_banner_active = True

        # 4. Clear explanation pane and restore AI tutor ready message
        try:
            self.query_one("#explanation_text", Static).update(
                render_markdown(DEFAULT_TUTOR_WELCOME_MARKDOWN)
            )
            self.query_one("#explanation_status_label", Label).update("")
        except Exception:
            pass

        # 5. Clear notes scratchpad
        try:
            self.query_one("#learning_scratchpad_textarea", TextArea).load_text("")
            self._save_scratchpad(immediate=True)
        except Exception:
            pass

        # 6. Reset FlagEditor to tool defaults
        if self.active_tool:
            try:
                tool_data = self.app.registry.get_tool(self.active_tool)
                manifest = tool_data.get("manifest") if tool_data else None
                container = self.query_one("#flag_editor_container", Vertical)
                await container.query("*").remove()
                self.flag_editor = FlagEditor(self.active_tool, manifest)
                await container.mount(self.flag_editor)
            except Exception:
                pass

        # 7. Reset recipe deck highlight
        try:
            recipes_deck = self.query_one("#recipes_scroll", RecipeDeck)
            recipes_deck.set_active_recipe_state(None, is_running=False)
        except Exception:
            pass

        # 8. Refresh graph browser (now 0 nodes)
        await self.refresh_graph()

        # 9. Switch sidebar view back to recipes
        self.action_show_recipes_view()

        # 10. Notify user
        self.notify(
            "Session reset. Cleared all logs, notes, AI dialogues, and graph entities.",
            title="Session Reset",
            timeout=3.5,
        )

    def clear_explanation(self) -> None:
        self.explanation_buffer = ""
        self.query_one("#explanation_text", Static).update(
            render_markdown("*Explanation cleared.*")
        )
        try:
            self.query_one("#explanation_status_label", Label).update("")
        except Exception:
            pass
        self.set_focus(None)
        self.notify("Explanation cleared")

    def clear_output(self) -> None:
        self._welcome_banner_active = False
        self.log_buffer = []
        self.query_one("#raw_output_terminal", TerminalStreamPane).clear()
        self.set_focus(None)
        self.notify("Raw output cleared")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat_input":
            self.submit_chat_question()

    @work(exclusive=True, group="learning_chat")
    async def submit_chat_question(self) -> None:
        chat_input = self.query_one("#chat_input", Input)
        raw_input = chat_input.value.strip()
        if not raw_input:
            return

        chat_input.value = ""

        try:
            copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
            copilot_tabs.active = "copilot_tab_ai"
            pane = self.query_one("#learning_copilot_pane")
            if "hidden_sidebar" in pane.classes:
                pane.remove_class("hidden_sidebar")
                self.query_one("#learning_copilot_resizer").remove_class("hidden")
        except Exception:
            pass

        explanation_pane = self.query_one("#explanation_text", Static)
        explanation_scroll = self.query_one("#explanation_scroll", VerticalScroll)

        flags_val = ""
        try:
            params, _ = self.flag_editor.get_command_params()
            flags_val = params.get("raw_flags", "")
        except Exception:
            flags_val = ""

        # Delegate command parsing to LearningSession deep module
        cmd_result = self.session.evaluate_slash_command(raw_input, active_flags_str=flags_val)
        if cmd_result and cmd_result.handled:
            if cmd_result.action == "clear":
                self.clear_explanation()
                return
            if cmd_result.action == "copy":
                self.action_copy_explanation()
                return
            if cmd_result.action == "exit":
                self.app.switch_screen("dashboard")
                return
            if cmd_result.action == "save_checkpoint":
                await self.action_save_checkpoint()
                return
            if cmd_result.action == "load_checkpoint":
                await self.action_load_checkpoint()
                return
            if cmd_result.action == "switch_recipes":
                try:
                    tabs = self.query_one("#learning_tabs", TabbedContent)
                    tabs.active = "tab_recipes"
                    self.notify("Switched to Recipes tab", title="Recipes")
                except Exception:
                    pass
            elif cmd_result.action == "toggle_ai":
                if hasattr(self.app, "settings"):
                    self.app.settings["ai_explanations_enabled"] = self.ai_explanations_enabled
                if hasattr(self.app, "save_settings"):
                    self.app.save_settings(
                        {"ai_explanations_enabled": self.ai_explanations_enabled}
                    )
                self._update_ai_toggle_button()
                status = "Enabled" if self.ai_explanations_enabled else "Turned Off"
                self.notify(f"AI Explanations {status}", title="AI Tutor")

            if cmd_result.message:
                self.explanation_buffer = (
                    self.explanation_buffer + f"\n\n***\n\n{cmd_result.message}\n"
                    if self.explanation_buffer
                    else f"{cmd_result.message}\n"
                )
                explanation_pane.update(render_markdown(self.explanation_buffer))
                explanation_scroll.scroll_end(animate=False)
            return

        # If slash command produced a generated prompt (e.g. /summary, /flags), or is standard text
        question = cmd_result.message if cmd_result else raw_input
        worker = self.query_ai_tutor(question, user_display=raw_input)
        await worker.wait()

    @work(exclusive=True, group="query_ai_tutor")
    async def query_ai_tutor(self, question: str, user_display: Optional[str] = None) -> None:
        try:
            copilot_tabs = self.query_one("#copilot_tabs", TabbedContent)
            copilot_tabs.active = "copilot_tab_ai"
            pane = self.query_one("#learning_copilot_pane")
            if "hidden_sidebar" in pane.classes:
                pane.remove_class("hidden_sidebar")
                self.query_one("#learning_copilot_resizer").remove_class("hidden")
        except Exception:
            pass

        explanation_pane = self.query_one("#explanation_text", Static)
        explanation_scroll = self.query_one("#explanation_scroll", VerticalScroll)

        display_prompt = user_display or question
        now_ts = datetime.now().strftime("%H:%M:%S")
        card_header = f"### 💬 Question · `{now_ts}`\n> **{display_prompt}**\n\n"
        base_buffer = (
            self.explanation_buffer + f"\n\n***\n\n{card_header}"
            if self.explanation_buffer
            else card_header
        )

        if not getattr(self, "ai_explanations_enabled", True):
            try:
                self.query_one("#explanation_status_label", Label).update(
                    "[#f59e0b]▲ AI Tutor is turned OFF (click AI: OFF to enable)[/]"
                )
            except Exception:
                pass
            self.notify(
                "AI Tutor is turned off. Toggle it ON to ask questions.", severity="warning"
            )
            return

        self.explanation_buffer = base_buffer + "*[AI Tutor is thinking...]*"
        try:
            explanation_pane.update(render_markdown(self.explanation_buffer))
        except Exception:
            pass
        explanation_scroll.scroll_end(animate=False)

        import time

        last_update = 0.0
        try:
            async for update in self.session.stream_tutor_response(question):
                self.explanation_buffer = base_buffer + update.accumulated
                now = time.time()
                if now - last_update > 0.08:
                    try:
                        explanation_pane.update(render_markdown(self.explanation_buffer))
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass
                    if explanation_scroll.is_vertical_scroll_end or (
                        explanation_scroll.max_scroll_y - explanation_scroll.scroll_offset.y <= 2
                    ):
                        explanation_scroll.scroll_end(animate=False)
                    last_update = now
                if update.is_error:
                    self.notify("Error getting explanation", severity="error")
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                explanation_pane.update(render_markdown(self.explanation_buffer))
            except Exception:
                pass
            was_at_end = explanation_scroll.is_vertical_scroll_end or (
                explanation_scroll.max_scroll_y - explanation_scroll.scroll_offset.y <= 2
            )
            if was_at_end:
                explanation_scroll.scroll_end(animate=False)

    def _strip_scanner_noise(self, raw_text: str) -> str:
        """Filter out repetitive scanner banner headers, ASCII art, and progress bars before LLM prompting."""
        from cyguide.engine.explainer import ExplanationTutor

        return ExplanationTutor.strip_scanner_noise(raw_text)

    async def _extract_structured_findings(
        self, store: Optional[Any] = None, session_id: Optional[str] = None
    ) -> tuple[str, str]:
        """Query GraphStore for session nodes via LearningSession."""
        return await self.session.extract_structured_findings(store=store, session_id=session_id)

    async def stop_scan(self):
        """Terminate the running tool."""
        await self.session.stop_scan()
        try:
            term = self.query_one("#raw_output_terminal", TerminalStreamPane)
            term.write("\n[!] Scan stopped by user.\n")
            term.flush()
        except Exception:
            pass
        self.reset_ui_after_run()

    def reset_ui_after_run(self):
        """Restore button states after scan finishes or stops."""
        self.scan_in_progress = False
        try:
            run_btn = self.query_one("#run_btn", Button)
            stop_btn = self.query_one("#stop_btn", Button)
            run_btn.display = True
            stop_btn.display = False
            run_btn.disabled = False
            stop_btn.disabled = True
        except Exception:
            pass
        try:
            sidebar_ask_btn = self.query_one("#sidebar_ask_btn", Button)
            sidebar_ask_btn.display = True
            sidebar_ask_btn.disabled = False
        except Exception:
            pass
        try:
            self.query_one("#recipes_scroll", RecipeDeck).reset_buttons()
        except Exception:
            pass
        self.active_recipe_idx = None

    def _handle_preflight_required(self, event: PreflightRequiredEvent) -> None:
        """Present the preflight modal when dependencies or parameters require attention."""

        def _on_preflight_closed(result: Optional[PreflightModalResult]) -> None:
            if not result or not result.confirmed:
                return
            if result.target != event.target:
                self.flag_editor.set_target(result.target)
            if result.flags != event.flags:
                self.flag_editor.set_flags(result.flags)
            self._skip_preflight_once = True
            try:
                self.run_scan()
            finally:
                self._skip_preflight_once = False

        self.app.push_screen(
            PreflightModal(
                report=event.report,
                verifier=event.verifier,
                active_tool=self.active_tool or "tool",
                initial_target=event.target,
                initial_flags=event.flags,
                recipe_idx=event.recipe_idx,
            ),
            _on_preflight_closed,
        )

    @work(exclusive=True)
    async def run_scan(self):
        if self.scan_in_progress:
            return

        try:
            params, target_ip = self.flag_editor.get_command_params()
        except ValueError as e:
            self.notify(str(e), severity="error")
            return

        raw_flags_str = params.get("raw_flags", "")
        active_flags_set = set(raw_flags_str.split())

        output_terminal = self.query_one("#raw_output_terminal", TerminalStreamPane)
        explainer_pane = self.query_one("#explanation_text", Static)
        explainer_scroll = self.query_one("#explanation_scroll", VerticalScroll)

        from cyguide.engine.gateway import ActionValidationError
        from cyguide.engine.learning import (
            BriefingChunkEvent,
            BriefingCompletedEvent,
            BriefingStartedEvent,
            PreflightRequiredEvent,
            ScanCompletedEvent,
            ScanOutputChunkEvent,
            ScanStartedEvent,
        )

        try:
            base_expl_buffer = self.explanation_buffer
            briefing_text = ""
            import time

            last_expl_update = time.time()

            async for event in self.session.run_scan(
                target=target_ip,
                flags_used=raw_flags_str,
                selected_flags=active_flags_set,
                recipe_idx=self.active_recipe_idx,
                skip_preflight=getattr(self, "_skip_preflight_once", False),
            ):
                if isinstance(event, PreflightRequiredEvent):
                    self._handle_preflight_required(event)
                    return

                elif isinstance(event, ScanStartedEvent):
                    self.scan_in_progress = True
                    run_btn = self.query_one("#run_btn", Button)
                    stop_btn = self.query_one("#stop_btn", Button)
                    try:
                        sidebar_ask_btn = self.query_one("#sidebar_ask_btn", Button)
                        sidebar_ask_btn.display = False
                        sidebar_ask_btn.disabled = True
                    except Exception:
                        pass
                    run_btn.display = False
                    stop_btn.display = True
                    stop_btn.disabled = False
                    try:
                        self.query_one("#recipes_scroll", RecipeDeck).set_active_recipe_state(
                            self.active_recipe_idx, is_running=True
                        )
                    except Exception:
                        pass

                    if getattr(self, "_welcome_banner_active", False) or event.run_count <= 1:
                        output_terminal.clear()
                        self._welcome_banner_active = False
                    output_terminal.write(event.header_text)
                    output_terminal.flush()
                    if getattr(self, "ai_explanations_enabled", True):
                        expl_header = (
                            f"\n\n***\n\n## ▶ Run #{event.run_count} · `{event.timestamp}`\n> `{event.cmd_str}`\n\n"
                            if self.explanation_buffer
                            else f"## ▶ Run #{event.run_count} · `{event.timestamp}`\n> `{event.cmd_str}`\n\n"
                        )
                        self.explanation_buffer += expl_header
                        try:
                            explainer_pane.update(
                                render_markdown(self.explanation_buffer + "\n*[Running scan...]*")
                            )
                        except Exception:
                            pass
                        explainer_scroll.scroll_end(animate=False)
                        base_expl_buffer = self.explanation_buffer

                elif isinstance(event, ScanOutputChunkEvent):
                    output_terminal.write(event.chunk)
                    await asyncio.sleep(0)

                elif isinstance(event, ScanCompletedEvent):
                    output_terminal.write(event.footer_text)
                    output_terminal.flush()
                    await self.refresh_graph()
                    try:
                        self.query_one("#chat_input", Input).disabled = False
                        self.query_one("#ask_btn", Button).disabled = False
                    except Exception:
                        pass

                elif isinstance(event, BriefingStartedEvent):
                    try:
                        self.query_one("#explanation_status_label", Label).update("")
                    except Exception:
                        pass
                    try:
                        explainer_pane.update(render_markdown(base_expl_buffer + event.placeholder))
                    except Exception:
                        pass
                    explainer_scroll.scroll_end(animate=False)

                elif isinstance(event, BriefingChunkEvent):
                    briefing_text += event.chunk
                    self.explanation_buffer = base_expl_buffer + briefing_text
                    now = time.time()
                    if now - last_expl_update > 0.08:
                        try:
                            explainer_pane.update(render_markdown(self.explanation_buffer))
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            pass
                        was_at_end = explainer_scroll.is_vertical_scroll_end or (
                            explainer_scroll.max_scroll_y - explainer_scroll.scroll_offset.y <= 2
                        )
                        if was_at_end:
                            explainer_scroll.scroll_end(animate=False)
                        last_expl_update = time.time()
                    await asyncio.sleep(0)

                elif isinstance(event, BriefingCompletedEvent):
                    self.explanation_buffer = base_expl_buffer + event.full_text
                    try:
                        explainer_pane.update(render_markdown(self.explanation_buffer))
                    except Exception:
                        pass
                    explainer_scroll.scroll_end(animate=False)

            if not getattr(self, "ai_explanations_enabled", True):
                try:
                    self.query_one("#explanation_status_label", Label).update(
                        "[#f59e0b]▲ AI explanation is turned OFF — scan briefing skipped[/]"
                    )
                except Exception:
                    pass
                self.notify(
                    "AI Explanation is turned off. Scan briefing skipped.", severity="information"
                )

        except ActionValidationError as e:
            self.notify(f"Security Policy: {str(e)}", severity="error")
            err_msg = f"\n[!] Policy Violation: {str(e)}\n"
            self.session.log_buffer.append(err_msg)
            output_terminal.write(err_msg)
            output_terminal.flush()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            err_msg = f"\n[!] Error: {str(e)}\n"
            self.session.log_buffer.append(err_msg)
            output_terminal.write(err_msg)
            output_terminal.flush()
        finally:
            self.reset_ui_after_run()

    def action_show_shortcuts(self) -> None:
        self.app.action_show_hotkeys()

    def action_nav_tool_browser(self) -> None:
        if self.active_tool:
            self.app.learning_mode_tool = self.active_tool
        self.app.switch_screen("tool_browser")

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#lesson_config_pane")
        resizer = None
        try:
            resizer = self.query_one("#learning_sidebar_resizer")
        except Exception:
            pass

        is_collapsing = not sidebar.has_class("collapsed")
        target_w = getattr(self, "_saved_sidebar_width", 32)
        if not is_collapsing:
            if hasattr(self.app, "settings"):
                target_w = self.app.settings.get("learning_sidebar_width", target_w)
        else:
            curr_val = getattr(sidebar.styles.width, "value", None)
            if curr_val and curr_val > 0:
                self._saved_sidebar_width = int(curr_val)

        is_animating = getattr(self.app, "animations_enabled", False)
        if is_animating:
            if is_collapsing:
                curr_w = int(sidebar.region.width or target_w)
                sidebar.styles.width = curr_w
                if resizer:
                    resizer.add_class("hidden")

                def _on_collapse_complete() -> None:
                    sidebar.add_class("collapsed")

                sidebar.styles.animate(
                    "width",
                    value=0,
                    duration=0.2,
                    easing="in_out_cubic",
                    on_complete=_on_collapse_complete,
                )
            else:
                sidebar.remove_class("collapsed")
                sidebar.styles.width = 0
                if resizer:
                    resizer.remove_class("hidden")
                sidebar.styles.animate(
                    "width",
                    value=target_w,
                    duration=0.2,
                    easing="in_out_cubic",
                )
        else:
            sidebar.set_class(is_collapsing, "collapsed")
            sidebar.display = not is_collapsing
            if resizer:
                resizer.set_class(is_collapsing, "hidden")
                resizer.display = not is_collapsing
        self.refresh(layout=True)

    def action_show_recipes_view(self) -> None:
        """Switch left sidebar to workflow recipes view."""
        try:
            self.query_one("#recipe_list", ListView).remove_class("hidden")
            self.query_one("#learning_entity_browser", EntityBrowser).add_class("hidden")
            self.query_one("#toggle_recipes_btn", Button).add_class("active_view")
            self.query_one("#toggle_graph_btn", Button).remove_class("active_view")
        except Exception:
            pass

    def action_show_graph_view(self) -> None:
        """Switch left sidebar to entity knowledge graph view."""
        try:
            self.query_one("#recipe_list", ListView).add_class("hidden")
            self.query_one("#learning_entity_browser", EntityBrowser).remove_class("hidden")
            self.query_one("#toggle_graph_btn", Button).add_class("active_view")
            self.query_one("#toggle_recipes_btn", Button).remove_class("active_view")
            self.run_worker(self.refresh_graph())
        except Exception:
            pass

    def action_toggle_sidebar_graph(self) -> None:
        """Toggle between recipes view and graph view in the left sidebar."""
        try:
            browser = self.query_one("#learning_entity_browser", EntityBrowser)
            if "hidden" in browser.classes:
                self.action_show_graph_view()
            else:
                self.action_show_recipes_view()
        except Exception:
            pass

    async def refresh_graph(self) -> None:
        """Fetch latest graph findings from session and refresh entity browser."""
        try:
            browser = self.query_one("#learning_entity_browser", EntityBrowser)
            snapshot = await self.session.get_graph_snapshot()
            await browser.refresh_entities(snapshot)
            node_cnt = len(snapshot.get("nodes", []))
            toggle_btn = self.query_one("#toggle_graph_btn", Button)
            toggle_btn.label = f"◈ GRAPH ({node_cnt})"
        except Exception:
            pass

    async def on_tree_node_selected(self, event: EntityBrowser.NodeSelected) -> None:
        """Handle entity selection from learning mode graph browser."""
        if not event.node or not event.node.data:
            return
        node_id = event.node.data.get("id")
        schema_type = event.node.data.get("type", "")
        if not node_id:
            return

        try:
            snapshot = await self.session.get_graph_snapshot()
            nodes = snapshot.get("nodes", [])
            selected_node = next((n for n in nodes if n.get("id") == node_id), None)
            if not selected_node:
                return

            pik_raw = selected_node.get("pik_json", "{}")
            pik = json.loads(pik_raw) if isinstance(pik_raw, str) else (pik_raw or {})
            target_val = ""
            if "ip" in pik:
                target_val = str(pik["ip"])
            elif "domain" in pik:
                target_val = str(pik["domain"])
            elif "host" in pik:
                target_val = str(pik["host"])
            elif "url" in pik:
                target_val = str(pik["url"])
            elif "name" in pik:
                target_val = str(pik["name"])

            if target_val:
                try:
                    self.query_one("#target_input", Input).value = target_val
                    self.notify(
                        f"Target set to: {target_val} ({schema_type})",
                        title="Entity Selected",
                        timeout=2.5,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def action_shrink_sidebar(self) -> None:
        try:
            pane = self.query_one("#lesson_config_pane")
            curr = int(
                pane.styles.width.value
                if pane.styles.width and pane.styles.width.value
                else (pane.region.width or 32)
            )
            new_w = max(20, curr - 4)
            pane.add_class("-fast-stepping")
            pane.styles.width = new_w
            self._sync_sidebar_responsive_layout(new_w)
            if hasattr(self.app, "settings"):
                self.app.settings["learning_sidebar_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_sidebar_width": new_w})
            try:
                self.set_timer(0.2, lambda: pane.remove_class("-fast-stepping"))
            except Exception:
                pass
        except Exception:
            pass

    def action_expand_sidebar(self) -> None:
        try:
            pane = self.query_one("#lesson_config_pane")
            curr = int(
                pane.styles.width.value
                if pane.styles.width and pane.styles.width.value
                else (pane.region.width or 32)
            )
            new_w = min(70, curr + 4)
            pane.add_class("-fast-stepping")
            pane.styles.width = new_w
            self._sync_sidebar_responsive_layout(new_w)
            if hasattr(self.app, "settings"):
                self.app.settings["learning_sidebar_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_sidebar_width": new_w})
            try:
                self.set_timer(0.2, lambda: pane.remove_class("-fast-stepping"))
            except Exception:
                pass
        except Exception:
            pass

    def action_shrink_copilot(self) -> None:
        """Shrink right Copilot sidebar width smoothly."""
        try:
            pane = self.query_one("#learning_copilot_pane")
            curr = int(
                pane.styles.width.value
                if pane.styles.width and pane.styles.width.value
                else (pane.region.width or 44)
            )
            new_w = max(26, curr - 4)
            pane.add_class("-fast-stepping")
            pane.styles.width = new_w
            self._sync_copilot_responsive_layout(new_w)
            if hasattr(self.app, "settings"):
                self.app.settings["learning_copilot_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_copilot_width": new_w})
            try:
                self.set_timer(0.2, lambda: pane.remove_class("-fast-stepping"))
            except Exception:
                pass
        except Exception:
            pass

    def action_expand_copilot(self) -> None:
        """Expand right Copilot sidebar width smoothly."""
        try:
            pane = self.query_one("#learning_copilot_pane")
            curr = int(
                pane.styles.width.value
                if pane.styles.width and pane.styles.width.value
                else (pane.region.width or 44)
            )
            new_w = min(80, curr + 4)
            pane.add_class("-fast-stepping")
            pane.styles.width = new_w
            self._sync_copilot_responsive_layout(new_w)
            if hasattr(self.app, "settings"):
                self.app.settings["learning_copilot_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_copilot_width": new_w})
            try:
                self.set_timer(0.2, lambda: pane.remove_class("-fast-stepping"))
            except Exception:
                pass
        except Exception:
            pass

    ORDERED_TABS = ["tab_recipes", "tab_output", "tab_theory"]

    def action_toggle_tab(self) -> None:
        self.action_next_tab()

    def action_next_tab(self) -> None:
        try:
            tabs = self.query_one("#learning_tabs", TabbedContent)
            curr = tabs.active
            if curr in self.ORDERED_TABS:
                curr_idx = self.ORDERED_TABS.index(curr)
                next_idx = (curr_idx + 1) % len(self.ORDERED_TABS)
                tabs.active = self.ORDERED_TABS[next_idx]
            else:
                tabs.active = self.ORDERED_TABS[0]
        except Exception:
            pass

    def action_prev_tab(self) -> None:
        try:
            tabs = self.query_one("#learning_tabs", TabbedContent)
            curr = tabs.active
            if curr in self.ORDERED_TABS:
                curr_idx = self.ORDERED_TABS.index(curr)
                prev_idx = (curr_idx - 1) % len(self.ORDERED_TABS)
                tabs.active = self.ORDERED_TABS[prev_idx]
            else:
                tabs.active = self.ORDERED_TABS[0]
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        key = event.key
        if key in (
            "ctrl+[",
            "ctrl+left_square_bracket",
            "ctrl+left_square_brace",
            "ctrl+{",
            "ctrl+left_curly_bracket",
            "ctrl+shift+left_square_bracket",
            "alt+[",
            "alt+left_square_bracket",
            "alt+{",
            "alt+left_curly_bracket",
            "alt+shift+left_square_bracket",
        ):
            event.stop()
            event.prevent_default()
            self.action_shrink_sidebar()
        elif key in (
            "ctrl+]",
            "ctrl+right_square_bracket",
            "ctrl+right_square_brace",
            "ctrl+}",
            "ctrl+right_curly_bracket",
            "ctrl+shift+right_square_bracket",
            "alt+]",
            "alt+right_square_bracket",
            "alt+}",
            "alt+right_curly_bracket",
            "alt+shift+right_square_bracket",
        ):
            event.stop()
            event.prevent_default()
            self.action_expand_sidebar()
        elif key == "ctrl+i":
            event.stop()
            event.prevent_default()
            self.action_focus_tutor()
        elif key in ("ctrl+alt+b", "alt+ctrl+b"):
            event.stop()
            event.prevent_default()
            self.action_toggle_copilot()
        elif key == "ctrl+b":
            event.stop()
            event.prevent_default()
            self.action_toggle_sidebar()
        elif key in (
            "ctrl+alt+[",
            "ctrl+alt+left_square_bracket",
            "ctrl+alt+{",
            "ctrl+alt+left_curly_bracket",
            "alt+ctrl+[",
            "alt+ctrl+left_square_bracket",
            "alt+ctrl+{",
            "alt+ctrl+left_curly_bracket",
        ):
            event.stop()
            event.prevent_default()
            self.action_expand_copilot()
        elif key in (
            "ctrl+alt+]",
            "ctrl+alt+right_square_bracket",
            "ctrl+alt+}",
            "ctrl+alt+right_curly_bracket",
            "alt+ctrl+]",
            "alt+ctrl+right_square_bracket",
            "alt+ctrl+}",
            "alt+ctrl+right_curly_bracket",
        ):
            event.stop()
            event.prevent_default()
            self.action_shrink_copilot()
        elif key == "escape":
            event.stop()
            event.prevent_default()
            self.action_nav_tool_browser()
