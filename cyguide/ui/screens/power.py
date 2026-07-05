"""The main Power Mode screen for advanced investigation."""

from typing import Optional, Dict, List, Any
from uuid import UUID
from datetime import datetime
import asyncio
from textual import events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import TabbedContent, TabPane, RichLog, Input, Label, Static
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

from cyguide.ui.widgets.power import EntityBrowser, JobQueue, CommandPalette
from cyguide.schemas.power import ActionRequest, JobStatusEnum, ActionSource

class PowerModeScreen(Screen):
    """The advanced operator workspace."""

    BINDINGS = [
        Binding("ctrl+t", "new_terminal_tab", "New Tab"),
        Binding("ctrl+w", "close_terminal_tab", "Close Tab"),
        Binding("ctrl+k", "kill_job", "Kill Job"),
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        Binding("ctrl+l", "toggle_shell_lock", "Toggle Lock"),
        Binding("ctrl+pageup", "prev_tab", "Prev Tab"),
        Binding("ctrl+pagedown", "next_tab", "Next Tab"),
        Binding("escape", "nav_dashboard", "Dashboard"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.active_session_id: Optional[str] = None
        self.selected_node_id: Optional[str] = None
        self.terminal_count: int = 0
        # Maps tab_id (str) -> job_id (str)
        self.tab_to_job: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen_container"):
            # Sidebar: Browser + Jobs - Now extends to the full height of the app
            with Vertical(id="power_sidebar"):
                yield Label("SESSION: -", id="session_label")
                yield EntityBrowser(id="entity_browser")
                yield JobQueue(id="job_queue")
            
            # Right Pane: Workbench (Top) + Command Palette (Bottom)
            with Vertical(id="power_right_pane"):
                with Vertical(id="power_workbench"):
                    with TabbedContent(id="job_tabs"):
                        with TabPane("Overview", id="tab_overview"):
                            yield RichLog(id="overview_log", highlight=True, markup=True)
                
                yield CommandPalette(id="command_palette")

        yield Static(
            "Terminal window too small. Please resize to at least 100x24 to use CyGuide.",
            id="size_warning",
            classes="hidden"
        )

    async def on_resize(self, event: events.Resize) -> None:
        is_too_small = event.size.width < 100 or event.size.height < 24
        container = self.query_one("#screen_container")
        warning = self.query_one("#size_warning")
        
        if is_too_small:
            container.add_class("hidden")
            warning.remove_class("hidden")
        else:
            container.remove_class("hidden")
            warning.add_class("hidden")
            self.query_one("#command_input", Input).focus()

    async def on_mount(self) -> None:
        self.active_session_id = self.app.selected_session_id
        if not self.active_session_id:
            self.notify("No active session found. Returning to dashboard.", severity="error")
            self.app.switch_screen("dashboard")
            return

        await self.refresh_ui()
        self.app.store.on_upsert(self.handle_live_update)

    async def refresh_ui(self) -> None:
        if not self.active_session_id: return
        
        ctx = await self.app.power_facade.get_context(
            self.active_session_id, 
            self.selected_node_id
        )
        
        try:
            self.query_one("#session_label", Label).update(f"SESSION: {ctx.session_name}")
        except: pass
        
        nodes = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
        try:
            await self.query_one("#entity_browser", EntityBrowser).refresh_entities(nodes)
        except: pass
        
        try:
            await self.query_one("#job_queue", JobQueue).update_jobs(ctx.active_jobs)
        except: pass
        
        palette = self.query_one("#command_palette", CommandPalette)
        palette.update_context(ctx.resolved_vars, is_registered_tool=True, cwd=ctx.cwd)
        self.query_one("#command_input", Input).focus()

    async def handle_live_update(self, session_id: str, finding: Any) -> None:
        if session_id == self.active_session_id:
            nodes = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
            try:
                await self.query_one("#entity_browser", EntityBrowser).refresh_entities(nodes)
            except: pass

    async def on_job_queue_job_selected(self, event: JobQueue.JobSelected) -> None:
        for tab_id, job_id in self.tab_to_job.items():
            if job_id == event.job_id:
                self.query_one("#job_tabs", TabbedContent).active = tab_id
                break

    async def on_tree_node_highlighted(self, event: EntityBrowser.NodeHighlighted) -> None:
        if event.node.data:
            self.selected_node_id = event.node.data.get("id")
            await self.refresh_ui()

    async def action_new_terminal_tab(self, title: Optional[str] = None) -> str:
        self.terminal_count += 1
        tab_id = f"term_{self.terminal_count}"
        display_title = title or f"Terminal #{self.terminal_count}"
        
        job_log = RichLog(id=f"log_{tab_id}", highlight=True, markup=True)
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

        is_builtin = tool_name in ["cd", "clear"]
        if tool_name == "clear":
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if active_tab_id and active_tab_id != "tab_overview":
                log = self.query_one(f"#log_{active_tab_id}", RichLog)
                log.clear()
            return

        try:
            await self.app.power_facade.gateway.validate_action(action)
        except Exception as e:
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if not active_tab_id or active_tab_id == "tab_overview":
                active_tab_id = await self.action_new_terminal_tab(title=f"Error: {tool_name}")
            
            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            job_log.write(f"\n[red]Validation Error: {str(e)}[/red]\n")
            return

        is_sudo = tool_name == "sudo"
        if (palette.shell_locked or is_sudo) and not is_builtin:
            if is_sudo:
                tabs = self.query_one("#job_tabs", TabbedContent)
                active_tab_id = tabs.active
                if not active_tab_id or active_tab_id == "tab_overview":
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

        # BACKGROUND MODE: New tab per job unless on a manually created empty tab
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        title_prefix = "[sh] " if action.is_explicit_shell else ""
        title = f"{title_prefix}{tool_name} {action.action_id.hex[:4]}"

        # If on a manually created terminal tab that hasn't run a job yet, rename it
        if active_tab_id and active_tab_id.startswith("term_") and active_tab_id not in self.tab_to_job:
            # Update the title of the current pane
            for pane in tabs.query(TabPane):
                if pane.id == active_tab_id:
                    pane.title = title
                    # Textual TabbedContent needs the internal Tab label updated explicitly
                    try:
                        tab_widget = tabs.query_one(f"#tab-{active_tab_id}")
                        tab_widget.update(title)
                    except:
                        pass
                    break
        else:
            # Create a new tab
            active_tab_id = await self.action_new_terminal_tab(title=title)
            
        job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
        self.tab_to_job[active_tab_id] = str(action.action_id)
        job_log.write(f"\n[bold #8b949e]❯ {tool_name} {' '.join(expanded_params)}[/bold #8b949e]\n")

        try:
            from rich.text import Text
            async def stream_output(text: str):
                job_log.write(Text.from_ansi(text))
            async def stream_error(text: str):
                job_log.write(Text.from_ansi(text))
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

    async def action_close_terminal_tab(self) -> None:
        """Close the currently active terminal tab, unless it's the overview."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        if not active_tab_id or active_tab_id == "tab_overview":
            return
            
        # Kill and remove job if it exists
        target_job_id = self.tab_to_job.get(active_tab_id)
        if target_job_id:
            await self.app.power_facade.executor.stop_task(target_job_id)
            self.app.power_facade.remove_job(UUID(target_job_id))
            self.tab_to_job.pop(active_tab_id)
            
        await tabs.remove_pane(active_tab_id)
        await self.refresh_ui()

    async def action_kill_job(self) -> None:
        """Terminate the job in the currently active tab."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        
        if not active_tab_id or active_tab_id == "tab_overview":
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
