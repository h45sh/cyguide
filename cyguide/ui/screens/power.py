"""The main Power Mode screen for advanced investigation."""

from typing import Optional, Dict, List, Any
from uuid import UUID
from datetime import datetime
import asyncio
from textual import events
from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import TabbedContent, TabPane, RichLog, Input, Label, Static, TextArea, Markdown, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

from cyguide.ui.widgets.power import EntityBrowser, JobQueue, CommandPalette, SuggestionsPane
from cyguide.schemas.power import ActionRequest, JobStatusEnum, ActionSource, JobStatus
import os

SHORTCUTS_MD = """
# CyGuide Keyboard Shortcuts

## Dashboard (Engagement Management)
* **`Ctrl+N`**: New Workspace
* **`Ctrl+S`**: New Session
* **`F2`**: Rename Workspace/Session
* **`Ctrl+D`**: Delete Mode
* **`Ctrl+M`**: Organize (Move) Mode
* **`Space`**: Select item (in Delete/Organize modes)
* **`Ctrl+B`**: Toggle Sidebar
* **`Esc`**: Cancel Action
* **`Q`**: Quit Application

## Power Mode (Advanced Operator Workspace)
* **`Ctrl+G`**: Toggle Global Entity Graph (Workspace-wide view)
* **`Ctrl+N`**: Toggle Note Taking Scratchpad
* **`Ctrl+E`**: Export Session Report & Database Archive
* **`Ctrl+T`**: Open New Terminal Tab
* **`Ctrl+W`**: Close Current Terminal Tab
* **`Ctrl+K`**: Kill Running Job
* **`Ctrl+PageUp / PageDown`**: Switch Terminal Tabs
* **`Ctrl+Tab / Ctrl+Shift+Tab`**: Switch Sessions
* **`Ctrl+B`**: Toggle Sidebar (Hide Browser & Job Queue)
* **`Ctrl+L`**: Toggle Raw Shell Lock
* **`?` or `help`**: Show this shortcuts menu
* **`Esc`**: Return to Dashboard

## Learning Mode
* **`Ctrl+L`**: Return to Dashboard (from Learning Mode)
* **`Q`**: Quit Application
"""

class ShortcutsDialog(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="shortcuts_dialog"):
            yield Markdown(SHORTCUTS_MD)
            with Horizontal(classes="dialog_buttons"):
                yield Button("Close", variant="primary", id="close_shortcuts")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_shortcuts":
            self.dismiss()

class PowerModeScreen(Screen):
    """The advanced operator workspace."""

    BINDINGS = [
        Binding("ctrl+t", "new_terminal_tab", "New Tab"),
        Binding("ctrl+w", "close_terminal_tab", "Close Tab"),
        Binding("ctrl+k", "kill_job", "Kill Job"),
        Binding("ctrl+e", "export_session", "Export Session"),
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        Binding("ctrl+l", "toggle_shell_lock", "Toggle Lock"),
        Binding("ctrl+n", "toggle_scratchpad", "Toggle Scratchpad"),
        Binding("ctrl+g", "toggle_global_graph", "Toggle Global Graph"),
        Binding("ctrl+pageup", "prev_tab", "Prev Tab"),
        Binding("ctrl+pagedown", "next_tab", "Next Tab"),
        Binding("escape", "nav_dashboard", "Dashboard"),
        Binding("ctrl+tab", "next_session", "Next Session"),
        Binding("ctrl+shift+tab", "prev_session", "Prev Session"),
        Binding("ctrl+right", "next_session", "Next Session (Alt)"),
        Binding("ctrl+left", "prev_session", "Prev Session (Alt)"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_session_id: Optional[str] = None
        self.selected_node_id: Optional[str] = None
        self.terminal_count: int = 0
        # Maps tab_id (str) -> job_id (str)
        self.tab_to_job: Dict[str, str] = {}
        self.scratchpad_file = "data/.cyguide_scratchpad.md"
        self.show_global_graph: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen_container"):
            # Sidebar: Browser + Jobs - Now extends to the full height of the app
            with Vertical(id="power_sidebar"):
                yield Label("SESSION: -", id="session_label")
                yield EntityBrowser(id="entity_browser")
                yield JobQueue(id="job_queue")
                yield SuggestionsPane(id="suggestions_pane")
            
            # Right Pane: Workbench (Top) + Command Palette (Bottom)
            with Vertical(id="power_right_pane"):
                with Vertical(id="power_workbench"):
                    with TabbedContent(id="job_tabs"):
                        pass
                
                yield CommandPalette(id="command_palette")
                
            # Scratchpad pane (docked side pane)
            with Vertical(id="scratchpad_pane", classes="hidden"):
                yield Label("SCRATCHPAD", id="scratchpad_label", classes="section_header")
                yield TextArea(id="scratchpad_textarea", language="markdown")

        yield Static(
            "Terminal window too small. Please resize to at least 100x24 to use CyGuide.",
            id="size_warning",
            classes="hidden"
        )

    async def on_resize(self, event: events.Resize) -> None:
        is_too_small = event.size.width < 100 or event.size.height < 24
        try:
            container = self.query_one("#screen_container")
            warning = self.query_one("#size_warning")
            
            if is_too_small:
                container.add_class("hidden")
                warning.remove_class("hidden")
            else:
                container.remove_class("hidden")
                warning.add_class("hidden")
                cmd_input = self.query_one("#command_input", Input)
                if cmd_input:
                    cmd_input.focus()
        except Exception:
            pass

    async def on_mount(self) -> None:
        self.active_session_id = self.app.selected_session_id
        if not self.active_session_id:
            self.notify("No active session found. Returning to dashboard.", severity="error")
            self.app.switch_screen("dashboard")
            return

        await self._restore_tabs()
        await self.refresh_ui()
        self.app.store.on_upsert(self.handle_live_update)

    async def on_screen_resume(self) -> None:
        """Triggered when the screen is resumed (switched back to)."""
        target_id = self.app.selected_session_id or self.active_session_id
        if not target_id:
            self.app.switch_screen("dashboard")
            return
            
        session_data = await self.app.store.get_session(target_id)
        if not session_data:
            self.notify("Session no longer exists.", severity="error")
            self.app.selected_session_id = None
            self.active_session_id = None
            self.app.switch_screen("dashboard")
            return

        if target_id != self.active_session_id:
            self.active_session_id = target_id
            
            tabs = self.query_one("#job_tabs", TabbedContent)
            children = list(tabs.query(TabPane))
            for child in children:
                await tabs.remove_pane(child.id)
            
            self.tab_to_job.clear()
            self.terminal_count = 0
            self.selected_node_id = None
            
            await self._restore_tabs()
            
        await self.refresh_ui()

    async def _restore_tabs(self) -> None:
        """Restore previous job tabs from the event log."""
        if not self.active_session_id: return
        events = await self.app.power_facade.get_session_events(self.active_session_id)
        
        import json
        from rich.text import Text
        
        for event in events:
            if event.get("schema_type") != "system.event":
                continue
                
            action_payload = event.get("action_payload")
            result_payload = event.get("result_payload")
            
            if not action_payload or not result_payload:
                continue
                
            try:
                action = json.loads(action_payload)
                result = json.loads(result_payload)
            except Exception:
                continue
                
            if "output" not in result:
                continue
                
            tool_name = action.get("tool_name", "unknown")
            is_explicit = action.get("is_explicit_shell", False)
            title_prefix = "[sh] " if is_explicit else ""
            action_id = action.get("action_id", "unknown")
            
            if action_id in self.app.power_facade.closed_job_ids:
                continue
                
            short_id = str(action_id)[:4]
            title = f"{title_prefix}{tool_name} {short_id}"
            
            tab_id = await self.action_new_terminal_tab(title=title)
            
            # Map restored tab to job queue
            if action_id != "unknown":
                try:
                    job_uuid = UUID(action_id)
                    self.tab_to_job[tab_id] = str(job_uuid)
                    
                    status = JobStatusEnum.FAILED if result.get("error") else JobStatusEnum.DONE
                    
                    # Ensure we have UTC timezone imported or use a naive fallback
                    from datetime import timezone
                    
                    job = JobStatus(
                        job_id=job_uuid,
                        session_id=UUID(self.active_session_id),
                        tool_name=tool_name,
                        status=status,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc)
                    )
                    self.app.power_facade._active_jobs[job_uuid] = job
                except Exception as e:
                    pass
            
            job_log = self.query_one(f"#log_{tab_id}", RichLog)
            
            params = action.get("params", {})
            raw_flags = params.get("raw_flags", "")
            
            # Since expanded_params is a list in handle_submission, but raw_flags is a string,
            # we can just print raw_flags directly.
            job_log.write(f"\n[bold #8b949e]❯ {tool_name} {raw_flags}[/bold #8b949e]\n")
            job_log.write(Text.from_ansi(result["output"]))
            
            if "error" in result:
                err = result["error"]
                if err == "Terminated manually":
                    job_log.write(f"\n[bold #f85149]SIGTERM: Job terminated by operator.[/bold #f85149]\n")
                else:
                    job_log.write(f"[red]Error: {err}[/red]")

    async def refresh_ui(self) -> None:
        if not self.active_session_id: return
        
        ctx = await self.app.power_facade.get_context(
            self.active_session_id, 
            self.selected_node_id
        )
        
        try:
            self.query_one("#session_label", Label).update(f"SESSION: {ctx.session_name}")
        except Exception: pass
        
        if self.show_global_graph:
            session_data = await self.app.store.get_session(self.active_session_id)
            if session_data:
                graph_data = await self.app.power_facade.get_workspace_graph_snapshot(session_data["workspace_id"])
            else:
                graph_data = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
        else:
            graph_data = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
            
        try:
            await self.query_one("#entity_browser", EntityBrowser).refresh_entities(graph_data)
        except Exception: pass
        
        try:
            await self.query_one("#job_queue", JobQueue).update_jobs(ctx.active_jobs)
        except Exception: pass
        
        try:
            proposed = await self.app.power_facade.get_proposed_findings(self.active_session_id)
            await self.query_one("#suggestions_pane", SuggestionsPane).update_suggestions(proposed)
        except Exception: pass
        
        palette = self.query_one("#command_palette", CommandPalette)
        palette.update_context(ctx.resolved_vars, is_registered_tool=True, cwd=ctx.cwd)
        self.query_one("#command_input", Input).focus()

    async def handle_live_update(self, session_id: str, finding: Any) -> None:
        if session_id == self.active_session_id:
            if self.show_global_graph:
                session_data = await self.app.store.get_session(self.active_session_id)
                if session_data:
                    nodes = await self.app.power_facade.get_workspace_graph_snapshot(session_data["workspace_id"])
                else:
                    nodes = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
            else:
                nodes = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
            try:
                await self.query_one("#entity_browser", EntityBrowser).refresh_entities(nodes)
            except Exception: pass

    async def on_job_queue_job_selected(self, event: JobQueue.JobSelected) -> None:
        if event.session_id != self.active_session_id:
            self.app.selected_session_id = event.session_id
            await self.on_screen_resume()
            session_data = await self.app.store.get_session(event.session_id)
            if session_data:
                self.notify(f"Switched to session: {session_data['name']}")
                
        for tab_id, job_id in self.tab_to_job.items():
            if job_id == event.job_id:
                self.query_one("#job_tabs", TabbedContent).active = tab_id
                break

    async def on_suggestions_pane_approved(self, event: SuggestionsPane.Approved) -> None:
        """Handle suggestion approval: populate the command prompt with the recommended command."""
        palette = self.query_one("#command_palette", CommandPalette)
        cmd_input = self.query_one("#command_input", Input)
        
        # Determine active prefix (shell lock vs normal tool mode)
        prefix = "! " if palette.shell_locked else "> "
        cmd_input.value = prefix + event.recommended_command
        
        # Focus input and place cursor at the end so user can edit/run
        cmd_input.focus()
        cmd_input.cursor_position = len(cmd_input.value)

    async def on_suggestions_pane_dismissed(self, event: SuggestionsPane.Dismissed) -> None:
        """Handle suggestion dismissal: delete from database."""
        await self.app.power_facade.dismiss_proposed_finding(self.active_session_id, event.schema_type, event.pik)
        self.notify("Suggestion dismissed.")
        await self.refresh_ui()

    async def on_tree_node_highlighted(self, event: EntityBrowser.NodeHighlighted) -> None:
        if event.node.data:
            self.selected_node_id = event.node.data.get("id")
            await self.refresh_ui()

    async def on_tree_node_selected(self, event: EntityBrowser.NodeSelected) -> None:
        if event.node.data:
            self.selected_node_id = event.node.data.get("id")
            await self.refresh_ui()

    async def action_new_terminal_tab(self, title: Optional[str] = None) -> str:
        self.terminal_count += 1
        tab_id = f"term_{self.terminal_count}"
        display_title = title or f"Terminal #{self.terminal_count}"
        
        job_log = RichLog(id=f"log_{tab_id}", highlight=False, markup=False, max_lines=10000)
        tabs = self.query_one("#job_tabs", TabbedContent)
        await tabs.add_pane(TabPane(display_title, job_log, id=tab_id))
        tabs.active = tab_id
        return tab_id

    async def on_command_palette_submitted(self, event: CommandPalette.Submitted) -> None:
        self.run_worker(self._handle_submission(event))

    async def _handle_submission(self, event: CommandPalette.Submitted) -> None:
        palette = self.query_one("#command_palette", CommandPalette)
        tool_name = event.tool_name
        expanded_params = event.expanded_params
        
        action = ActionRequest(
            session_id=UUID(self.active_session_id),
            tool_name=tool_name,
            target_entity_id=self.selected_node_id,
            params={"raw_flags": " ".join(expanded_params)},
            triggered_by=ActionSource.USER,
            is_explicit_shell=event.is_manual_shell or palette.shell_locked
        )

        is_builtin = tool_name in ["cd", "clear", "?", "help"]
        
        if tool_name in ["?", "help"]:
            self.app.push_screen(ShortcutsDialog())
            return
        elif tool_name == "clear":
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if active_tab_id:
                log = self.query_one(f"#log_{active_tab_id}", RichLog)
                log.clear()
            return

        try:
            await self.app.power_facade.gateway.validate_action(action)
        except Exception as e:
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if not active_tab_id:
                active_tab_id = await self.action_new_terminal_tab(title=f"Error: {tool_name}")
            
            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            job_log.write(f"\n[red]Validation Error: {str(e)}[/red]\n")
            return

        is_sudo = tool_name == "sudo"
        if (palette.shell_locked or is_sudo) and not is_builtin:
            if is_sudo:
                tabs = self.query_one("#job_tabs", TabbedContent)
                active_tab_id = tabs.active
                if not active_tab_id:
                    active_tab_id = await self.action_new_terminal_tab(title=f"sudo {expanded_params[0] if expanded_params else ''}")
                
                job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
                job_log.write(f"\n[bold #8b949e]❯ sudo {' '.join(expanded_params)}[/bold #8b949e]\n")
                job_log.write(f"[italic #8b949e]Suspending for sudo password entry...[/italic #8b949e]\n")

            with self.app.suspend():
                import subprocess
                full_cmd = f"{tool_name} {' '.join(expanded_params)}"
                subprocess.run(full_cmd, shell=True, executable=self.app.user_shell, env=self.app.user_env)
            
            if is_sudo:
                job_log.write(f"[italic #3fb950]Resumed from sudo.[/italic #3fb950]\n")

            await self.refresh_ui()
            return

        # BACKGROUND MODE: Tab reuse logic
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        title_prefix = "[sh] " if action.is_explicit_shell else ""
        title = f"{title_prefix}{tool_name} {action.action_id.hex[:4]}"

        # Determine if we need a new tab
        needs_new_tab = event.new_tab
        
        if not needs_new_tab and active_tab_id and active_tab_id.startswith("term_"):
            if active_tab_id in self.tab_to_job:
                # Check if the job in the current tab is still running
                job_id = self.tab_to_job[active_tab_id]
                try:
                    job = self.app.power_facade._active_jobs.get(UUID(job_id))
                    if job and job.status == JobStatusEnum.RUNNING:
                        needs_new_tab = True
                except Exception:
                    pass
        elif not active_tab_id or not active_tab_id.startswith("term_"):
            needs_new_tab = True

        if needs_new_tab:
            active_tab_id = await self.action_new_terminal_tab(title=title)
            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
        else:
            # Reusing the tab, so remove the old job from the Job Queue tracking
            if active_tab_id in self.tab_to_job:
                old_job_id = self.tab_to_job[active_tab_id]
                try:
                    await self.app.power_facade.remove_job(UUID(old_job_id))
                except Exception:
                    pass

            # Rename the existing tab
            for pane in tabs.query(TabPane):
                if pane.id == active_tab_id:
                    pane.title = title
                    try:
                        tab_widget = tabs.query_one(f"#tab-{active_tab_id}")
                        tab_widget.update(title)
                    except Exception:
                        pass
                    break
            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            # We explicitly do not clear the log here so that consecutive commands
            # in the same tab appear below the previous ones, mimicking a real shell.

        self.tab_to_job[active_tab_id] = str(action.action_id)
        job_log.write(f"\n[bold #8b949e]❯ {tool_name} {' '.join(expanded_params)}[/bold #8b949e]\n")

        try:
            from rich.text import Text
            async def stream_output(text: str):
                job_log.write(Text.from_ansi(text))
                await asyncio.sleep(0)
            async def stream_error(text: str):
                job_log.write(Text.from_ansi(text))
                await asyncio.sleep(0)
            async def on_complete():
                await self.refresh_ui()

            await self.app.power_facade.submit_action(
                action, 
                on_output=stream_output, 
                on_complete=on_complete,
                on_error_output=stream_error
            )
            await self.refresh_ui()
        except Exception as e:
            job_log.write(f"[red]Error: {str(e)}[/red]")
            await self.refresh_ui()

    def on_click(self) -> None:
        self.query_one("#command_input", Input).focus()

    def on_blur(self) -> None:
        self.query_one("#command_input", Input).focus()

    def action_toggle_sidebar(self) -> None:
        self.query_one("#power_sidebar").toggle_class("collapsed")

    def action_nav_dashboard(self) -> None:
        self.app.switch_screen("dashboard")

    def action_toggle_shell_lock(self) -> None:
        palette = self.query_one("#command_palette", CommandPalette)
        palette.shell_locked = not palette.shell_locked
        cmd_input = self.query_one("#command_input", Input)
        if palette.shell_locked:
            if cmd_input.value.startswith(">"):
                cmd_input.value = "!" + cmd_input.value[1:]
        else:
            if cmd_input.value.startswith("!"):
                cmd_input.value = "> " + cmd_input.value[1:].lstrip()
        cmd_input.focus()
        self.run_worker(self.refresh_ui())

    async def action_next_tab(self) -> None:
        """Switch to the next workbench tab."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        children = list(tabs.query(TabPane))
        if not children: return
        current_idx = next((i for i, c in enumerate(children) if c.id == tabs.active), 0)
        tabs.active = children[(current_idx + 1) % len(children)].id

    async def action_prev_tab(self) -> None:
        """Switch to the previous workbench tab."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        children = list(tabs.query(TabPane))
        if not children: return
        current_idx = next((i for i, c in enumerate(children) if c.id == tabs.active), 0)
        tabs.active = children[(current_idx - 1) % len(children)].id

    async def action_next_session(self) -> None:
        """Switch to the next session in the current workspace."""
        if not self.active_session_id: return
        
        session_data = await self.app.store.get_session(self.active_session_id)
        if not session_data: return
        
        workspace_id = session_data["workspace_id"]
        sessions = await self.app.store.list_sessions(workspace_id)
        if not sessions or len(sessions) <= 1:
            return
            
        current_idx = -1
        for i, s in enumerate(sessions):
            if s["id"] == self.active_session_id:
                current_idx = i
                break
                
        if current_idx != -1:
            next_idx = (current_idx + 1) % len(sessions)
            next_session_id = sessions[next_idx]["id"]
            
            self.app.selected_session_id = next_session_id
            await self.on_screen_resume()
            self.notify(f"Switched to session: {sessions[next_idx]['name']}")

    async def action_prev_session(self) -> None:
        """Switch to the previous session in the current workspace."""
        if not self.active_session_id: return
        
        session_data = await self.app.store.get_session(self.active_session_id)
        if not session_data: return
        
        workspace_id = session_data["workspace_id"]
        sessions = await self.app.store.list_sessions(workspace_id)
        if not sessions or len(sessions) <= 1:
            return
            
        current_idx = -1
        for i, s in enumerate(sessions):
            if s["id"] == self.active_session_id:
                current_idx = i
                break
                
        if current_idx != -1:
            prev_idx = (current_idx - 1) % len(sessions)
            prev_session_id = sessions[prev_idx]["id"]
            
            self.app.selected_session_id = prev_session_id
            await self.on_screen_resume()
            self.notify(f"Switched to session: {sessions[prev_idx]['name']}")

    async def action_close_terminal_tab(self) -> None:
        """Close the currently active terminal tab, """
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        if not active_tab_id:
            return
            
        # Kill and remove job if it exists
        target_job_id = self.tab_to_job.get(active_tab_id)
        if target_job_id:
            await self.app.power_facade.executor.stop_task(target_job_id)
            await self.app.power_facade.remove_job(UUID(target_job_id))
            self.tab_to_job.pop(active_tab_id)
            
        await tabs.remove_pane(active_tab_id)
        await self.refresh_ui()

    async def action_kill_job(self) -> None:
        """Terminate the job in the currently active tab."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        if not active_tab_id:
            return
            
        target_job_id = self.tab_to_job.get(active_tab_id)
        
        if target_job_id:
            try:
                # Get the log to show feedback
                job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
                
                await self.app.power_facade.kill_job(UUID(target_job_id))
                job_log.write(f"\n[bold #f85149]SIGTERM: Job terminated by operator.[/bold #f85149]\n")
                
                # Refresh to update status icon in sidebar
                await self.refresh_ui()
            except Exception as e:
                # Silently fail if log isn't found or other UI issues
                pass

    async def on_command_palette_close_tab_request(self, event: CommandPalette.CloseTabRequest) -> None:
        """Handle Close Tab request from the command palette (bypassing Input widget)."""
        await self.action_close_terminal_tab()

    async def on_command_palette_kill_job_request(self, event: CommandPalette.KillJobRequest) -> None:
        """Handle Kill Job request from the command palette (bypassing Input widget)."""
        await self.action_kill_job()

    async def on_command_palette_next_session_request(self, event: CommandPalette.NextSessionRequest) -> None:
        """Handle Next Session request from the command palette."""
        await self.action_next_session()

    async def on_command_palette_prev_session_request(self, event: CommandPalette.PrevSessionRequest) -> None:
        """Handle Prev Session request from the command palette."""
        await self.action_prev_session()

    async def on_command_palette_export_request(self, event: CommandPalette.ExportRequest) -> None:
        """Handle Export request from the command palette (bypassing Input widget)."""
        await self.action_export_session()

    def _load_scratchpad(self) -> None:
        try:
            if os.path.exists(self.scratchpad_file):
                with open(self.scratchpad_file, "r") as f:
                    content = f.read()
                self.query_one("#scratchpad_textarea", TextArea).load_text(content)
        except Exception:
            pass

    def _save_scratchpad(self) -> None:
        try:
            content = self.query_one("#scratchpad_textarea", TextArea).text
            with open(self.scratchpad_file, "w") as f:
                f.write(content)
        except Exception:
            pass

    async def action_toggle_global_graph(self) -> None:
        self.show_global_graph = not self.show_global_graph
        status = "Global (Workspace)" if self.show_global_graph else "Local (Session)"
        self.notify(f"Entity Graph scoped to: {status}")
        await self.refresh_ui()

    def action_toggle_scratchpad(self) -> None:
        pane = self.query_one("#scratchpad_pane")
        if pane.has_class("hidden"):
            self._load_scratchpad()
            pane.remove_class("hidden")
            self.query_one("#scratchpad_textarea", TextArea).focus()
        else:
            self._save_scratchpad()
            pane.add_class("hidden")
            self.query_one("#command_input", Input).focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "scratchpad_textarea":
            self._save_scratchpad()

    async def action_export_session(self) -> None:
        """Export the current session's findings to a Markdown report and database archive."""
        if not self.active_session_id:
            self.notify("No active session to export.", severity="error")
            return
            
        try:
            os.makedirs("reports", exist_ok=True)
            os.makedirs("exports", exist_ok=True)
            
            session = await self.app.store.get_session(self.active_session_id)
            if not session:
                self.notify("Session not found.", severity="error")
                return
                
            session_name = session["name"]
            import re
            slug = re.sub(r'[^a-zA-Z0-9_-]', '_', session_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            report_path = os.path.abspath(f"reports/report_{slug}_{timestamp}.md")
            db_path = os.path.abspath(f"exports/archive_{slug}_{timestamp}.db")
            
            # Generate Report
            from cyguide.engine.reporter import generate_markdown_report
            report_content = await generate_markdown_report(self.app.store, self.active_session_id)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
                
            # Export DB
            await self.app.power_facade.export_session(self.active_session_id, db_path)
            
            self.notify(f"Report: reports/report_{slug}_{timestamp}.md")
            self.notify(f"Database: exports/archive_{slug}_{timestamp}.db")
        except Exception as e:
            self.notify(f"Export failed: {str(e)}", severity="error")

