"""Learning Mode screen with redesigned Phase 2 lesson layout."""

import asyncio
from typing import Any, List, Optional

from rich.markdown import Markdown as RichMarkdown
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
)


def render_markdown(text: str) -> RichMarkdown:
    """Render markdown using Rich renderables without DOM widget hierarchy churn."""
    return RichMarkdown(text, justify="left", code_theme="monokai")


from cyguide.ui.widgets import ResizeHandle, TerminalStreamPane
from cyguide.ui.widgets.flags import FlagEditor
from cyguide.ui.widgets.recipe_deck import RecipeDeck, RecipeListItem


class LearningModeScreen(Screen):
    """Phase 2: The Lesson Screen."""

    BINDINGS = [
        ("f1", "show_shortcuts", "Help"),
        ("ctrl+left", "prev_tab", "Prev Tab"),
        ("ctrl+right", "next_tab", "Next Tab"),
        Binding("ctrl+c", "copy_selection", "Copy Selection", show=False),
        Binding("ctrl+y", "copy_explanation", "Copy All", show=False),
        ("escape", "nav_tool_browser", "Tool Browser"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
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
                    yield Label("◆ TOOL CONTEXT", id="tool_name_header", classes="pane_title")
                    yield Static("", id="tool_summary_header")

                yield Label(
                    "WORKFLOW RECIPES", id="recipes_header_label", classes="pane_section_title"
                )
                with ListView(id="recipe_list"):
                    pass  # Populated in select_tool

                with Vertical(id="launchpad_container"):
                    yield Vertical(id="flag_editor_container")
                    with Vertical(id="run_stop_container"):
                        yield Button("✦  ASK AI", id="sidebar_ask_btn", classes="sidebar_btn")
                        yield Button(
                            "▶  RUN SCAN", id="run_btn", variant="success", classes="sidebar_btn"
                        )
                        yield Button(
                            "■  STOP SCAN",
                            id="stop_btn",
                            variant="error",
                            classes="hidden sidebar_btn",
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

            # Right Zone: Execution Workbench + Bottom Chat Dock
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

                    with TabPane("◆ EXPLANATION", id="tab_explanation"):
                        with Horizontal(classes="pane_toolbar", id="explanation_toolbar"):
                            yield Label(
                                "", id="explanation_status_label", classes="pane_status_label"
                            )
                            yield Button(
                                "● AI: ON",
                                id="toggle_ai_explanation_btn",
                                classes="pane_action_btn ai_toggle_btn ai_toggle_on",
                            )
                            yield Button(
                                "COPY", id="copy_explanation_btn", classes="pane_action_btn"
                            )
                            yield Button(
                                "CLEAR", id="clear_explanation_btn", classes="pane_action_btn"
                            )
                        with VerticalScroll(id="explanation_scroll"):
                            yield Static(
                                render_markdown(
                                    "*Select a recipe and run the tool to see explanations.*"
                                ),
                                id="explanation_text",
                            )

                # Bottom Docked Chat Bar (identical to Power Mode's command palette)
                with Horizontal(id="chat_dock"):
                    yield Label("◆", id="chat_prompt_symbol")
                    yield Input(
                        placeholder="Ask AI tutor or type / for commands (/summary, /flags, /help)...",
                        id="chat_input",
                        disabled=False,
                    )
                    yield Button("ASK", id="ask_btn", variant="primary", disabled=False)

        yield Footer()

    def _restore_sidebar_width(self) -> None:
        """Restore user's saved sidebar width preference."""
        try:
            if hasattr(self.app, "settings"):
                saved_width = self.app.settings.get("learning_sidebar_width")
                if saved_width:
                    pane = self.query_one("#lesson_config_pane")
                    pane.styles.width = int(saved_width)
        except Exception:
            pass

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
            if getattr(self, "ai_explanations_enabled", True):
                btn.label = "● AI: ON"
                btn.remove_class("ai_toggle_off")
                btn.add_class("ai_toggle_on")
                status_lbl.update("")
            else:
                btn.label = "○ AI: OFF"
                btn.remove_class("ai_toggle_on")
                btn.add_class("ai_toggle_off")
                status_lbl.update("[dim #a1a1aa]▲ AI briefings paused[/]")
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
        self._restore_sidebar_width()
        self._restore_ai_explanation_pref()
        await self.update_tool_context(force=True)

    async def on_screen_resume(self) -> None:
        """Triggered when the screen is resumed (switched back to)."""
        self._restore_sidebar_width()
        self._restore_ai_explanation_pref()
        await self.update_tool_context(force=False)

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
        context = self.session.select_tool(tool_name)
        if not context:
            return

        # Keep previous buffer history across tools if already present
        if not self.log_buffer:
            self.query_one("#raw_output_terminal", TerminalStreamPane).clear()
        if not self.explanation_buffer:
            self.query_one("#explanation_text", Static).update(
                render_markdown(context.welcome_markdown)
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

        # 4. Update Flag Editor
        container = self.query_one("#flag_editor_container", Vertical)
        await container.query("*").remove()
        self.flag_editor = FlagEditor(tool_name, context.manifest)
        await container.mount(self.flag_editor)

        # 5. Set Smart Default Target for the Tool
        default_targets = {
            "nmap": "127.0.0.1",
            "gobuster": "http://scanme.nmap.org",
            "nikto": "http://scanme.nmap.org",
            "subfinder": "example.com",
            "whois": "example.com",
        }
        target_input = self.query_one("#target_input", Input)
        target_val = default_targets.get(tool_name, "127.0.0.1")
        target_input.value = target_val
        self.flag_editor.update_preview()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RecipeListItem):
            # Pre-populate flags from recipe
            self.flag_editor.set_flags(event.item.recipe.flags)
            self.notify(f"Loaded recipe: {event.item.recipe.name}", title="Recipe Loaded")
            try:
                recipe_list = self.query_one("#recipe_list", ListView)
                self.active_recipe_idx = recipe_list.index
            except Exception:
                pass

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
                        tabs = self.query_one("#learning_tabs", TabbedContent)
                        tabs.active = "tab_explanation"
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
                    self.notify(f"Loaded recipe: {recipe.name}", title="Recipe Loaded")
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
        elif bid == "clear_output_btn":
            self.clear_output()
        elif bid == "copy_explanation_btn":
            self.action_copy_explanation()
        elif bid == "copy_output_btn":
            self.action_copy_output()

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
                self.notify(f"Copy failed: {e}", severity="error")
                return

        self.notify(
            "No text selected. Highlight text to copy, or use Ctrl+Y / /copy to copy full explanation.",
            severity="information",
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
            self.query_one("#learning_tabs", TabbedContent).active = "tab_explanation"
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
                    self.explanation_buffer + f"\n\n---\n\n{cmd_result.message}\n"
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
            self.query_one("#learning_tabs", TabbedContent).active = "tab_explanation"
        except Exception:
            pass

        explanation_pane = self.query_one("#explanation_text", Static)
        explanation_scroll = self.query_one("#explanation_scroll", VerticalScroll)

        display_prompt = user_display or question
        base_buffer = (
            self.explanation_buffer + f"\n\n---\n\n### ❯ You: {display_prompt}\n\n"
            if self.explanation_buffer
            else f"### ❯ You: {display_prompt}\n\n"
        )

        if not getattr(self, "ai_explanations_enabled", True):
            try:
                self.query_one("#explanation_status_label", Label).update(
                    "[#eab308]▲ AI Tutor is turned OFF (click AI: OFF to enable)[/]"
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

    @work(exclusive=True)
    async def run_scan(self):
        if self.scan_in_progress:
            return

        try:
            params, target_ip = self.flag_editor.get_command_params()
        except ValueError as e:
            self.notify(str(e), severity="error")
            return

        self.scan_in_progress = True
        run_btn = self.query_one("#run_btn", Button)
        stop_btn = self.query_one("#stop_btn", Button)
        try:
            sidebar_ask_btn = self.query_one("#sidebar_ask_btn", Button)
            sidebar_ask_btn.display = False
            sidebar_ask_btn.disabled = True
        except Exception:
            pass

        # UI Setup for Run
        run_btn.display = False
        stop_btn.display = True
        stop_btn.disabled = False

        if self.active_recipe_idx is None:
            try:
                manifest = (
                    self.app.registry.get_tool(self.active_tool).get("manifest")
                    if self.active_tool
                    else None
                )
                if manifest and manifest.learning and manifest.learning.recipes:
                    curr_flags = set(params.get("raw_flags", "").split())
                    for r_idx, r in enumerate(manifest.learning.recipes):
                        if set(r.flags) == curr_flags:
                            self.active_recipe_idx = r_idx
                            break
            except Exception:
                pass

        try:
            self.query_one("#recipes_scroll", RecipeDeck).set_active_recipe_state(
                self.active_recipe_idx, is_running=True
            )
        except Exception:
            pass

        output_terminal = self.query_one("#raw_output_terminal", TerminalStreamPane)
        explainer_pane = self.query_one("#explanation_text", Static)
        explainer_scroll = self.query_one("#explanation_scroll", VerticalScroll)

        async def on_raw_chunk(line: str) -> None:
            output_terminal.write(line)
            await asyncio.sleep(0)

        from cyguide.engine.gateway import ActionValidationError
        from cyguide.engine.learning import (
            BriefingChunkEvent,
            BriefingCompletedEvent,
            BriefingStartedEvent,
            ScanCompletedEvent,
            ScanStartedEvent,
        )

        try:
            base_expl_buffer = self.explanation_buffer
            briefing_text = ""
            import time

            last_expl_update = time.time()

            raw_flags_str = params.get("raw_flags", "")
            active_flags_set = set(raw_flags_str.split())

            async for event in self.session.run_scan(
                target=target_ip,
                flags_used=raw_flags_str,
                selected_flags=active_flags_set,
                recipe_idx=self.active_recipe_idx,
                on_raw_chunk=on_raw_chunk,
            ):
                if isinstance(event, ScanStartedEvent):
                    output_terminal.write(event.header_text)
                    output_terminal.flush()
                    if getattr(self, "ai_explanations_enabled", True):
                        expl_header = (
                            f"\n\n---\n\n# Run #{event.run_count}: `{event.cmd_str}` *({event.timestamp})*\n\n"
                            if self.explanation_buffer
                            else f"# Run #{event.run_count}: `{event.cmd_str}` *({event.timestamp})*\n\n"
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

                elif isinstance(event, ScanCompletedEvent):
                    output_terminal.write(event.footer_text)
                    output_terminal.flush()
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
                        "[#eab308]▲ AI explanation is turned OFF — scan briefing skipped[/]"
                    )
                except Exception:
                    pass
                self.notify(
                    "AI Explanation is turned off. Scan briefing skipped.", severity="information"
                )

        except ActionValidationError as e:
            self.notify(f"Security Policy: {str(e)}", severity="error")
            err_msg = f"\n[!] Policy Violation: {str(e)}\n"
            self.log_buffer.append(err_msg)
            output_terminal.write(err_msg)
            output_terminal.flush()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            err_msg = f"\n[!] Error: {str(e)}\n"
            self.log_buffer.append(err_msg)
            output_terminal.write(err_msg)
            output_terminal.flush()
        finally:
            self.reset_ui_after_run()

    def action_show_shortcuts(self) -> None:
        from cyguide.ui.dialogs import ShortcutsDialog

        if any(isinstance(s, ShortcutsDialog) for s in self.app._screen_stack):
            return
        self.app.push_screen(ShortcutsDialog())

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
                sidebar.add_class("collapsed")
                if resizer:
                    resizer.add_class("hidden")
                sidebar.styles.animate(
                    "width",
                    value=0,
                    duration=0.2,
                    easing="in_out_cubic",
                )
            else:
                sidebar.remove_class("collapsed")
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

    def action_shrink_sidebar(self) -> None:
        try:
            pane = self.query_one("#lesson_config_pane")
            curr = int(
                pane.styles.width.value
                if pane.styles.width and pane.styles.width.value
                else (pane.region.width or 32)
            )
            new_w = max(20, curr - 4)
            pane.styles.width = new_w
            if hasattr(self.app, "settings"):
                self.app.settings["learning_sidebar_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_sidebar_width": new_w})
            self.refresh(layout=True)
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
            pane.styles.width = new_w
            if hasattr(self.app, "settings"):
                self.app.settings["learning_sidebar_width"] = new_w
            if hasattr(self.app, "save_settings"):
                self.app.save_settings({"learning_sidebar_width": new_w})
            self.refresh(layout=True)
        except Exception:
            pass

    ORDERED_TABS = ["tab_recipes", "tab_output", "tab_explanation"]

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
            "alt+]",
            "alt+right_square_bracket",
            "alt+}",
            "alt+right_curly_bracket",
            "alt+shift+right_square_bracket",
        ):
            event.stop()
            event.prevent_default()
            self.action_expand_sidebar()
