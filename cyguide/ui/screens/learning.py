"""Learning Mode screen with redesigned Phase 2 lesson layout."""

import asyncio
from typing import List, Dict, Any, Optional

from textual import work
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, ListItem, ListView, Button, Input, Checkbox, Markdown
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

        preview_flags = flags.replace("{url}", target)
        preview_flags = preview_flags.replace("{target}", target)
        preview_flags = preview_flags.replace("{domain}", target)
        preview_flags = preview_flags.replace("{port}", "80")
        preview_flags = preview_flags.replace("{wordlist}", "./wordlist.txt")
        
        if "{url}" in flags or "{target}" in flags or "{domain}" in flags:
            cmd = f"{self.tool_name} {preview_flags}"
        else:
            cmd = f"{self.tool_name} {preview_flags} {target}"
            
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
    """Full-screen view for raw output or rendered markdown."""
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, content: str, is_markdown: bool = False):
        super().__init__()
        self.content = content
        self.is_markdown = is_markdown
        
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="expanded_output_container"):
            if self.is_markdown:
                yield Markdown(self.content, id="expanded_markdown_output")
            else:
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
        self.run_count = 0

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
                        yield Button("↕ EXPAND", id="toggle_expl_size_btn", classes="header_btn")
                        yield Button("🗑️ CLEAR", id="clear_expl_btn", classes="header_btn")
                        yield Button("📋 COPY", id="copy_explanation_btn", classes="header_btn")
                        yield Button("⛶", id="expand_explanation_btn", classes="header_btn")
                    with VerticalScroll(id="explanation_scroll"):
                        yield Markdown("*Select a recipe and run the tool to see explanations.*", id="explanation_text")
                
                with Vertical(id="output_pane"):
                    with Horizontal(id="output_header"):
                        yield Label("RAW OUTPUT", classes="section_header")
                        yield Static("", id="header_spacer")
                        yield Button("↕ EXPAND", id="toggle_output_size_btn", classes="header_btn")
                        yield Button("🗑️ CLEAR", id="clear_output_btn", classes="header_btn")
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
        await self.update_tool_context(force=True)

    async def on_screen_resume(self) -> None:
        """Triggered when the screen is resumed (switched back to)."""
        await self.update_tool_context(force=False)

    async def update_tool_context(self, force: bool = False) -> None:
        """Refresh the screen content based on the selected tool."""
        try:
            selected_tool = getattr(self.app, "learning_mode_tool", None)
        except Exception:
            selected_tool = None
        if selected_tool and (force or selected_tool != self.active_tool):
            await self.select_tool(selected_tool)

    async def select_tool(self, tool_name: str):
        self.active_tool = tool_name
        tool_data = self.app.registry.get_tool(tool_name)
        if not tool_data: return
        manifest = tool_data["manifest"]
        
        # Keep previous buffer history across tools if already present
        if not self.log_buffer:
            self.query_one("#raw_output_text", Static).update("")
        if not self.explanation_buffer:
            self.query_one("#explanation_text", Markdown).update("*Select a recipe and run the tool to see explanations.*")
        
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
        
        # 5. Set Smart Default Target for the Tool
        default_targets = {
            "nmap": "127.0.0.1",
            "gobuster": "http://scanme.nmap.org",
            "nikto": "http://scanme.nmap.org",
            "subfinder": "example.com",
            "whois": "example.com"
        }
        target_input = self.query_one("#target_input", Input)
        target_input.value = default_targets.get(tool_name, "127.0.0.1")
        self.flag_editor.update_preview()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RecipeListItem):
            # Pre-populate flags from recipe
            self.flag_editor.set_flags(event.item.recipe.flags)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run_btn":
            self.run_scan()
        elif event.button.id == "stop_btn":
            await self.stop_scan()
        elif event.button.id == "toggle_expl_size_btn":
            exec_pane = self.query_one("#lesson_execution_pane")
            btn = self.query_one("#toggle_expl_size_btn", Button)
            out_btn = self.query_one("#toggle_output_size_btn", Button)
            if exec_pane.has_class("explanation-maximized"):
                exec_pane.remove_class("explanation-maximized")
                btn.label = "↕ EXPAND"
            else:
                exec_pane.remove_class("output-maximized")
                exec_pane.add_class("explanation-maximized")
                btn.label = "↕ SHRINK"
                out_btn.label = "↕ EXPAND"
        elif event.button.id == "toggle_output_size_btn":
            exec_pane = self.query_one("#lesson_execution_pane")
            btn = self.query_one("#toggle_output_size_btn", Button)
            expl_btn = self.query_one("#toggle_expl_size_btn", Button)
            if exec_pane.has_class("output-maximized"):
                exec_pane.remove_class("output-maximized")
                btn.label = "↕ EXPAND"
            else:
                exec_pane.remove_class("explanation-maximized")
                exec_pane.add_class("output-maximized")
                btn.label = "↕ SHRINK"
                expl_btn.label = "↕ EXPAND"
        elif event.button.id == "clear_expl_btn":
            self.explanation_buffer = ""
            self.query_one("#explanation_text", Markdown).update("*Explanations cleared.*")
            self.notify("Explanations cleared.")
        elif event.button.id == "clear_output_btn":
            self.log_buffer = []
            self.query_one("#raw_output_text", Static).update("")
            self.notify("Raw output cleared.")
        elif event.button.id == "copy_output_btn":
            try:
                import pyperclip
                pyperclip.copy("".join(self.log_buffer))
                self.notify("Output copied to clipboard!")
            except Exception:
                self.notify("Copy failed", severity="error")
        elif event.button.id == "expand_output_btn":
            self.app.push_screen(ExpandedOutputScreen("".join(self.log_buffer), is_markdown=False))
        elif event.button.id == "copy_explanation_btn":
            try:
                import pyperclip
                pyperclip.copy(self.explanation_buffer)
                self.notify("Explanation copied to clipboard!")
            except Exception:
                self.notify("Copy failed", severity="error")
        elif event.button.id == "expand_explanation_btn":
            self.app.push_screen(ExpandedOutputScreen(self.explanation_buffer, is_markdown=True))
        elif event.button.id == "ask_btn":
            self.submit_chat_question()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat_input":
            self.submit_chat_question()

    @work(exclusive=True)
    async def submit_chat_question(self) -> None:
        chat_input = self.query_one("#chat_input", Input)
        question = chat_input.value.strip()
        if not question: return
        
        chat_input.value = ""
        self.explanation_buffer += f"\n\n---\n\n### 💬 Question: {question}\n\n"
        explanation_pane = self.query_one("#explanation_text", Markdown)
        explanation_scroll = self.query_one("#explanation_scroll", VerticalScroll)
        explanation_pane.update(self.explanation_buffer)
        explanation_scroll.scroll_end(animate=False)
        
        # Build prompt with context
        context = "".join(self.log_buffer[-50:]) # Last 50 lines of logs as context
        prompt = (
            f"You are a cybersecurity tutor in CyGuide.\n"
            f"Context from scan output ({self.active_tool}):\n{context}\n\n"
            f"Student Question: {question}\n\n"
            "Provide a concise, direct, and well-structured answer in clean Markdown. "
            "Use bullet points, bold keywords, or brief code snippets where relevant. Avoid conversational filler."
        )
        
        import time
        last_chat_update = time.time()
        CHAT_UPDATE_INTERVAL = 0.05
        
        try:
            async for chunk in self.app.explainer.ask(prompt):
                self.explanation_buffer += chunk
                now = time.time()
                if now - last_chat_update > CHAT_UPDATE_INTERVAL:
                    explanation_pane.update(self.explanation_buffer)
                    explanation_scroll.scroll_end(animate=False)
                    last_chat_update = now
                await asyncio.sleep(0)
        except Exception as e:
            self.explanation_buffer += f"\n\n> ⚠️ **Error getting explanation:** {str(e)}\n"
            self.notify(f"Explanation error: {e}", severity="error")
        finally:
            explanation_pane.update(self.explanation_buffer)
            explanation_scroll.scroll_end(animate=False)


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
        
        self.run_count += 1
        timestamp = datetime.now().strftime('%H:%M:%S')
        flags_used = params.get("raw_flags", "")
        cmd_str = f"{self.active_tool} {flags_used} {target_ip}".strip().replace("  ", " ")

        output_pane = self.query_one("#raw_output_text", Static)
        output_scroll = self.query_one("#output_scroll", VerticalScroll)
        explainer_pane = self.query_one("#explanation_text", Markdown)
        explainer_scroll = self.query_one("#explanation_scroll", VerticalScroll)
        
        # Append Run Header to Raw Output Log
        log_header = f"\n\n{'═'*65}\n▶ RUN #{self.run_count} [{timestamp}]  $ {cmd_str}\n{'═'*65}\n\n" if self.log_buffer else f"{'═'*65}\n▶ RUN #{self.run_count} [{timestamp}]  $ {cmd_str}\n{'═'*65}\n\n"
        self.log_buffer.append(log_header)
        output_pane.update("".join(self.log_buffer[-2000:]))
        output_scroll.scroll_end(animate=False)
        
        # Append Run Header to Explanation
        expl_run_header = f"\n\n---\n\n# ⚡ Run #{self.run_count}: `{cmd_str}` *({timestamp})*\n\n" if self.explanation_buffer else f"# ⚡ Run #{self.run_count}: `{cmd_str}` *({timestamp})*\n\n"
        self.explanation_buffer += expl_run_header
        explainer_pane.update(self.explanation_buffer + "\n*[Running scan...]*")
        explainer_scroll.scroll_end(animate=False)

        # Throttling state
        self._last_ui_update = 0
        UPDATE_INTERVAL = 0.05 

        async def update_ui_throttled():
            import time
            now = time.time()
            if now - self._last_ui_update > UPDATE_INTERVAL:
                display_slice = "".join(self.log_buffer[-2000:])
                output_pane.update(display_slice)
                output_scroll.scroll_end(animate=False)
                self._last_ui_update = now
            
            await asyncio.sleep(0) # ALWAYS yield to UI loop


        async def on_raw_output(line: str):
            self.log_buffer.append(line)
            await update_ui_throttled()

        # Create the appropriate target schema for the tool
        target = None
        if self.active_tool in ("gobuster", "nikto") and target_ip.startswith("http"):
            from cyguide.schemas.web import WebEndpoint
            target = WebEndpoint.create(url=target_ip, method="GET", status_code=0)
        elif self.active_tool in ("subfinder", "whois"):
            # Ensure it's treated as a domain
            from cyguide.schemas.dns import DnsRecord
            from cyguide.schemas.base import BaseFinding
            # Create a dummy DomainInfo. Wait, DomainInfo is not defined, let's just use DNSRecord
            target = DnsRecord.create(domain=target_ip, record_type="A", value="")
        else:
            target = NetworkHost.create(ip=target_ip)
        
        try:
            async for finding in self.app.learning_engine.execute(
                self.active_tool, 
                target, 
                params, 
                session_id=self.app.learning_session_id,
                on_output=on_raw_output
            ):
                pass
                
            # Activate chat after scan complete
            self.query_one("#chat_input", Input).disabled = False
            self.query_one("#ask_btn", Button).disabled = False

            # Trigger automated explanation of findings
            if hasattr(self.app, "explainer") and self.app.explainer:
                explainer_pane.update(self.explanation_buffer + "\n*[Analyzing scan results & generating structured breakdown...]*")
                explainer_scroll.scroll_end(animate=False)
                
                context_logs = "".join(self.log_buffer[-80:])
                
                prompt = (
                    f"You are a cybersecurity instructor in CyGuide.\n"
                    f"Tool: {self.active_tool}\n"
                    f"Command executed: {self.active_tool} {flags_used} {target_ip}\n\n"
                    f"Raw Terminal Output:\n{context_logs}\n\n"
                    "Generate a concise, scannable educational breakdown in standard Markdown.\n"
                    "Do NOT include conversational greetings, fluff, or preambles.\n\n"
                    "Strictly follow this structure:\n"
                    "## 🎯 Quick Summary\n"
                    "1-2 punchy sentences summarizing the target state.\n\n"
                    "## 📊 Discovered Services & Findings\n"
                    "| Port / Item | Service & Version | State | Meaning |\n"
                    "| :--- | :--- | :--- | :--- |\n"
                    "(Concise rows only. Keep cell text short to fit terminal widths.)\n\n"
                    "## ⚙️ Flags Breakdown\n"
                    "| Flag | Name | Practical Purpose |\n"
                    "| :--- | :--- | :--- |\n"
                    "(List each flag used with brief 1-line explanation.)\n\n"
                    "## 💡 Key Takeaways\n"
                    "- Key learning point 1\n"
                    "- Key learning point 2\n\n"
                    "## 🚀 Next Recommended Commands\n"
                    "1. `command_here` — 1-sentence reason\n"
                    "2. `command_here` — 1-sentence reason\n"
                )
                
                import time
                last_expl_update = time.time()
                try:
                    async for chunk in self.app.explainer.ask(prompt):
                        self.explanation_buffer += chunk
                        now = time.time()
                        if now - last_expl_update > 0.05:
                            explainer_pane.update(self.explanation_buffer)
                            explainer_scroll.scroll_end(animate=False)
                            last_expl_update = now
                        await asyncio.sleep(0)
                except Exception as e:
                    self.explanation_buffer += f"\n\n> ⚠️ **Explanation error:** {str(e)}\n"
                finally:
                    explainer_pane.update(self.explanation_buffer)
                    explainer_scroll.scroll_end(animate=False)
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_buffer.append(f"\n[!] Error: {str(e)}\n")
        finally:
            # Final UI flush
            output_pane.update("".join(self.log_buffer[-2000:]))
            output_scroll.scroll_end(animate=False)
            self.reset_ui_after_run()

    def action_nav_tool_browser(self) -> None:
        self.app.switch_screen("tool_browser")

    def action_toggle_sidebar(self) -> None:
        self.query_one("#lesson_config_pane").toggle_class("collapsed")
