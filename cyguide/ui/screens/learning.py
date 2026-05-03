"""Learning Mode screen with redesigned Phase 2 lesson layout."""

import asyncio
from typing import List, Dict, Any, Optional

from textual import work
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, ListItem, ListView, Button, Input, Checkbox
from textual.containers import Vertical, Horizontal, Grid, VerticalScroll
from textual.app import ComposeResult
from cyguide.schemas.network import NetworkHost
from datetime import datetime

class RecipeListItem(ListItem):
    """A list item that shows a recipe name."""
    def __init__(self, recipe: Any, tool_name: str):
        super().__init__()
        self.recipe = recipe
        self.tool_name = tool_name

    def compose(self) -> ComposeResult:
        yield Label(f"▶ {self.recipe.name}", classes="recipe_name")

class FlagEditor(Vertical):
    """Widget for manual flag entry and command preview."""
    def __init__(self, tool_name: str, manifest: Any):
        super().__init__()
        self.tool_name = tool_name
        self.manifest = manifest
        
    def compose(self) -> ComposeResult:
        yield Label("ADDITIONAL FLAGS", classes="section_header")
        yield Input(placeholder="e.g. -sV -Pn", id="flags_input")
            
        yield Label("\nTARGET", classes="section_header")
        yield Input(value="127.0.0.1", id="target_input")
        
        yield Label("\nPREVIEW", classes="section_header")
        yield Static(f"{self.tool_name} 127.0.0.1", id="command_preview")
        yield Label("", id="sudo_warning")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_preview()

    def update_preview(self) -> None:
        target = self.query_one("#target_input", Input).value
        flags = self.query_one("#flags_input", Input).value
        
        warning = self.query_one("#sudo_warning", Label)
        if "sudo" in flags.lower() or "sudo" in target.lower():
            warning.update("[!] Sudo commands cannot be performed in Learning Mode.")
            warning.styles.color = "red"
        else:
            warning.update("")

        cmd = f"{self.tool_name} {flags} {target}"
        self.query_one("#command_preview", Static).update(cmd.replace("  ", " "))

    def set_flags(self, flags_list: List[str]):
        """Set flags from a recipe and update UI."""
        input_widget = self.query_one("#flags_input", Input)
        input_widget.value = " ".join(flags_list)
        self.update_preview()

    def get_command_params(self):
        flags = self.query_one("#flags_input", Input).value
        if "sudo" in flags.lower():
            raise ValueError("Sudo is not allowed in Learning Mode.")
        return {"raw_flags": flags}, self.query_one("#target_input", Input).value


class ExpandedOutputScreen(Screen):
    """Full-screen view for raw output."""
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, content: str):
        super().__init__()
        self.content = content
        
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="expanded_output_container"):
            yield Static(self.content, id="expanded_raw_output", markup=False)
        yield Footer()

class LearningModeScreen(Screen):
    """Phase 2: The Lesson Screen."""
    
    BINDINGS = [
        ("escape", "nav_tool_browser", "Tool Browser"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.active_tool = None
        self.log_buffer = [] # Use list for O(1) appends
        self.scan_in_progress = False
        self.explanation_buffer = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="learning_layout"):
            # Left Zone: Context and Configuration
            with Vertical(id="lesson_config_pane"):
                with VerticalScroll(id="lesson_config_content"):
                    with Vertical(id="tool_context_zone"):
                        yield Label("TOOL CONTEXT", classes="section_header")
                        yield Label("", id="tool_name_header")
                        yield Static("", id="tool_summary_header")
                    
                    yield Label("RECIPE", classes="section_header")
                    with ListView(id="recipe_list"):
                        pass # Populated in select_tool
                    
                    yield Vertical(id="flag_editor_container")
                
                # Fixed at bottom
                with Horizontal(id="run_stop_container"):
                    yield Button("▶ RUN", id="run_btn", variant="success", classes="sidebar_btn")
                    yield Button("⏹ STOP", id="stop_btn", variant="error", classes="hidden sidebar_btn")
            
            # Right Zone: Explanation and Output
            with Vertical(id="lesson_execution_pane"):
                with Vertical(id="explanation_pane"):
                    with Horizontal(id="explanation_header"):
                        yield Label("EXPLANATION", classes="section_header")
                        yield Static("", id="header_spacer")
                        yield Button("📋 COPY", id="copy_explanation_btn", classes="header_btn")
                        yield Button("⛶", id="expand_explanation_btn", classes="header_btn")
                    with VerticalScroll(id="explanation_scroll"):
                        yield Static("Select a recipe and run the tool to see explanations.", id="explanation_text")
                
                with Vertical(id="output_pane"):
                    with Horizontal(id="output_header"):
                        yield Label("RAW OUTPUT", classes="section_header")
                        yield Static("", id="header_spacer")
                        yield Button("📋 COPY", id="copy_output_btn", classes="header_btn")
                        yield Button("⛶", id="expand_output_btn", classes="header_btn")
                    with VerticalScroll(id="output_scroll"):
                        yield Static("", id="raw_output_text", markup=False)
                
                with Vertical(id="chat_zone"):
                    yield Label("ASK ABOUT THESE RESULTS", classes="section_header")
                    with Horizontal(id="chat_bar"):
                        yield Input(placeholder="Ask a question about these results...", id="chat_input", disabled=True)
                        yield Button("ASK", id="ask_btn", disabled=True)
            
        yield Footer()

    async def on_mount(self) -> None:
        """Triggered when the screen is first mounted."""
        await self.update_tool_context()

    async def on_screen_resume(self) -> None:
        """Triggered when the screen is resumed (switched back to)."""
        await self.update_tool_context()

    async def update_tool_context(self) -> None:
        """Refresh the screen content based on the selected tool."""
        if hasattr(self.app, "learning_mode_tool"):
            await self.select_tool(self.app.learning_mode_tool)

    async def select_tool(self, tool_name: str):
        self.active_tool = tool_name
        tool_data = self.app.registry.get_tool(tool_name)
        if not tool_data: return
        manifest = tool_data["manifest"]
        
        # 1. Clear old run data
        self.log_buffer = []
        self.explanation_buffer = ""
        self.query_one("#raw_output_text", Static).update("")
        self.query_one("#explanation_text", Static).update("Select a recipe and run the tool to see explanations.")
        
        # 2. Update Header
        self.query_one("#tool_name_header", Label).update(manifest.meta.name.upper())
        self.query_one("#tool_summary_header", Static).update(manifest.meta.one_line_summary)
        
        # 3. Update Recipes
        recipe_list = self.query_one("#recipe_list", ListView)
        await recipe_list.clear()
        if manifest.learning and manifest.learning.recipes:
            for r in manifest.learning.recipes:
                await recipe_list.append(RecipeListItem(r, tool_name))
        
        # 4. Update Flag Editor
        container = self.query_one("#flag_editor_container", Vertical)
        await container.query("*").remove()
        self.flag_editor = FlagEditor(tool_name, manifest)
        await container.mount(self.flag_editor)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RecipeListItem):
            # Pre-populate flags from recipe
            self.flag_editor.set_flags(event.item.recipe.flags)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run_btn":
            self.run_scan()
        elif event.button.id == "stop_btn":
            await self.stop_scan()
        elif event.button.id == "copy_output_btn":
            try:
                import pyperclip
                pyperclip.copy("".join(self.log_buffer))
                self.notify("Output copied to clipboard!")
            except:
                self.notify("Copy failed", severity="error")
        elif event.button.id == "expand_output_btn":
            self.app.push_screen(ExpandedOutputScreen("".join(self.log_buffer)))
        elif event.button.id == "copy_explanation_btn":
            try:
                import pyperclip
                pyperclip.copy(self.explanation_buffer)
                self.notify("Explanation copied to clipboard!")
            except:
                self.notify("Copy failed", severity="error")
        elif event.button.id == "expand_explanation_btn":
            self.app.push_screen(ExpandedOutputScreen(self.explanation_buffer))


    async def stop_scan(self):
        """Terminate the running tool."""
        await self.app.executor.stop_tool(self.app.learning_session_id)
        self.log_buffer.append("\n[!] Scan stopped by user.\n")
        self.query_one("#raw_output_text", Static).update("".join(self.log_buffer))
        self.reset_ui_after_run()

    def reset_ui_after_run(self):
        """Restore button states after scan finishes or stops."""
        self.scan_in_progress = False
        run_btn = self.query_one("#run_btn", Button)
        stop_btn = self.query_one("#stop_btn", Button)
        run_btn.display = True
        stop_btn.display = False
        run_btn.disabled = False
        stop_btn.disabled = True

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
        
        # UI Setup for Run
        run_btn.display = False
        stop_btn.display = True
        stop_btn.disabled = False
        
        output_pane = self.query_one("#raw_output_text", Static)
        output_scroll = self.query_one("#output_scroll", VerticalScroll)
        explainer_pane = self.query_one("#explanation_text", Static)
        
        self.log_buffer = [] # Clear buffer for new run
        output_pane.update("Scanning...\n")
        
        self.explanation_buffer = ""
        explainer_pane.update("[analyzing findings...]")

        # Throttling state
        self._last_ui_update = 0
        UPDATE_INTERVAL = 0.05 

        async def update_ui_throttled():
            import time
            now = time.time()
            if now - self._last_ui_update > UPDATE_INTERVAL:
                output_pane.update("".join(self.log_buffer))
                output_scroll.scroll_end(animate=False)
                explainer_pane.update(self.explanation_buffer)
                self._last_ui_update = now
            
            await asyncio.sleep(0) # ALWAYS yield to UI loop

        async def on_explanation(chunk: str):
            self.explanation_buffer += chunk
            await update_ui_throttled()

        async def on_raw_output(line: str):
            self.log_buffer.append(line)
            await update_ui_throttled()

        target = NetworkHost.create(ip=target_ip)
        
        try:
            async for finding in self.app.learning_engine.execute(
                self.active_tool, 
                target, 
                params, 
                session_id=self.app.learning_session_id,
                on_explanation=on_explanation,
                on_output=on_raw_output
            ):
                pass
                
            # Activate chat after scan complete
            self.query_one("#chat_input", Input).disabled = False
            self.query_one("#ask_btn", Button).disabled = False
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            output_pane.update("".join(self.log_buffer) + f"\n[!] Error: {str(e)}")
        finally:
            # Final UI flush
            output_pane.update("".join(self.log_buffer))
            output_scroll.scroll_end(animate=False)
            self.reset_ui_after_run()

    def action_nav_tool_browser(self) -> None:
        self.app.switch_screen("tool_browser")

    def action_toggle_sidebar(self) -> None:
        self.query_one("#lesson_config_pane").toggle_class("collapsed")
