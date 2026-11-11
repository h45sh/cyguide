"""The main Power Mode screen for advanced investigation."""

import asyncio
import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    Markdown,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from cyguide.paths import get_default_exports_dir, get_default_reports_dir
from cyguide.schemas.power import ActionRequest, ActionSource, JobStatus, JobStatusEnum
from cyguide.ui.widgets.power import CommandPalette, EntityBrowser, JobQueue
from cyguide.ui.widgets.resizer import ResizeHandle

SHORTCUTS_MD = """
# CyGuide Keyboard Shortcuts & Hotkeys

## Global & Help
* **`F1` / `Ctrl+/`**: Show this Keyboard Shortcuts & Hotkeys Help dialog
* **`Ctrl+P`**: Open Command Palette (e.g. Toggle Animations)
* **`Q` / `Ctrl+Q`**: Quit Application

## Dashboard (Engagement Management)
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+N`**: New Workspace
* **`Ctrl+S`**: New Session
* **`Ctrl+H`**: Toggle Session History (Active vs. Archived)
* **`Ctrl+A` / `c`**: Archive / Reopen Engagement
* **`F2`**: Rename highlighted Workspace or Session inline
* **`Ctrl+D`**: Toggle Delete Mode / Confirm Deletion
* **`Ctrl+M`**: Toggle Organize (Move) Mode / Confirm Move
* **`Space`**: Select/check item (in Delete/Organize modes)
* **`Ctrl+B`**: Toggle Workspace Sidebar
* **`Ctrl+L`**: Switch to Learning Mode
* **`Esc`**: Cancel Action / Mode
* **`Q`**: Quit Application

## Power Mode (Advanced Operator Workspace)
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+T`**: Open New Terminal Tab
* **`Ctrl+W`**: Close Active Terminal Tab
* **`Ctrl+Y`**: Copy Active Terminal Tab Log to Clipboard
* **`Ctrl+K`**: Kill / Terminate Running Job (`SIGTERM`)
* **`Ctrl+R`**: Reopen Archived Session (Restores Write Mode)
* **`Ctrl+PageUp / PageDown`**: Switch Terminal Tabs
* **`Shift+Enter` / `Alt+Enter` / `Ctrl+J`**: Run Command in New Tab
* **`Ctrl+Tab / Ctrl+Shift+Tab`**: Switch Sessions
* **`Ctrl+Right / Ctrl+Left`**: Switch Sessions (Alt)
* **`Ctrl+B`**: Toggle Sidebar (Hide Browser & Job Queue)
* **`Ctrl+N`**: Toggle Note Taking Scratchpad
* **`Ctrl+G`**: Toggle Global Entity Graph (Workspace-wide view)
* **`Ctrl+E`**: Export Session Report & Database Archive
* **`Ctrl+L`**: Toggle Raw Shell Lock
* **`!` prefix**: One-time Raw Shell Command
* **`Tab`**: Auto-complete Filenames (in Shell-Locked mode)
* **`Up / Down`**: Command History
* **`?` or `help`**: Show this shortcuts menu
* **`Esc`**: Return to Dashboard

## Entity Browser
* **`Enter` / Click**: Select Entity Node

## Learning Mode
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+B`**: Toggle Lesson Sidebar
* **`Esc`**: Return to Tool Browser / Dashboard
* **`Q`**: Quit Application
"""

class ShortcutsDialog(ModalScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("f1", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="shortcuts_dialog"):
            yield Markdown(SHORTCUTS_MD)
            with Horizontal(classes="dialog_buttons"):
                yield Button("Close", variant="primary", id="close_shortcuts")

    def on_mount(self) -> None:
        def focus_close():
            try:
                self.query_one("#close_shortcuts", Button).focus()
            except Exception:
                pass
        self.call_after_refresh(focus_close)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_shortcuts":
            self.dismiss()

class PowerModeScreen(Screen):
    """The advanced operator workspace."""

    BINDINGS = [
        Binding("f1", "show_shortcuts", "Help"),
        Binding("ctrl+t", "new_terminal_tab", "New Tab"),
        Binding("ctrl+w", "close_terminal_tab", "Close Tab"),
        Binding("ctrl+y", "copy_active_tab", "Copy Tab Log"),
        Binding("ctrl+k", "kill_job", "Kill Job"),
        Binding("ctrl+r", "reopen_session", "Reopen Session", show=False),
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
        self._scratchpad_file: Optional[str] = None
        self.show_global_graph: bool = False
        self._active_subscriptions: Dict[UUID, Callable] = {}

    @property
    def scratchpad_file(self) -> str:
        if hasattr(self, "_scratchpad_file") and self._scratchpad_file is not None:
            return self._scratchpad_file
        if hasattr(self, "app") and hasattr(self.app, "get_scratchpad_path"):
            return self.app.get_scratchpad_path()
        return "scratchpad.md"

    @scratchpad_file.setter
    def scratchpad_file(self, val: str) -> None:
        self._scratchpad_file = val

    def compose(self) -> ComposeResult:
        with Horizontal(id="screen_container"):
            # Sidebar: Browser + Jobs - Now extends to the full height of the app
            with Vertical(id="power_sidebar"):
                yield Label("◆ SESSION: -", id="session_label")
                yield EntityBrowser(id="entity_browser")
                yield JobQueue(id="job_queue")

            # Left resizer handle for sidebar
            yield ResizeHandle(
                target_id="power_sidebar",
                side="left",
                min_size=16,
                max_size=70,
                setting_key="power_sidebar_width",
                id="sidebar_resizer",
            )

            # Center Pane: Workbench (Top) + Command Palette (Bottom)
            with Vertical(id="power_right_pane"):
                with Vertical(id="power_workbench"):
                    with TabbedContent(id="job_tabs"):
                        pass

                yield CommandPalette(id="command_palette")

            # Right resizer handle for scratchpad
            yield ResizeHandle(
                target_id="scratchpad_pane",
                side="right",
                min_size=20,
                max_size=70,
                setting_key="scratchpad_width",
                id="scratchpad_resizer",
                classes="hidden",
            )

            # Scratchpad pane (docked side pane)
            with Vertical(id="scratchpad_pane", classes="hidden"):
                with Horizontal(classes="pane_header"):
                    yield Label("◆ SCRATCHPAD", id="scratchpad_label", classes="pane_title")
                yield TextArea(id="scratchpad_textarea", language="markdown", theme="vscode_dark")


        yield Static(
            "Terminal window too small (minimum 75x15).\nPlease resize your terminal or press [Esc] for Dashboard.",
            id="size_warning",
            classes="hidden"
        )

    async def on_resize(self, event: events.Resize) -> None:
        is_too_small = event.size.width < 75 or event.size.height < 15
        try:
            container = self.query_one("#screen_container")
            warning = self.query_one("#size_warning")

            if is_too_small:
                container.add_class("hidden")
                warning.remove_class("hidden")
            else:
                container.remove_class("hidden")
                warning.add_class("hidden")
                try:
                    palette = self.query_one("#command_palette", CommandPalette)
                    palette.scroll_to(y=0, animate=False)
                except Exception:
                    pass
                cmd_input = self.query_one("#command_input", Input)
                if cmd_input:
                    cmd_input.focus()
        except Exception:
            pass

    async def on_mount(self) -> None:
        self.active_session_id = getattr(self.app, "selected_session_id", None)
        if not self.active_session_id:
            self.notify("No active session found. Returning to dashboard.", severity="error")
            if hasattr(self.app, "switch_screen"):
                try:
                    self.app.switch_screen("dashboard")
                except Exception:
                    pass
            return


        # Restore persistent pane widths
        if hasattr(self.app, "settings") and self.app.settings:
            saved_sb = self.app.settings.get("power_sidebar_width")
            if saved_sb:
                try:
                    self.query_one("#power_sidebar").styles.width = int(saved_sb)
                except Exception:
                    pass
            saved_sp = self.app.settings.get("scratchpad_width")
            if saved_sp:
                try:
                    self.query_one("#scratchpad_pane").styles.width = int(saved_sp)
                except Exception:
                    pass

        if hasattr(self.app, "power_facade"):
            self.app.power_facade.on_job_status_change(self._handle_job_status_change)
        await self._restore_tabs()
        await self.refresh_ui()
        self.app.store.on_upsert(self.handle_live_update)

    def on_unmount(self) -> None:
        if hasattr(self.app, "power_facade"):
            self.app.power_facade.remove_job_status_change(self._handle_job_status_change)
            for j_id, cb in list(self._active_subscriptions.items()):
                self.app.power_facade.unsubscribe_job_output(j_id, cb)
        self._active_subscriptions.clear()

    def _handle_job_status_change(self, job: JobStatus) -> None:
        """Handle real-time job status updates from power_facade."""
        if str(job.session_id) != str(self.active_session_id):
            return

        # If job completed or failed, remove subscription and clean tab title
        if job.status in (JobStatusEnum.DONE, JobStatusEnum.FAILED):
            cb = self._active_subscriptions.pop(job.job_id, None)
            if cb and hasattr(self.app, "power_facade"):
                self.app.power_facade.unsubscribe_job_output(job.job_id, cb)

            try:
                tabs = self.query_one("#job_tabs", TabbedContent)
                for tab_id, j_id in self.tab_to_job.items():
                    if j_id == str(job.job_id):
                        tab = tabs.get_tab(tab_id)
                        if tab:
                            tab.label = str(tab.label).replace("◌ ", "").replace("[◯] ", "")
                        for pane in tabs.query(TabPane):
                            if pane.id == tab_id:
                                pane.title = str(pane.title).replace("◌ ", "").replace("[◯] ", "")
                                break
                        break
            except Exception:
                pass

        self.run_worker(self.refresh_ui())

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
            # Clean up old subscriptions
            for j_id, cb in list(self._active_subscriptions.items()):
                self.app.power_facade.unsubscribe_job_output(j_id, cb)
            self._active_subscriptions.clear()

            self.active_session_id = target_id

            tabs = self.query_one("#job_tabs", TabbedContent)
            children = list(tabs.query(TabPane))
            for child in children:
                await tabs.remove_pane(child.id)

            self.tab_to_job.clear()
            self.terminal_count = 0
            self.selected_node_id = None

            await self._restore_tabs()

        try:
            palette = self.query_one("#command_palette", CommandPalette)
            palette.scroll_to(y=0, animate=False)
        except Exception:
            pass

        await self.refresh_ui()

    async def _restore_tabs(self) -> None:
        """Restore previous job tabs from the event log and active running jobs."""
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

            action_id = action.get("action_id", "unknown")
            if action_id in self.app.power_facade.closed_job_ids:
                continue

            # If this job is actively running in power_facade, let running restoration handle it
            try:
                j_uuid = UUID(action_id)
                active_job = self.app.power_facade._active_jobs.get(j_uuid)
                if active_job and active_job.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED):
                    continue
            except Exception:
                pass

            tool_name = action.get("tool_name", "unknown")
            is_explicit = action.get("is_explicit_shell", False)
            title_prefix = "sh › " if is_explicit else ""

            short_id = str(action_id)[:4]
            title = f"{title_prefix}{tool_name} {short_id}"

            tab_id = await self.action_new_terminal_tab(title=title)

            # Map restored tab to job queue
            if action_id != "unknown":
                try:
                    job_uuid = UUID(action_id)
                    self.tab_to_job[tab_id] = str(job_uuid)

                    status = JobStatusEnum.FAILED if result.get("error") else JobStatusEnum.DONE

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
            raw_flags = (params.get("raw_flags") or "").strip()

            if raw_flags.startswith(tool_name):
                cmd_display = raw_flags
            elif raw_flags:
                cmd_display = f"{tool_name} {raw_flags}"
            else:
                cmd_display = tool_name

            job_log.write(Text.from_markup(f"\n[bold #38bdf8]❯[/] [bold #e2e8f0]{escape(cmd_display)}[/]\n"))
            job_log.write(Text.from_ansi(result.get("output", "")))

            if result.get("error"):
                err = result["error"]
                if err == "Terminated manually":
                    job_log.write(Text.from_markup("\n[bold #f85149]SIGTERM: Job terminated by operator.[/]\n"))
                else:
                    job_log.write(Text.from_markup(f"\n[bold #f85149]Error:[/] [red]{escape(str(err))}[/]\n"))

        # Restore any active/running jobs for this session that do not yet have a tab
        running_jobs = [
            j for j in self.app.power_facade._active_jobs.values()
            if str(j.session_id) == str(self.active_session_id)
            and j.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
        ]

        for r_job in running_jobs:
            if str(r_job.job_id) in self.tab_to_job.values():
                continue
            action = self.app.power_facade.get_job_action(r_job.job_id)
            tool_name = r_job.tool_name or (action.tool_name if action else "job")
            is_explicit = action.is_explicit_shell if action else False
            title_prefix = "sh › " if is_explicit else ""
            short_id = str(r_job.job_id)[:4]
            title = f"◌ {title_prefix}{tool_name} {short_id}"

            tab_id = await self.action_new_terminal_tab(title=title)
            self.tab_to_job[tab_id] = str(r_job.job_id)

            job_log = self.query_one(f"#log_{tab_id}", RichLog)

            if action:
                params = action.params or {}
                raw_flags = (params.get("raw_flags") or "").strip()
                if raw_flags.startswith(tool_name):
                    cmd_display = raw_flags
                elif raw_flags:
                    cmd_display = f"{tool_name} {raw_flags}"
                else:
                    cmd_display = tool_name
            else:
                cmd_display = tool_name

            job_log.write(Text.from_markup(f"\n[bold #38bdf8]❯[/] [bold #e2e8f0]{escape(cmd_display)}[/]\n"))

            # Populate already accumulated output buffer
            buf = self.app.power_facade.get_job_buffer(r_job.job_id)
            if buf:
                job_log.write(Text.from_ansi(buf))

            # Subscribe to live streaming output chunks
            def make_chunk_subscriber(target_log):
                async def _on_chunk(chunk: str):
                    try:
                        target_log.write(Text.from_ansi(chunk))
                    except Exception:
                        pass
                return _on_chunk

            chunk_cb = make_chunk_subscriber(job_log)
            self._active_subscriptions[r_job.job_id] = chunk_cb
            self.app.power_facade.subscribe_job_output(r_job.job_id, chunk_cb)

    async def refresh_ui(self) -> None:
        if not self.active_session_id: return

        ctx = await self.app.power_facade.get_context(
            self.active_session_id,
            self.selected_node_id
        )

        session_data = await self.app.store.get_session(self.active_session_id)
        is_closed = session_data and session_data.get("status") == "CLOSED"
        running_cnt = self.app.power_facade.get_active_jobs_count(self.active_session_id)

        try:
            if is_closed:
                status_suffix = " [dim #64748b]⊘ ARCHIVED[/]"
                badge_len = len(" ⊘ ARCHIVED")
            elif running_cnt > 0:
                status_suffix = f" [bold #34d399]● {running_cnt} RUNNING[/]"
                badge_len = len(f" ● {running_cnt} RUNNING")
            else:
                status_suffix = " [dim #38bdf8]▪ IDLE[/]"
                badge_len = len(" ▪ IDLE")

            # In a 34-column sidebar, usable text width is ~30 characters.
            sess_name = ctx.session_name
            if sess_name.lower().startswith("session"):
                base_title = f"◆ {sess_name}"
            else:
                base_title = f"◆ SESSION: {sess_name}"

            if len(base_title) + badge_len > 29:
                # Use compact status badge so it never truncates mid-text
                if is_closed:
                    status_suffix = " [dim #64748b]⊘[/]"
                elif running_cnt > 0:
                    status_suffix = f" [bold #34d399]● {running_cnt}[/]"
                else:
                    status_suffix = " [dim #38bdf8]▪[/]"

            self.query_one("#session_label", Label).update(f"{base_title}{status_suffix}")
        except NoMatches:
            pass

        if self.show_global_graph:
            if session_data:
                graph_data = await self.app.power_facade.get_workspace_graph_snapshot(session_data["workspace_id"])
            else:
                graph_data = await self.app.power_facade.get_graph_snapshot(self.active_session_id)
        else:
            graph_data = await self.app.power_facade.get_graph_snapshot(self.active_session_id)

        try:
            await self.query_one("#entity_browser", EntityBrowser).refresh_entities(graph_data)
        except NoMatches:
            pass

        try:
            # Show all active jobs for this session (running, queued, or recently completed)
            session_jobs = [
                j for j in ctx.active_jobs
                if str(j.session_id) == str(self.active_session_id)
            ]
            await self.query_one("#job_queue", JobQueue).update_jobs(session_jobs)
        except NoMatches:
            pass


        palette = self.query_one("#command_palette", CommandPalette)
        palette.update_context(ctx.resolved_vars, is_registered_tool=True, cwd=ctx.cwd)
        cmd_input = self.query_one("#command_input", Input)
        if is_closed:
            cmd_input.placeholder = "[LOCKED / ARCHIVED ENGAGEMENT] Press Ctrl+R to Reopen for active scan execution"
        else:
            cmd_input.placeholder = "Enter tool command or ! <shell command>... (e.g., nmap -sV $IP)"
        try:
            scratchpad = self.query_one("#scratchpad_textarea", TextArea)
            browser = self.query_one("#entity_browser")
            if not scratchpad.has_focus and not browser.has_focus:
                cmd_input.focus()
        except NoMatches:
            cmd_input.focus()

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
            except NoMatches:
                pass

    async def on_job_queue_job_selected(self, event: JobQueue.JobSelected) -> None:
        if event.session_id != self.active_session_id:
            self.app.selected_session_id = event.session_id
            await self.on_screen_resume()
            session_data = await self.app.store.get_session(event.session_id)
            if session_data:
                self.notify(f"Switched to session: {session_data['name']}")

        # Focus tab if already open
        tabs = self.query_one("#job_tabs", TabbedContent)
        for tab_id, job_id in self.tab_to_job.items():
            if job_id == event.job_id:
                tabs.active = tab_id
                return

        # If tab was closed or not yet mounted, open it dynamically
        try:
            from rich.text import Text
            j_uuid = UUID(event.job_id)
            job = self.app.power_facade._active_jobs.get(j_uuid)
            action = self.app.power_facade.get_job_action(j_uuid)
            tool_name = (job.tool_name if job else None) or (action.tool_name if action else "job")
            is_running = job and job.status in (JobStatusEnum.RUNNING, JobStatusEnum.QUEUED)
            prefix = "◌ " if is_running else ""
            short_id = event.job_id[:4]
            is_explicit = action.is_explicit_shell if action else False
            sh_prefix = "sh › " if is_explicit else ""
            tab_title = f"{prefix}{sh_prefix}{tool_name} {short_id}"

            new_tab_id = await self.action_new_terminal_tab(title=tab_title)
            self.tab_to_job[new_tab_id] = event.job_id
            log = self.query_one(f"#log_{new_tab_id}", RichLog)

            if action:
                params = action.params or {}
                raw_flags = (params.get("raw_flags") or "").strip()
                if raw_flags.startswith(tool_name):
                    cmd_display = raw_flags
                elif raw_flags:
                    cmd_display = f"{tool_name} {raw_flags}"
                else:
                    cmd_display = tool_name
            else:
                cmd_display = tool_name

            log.write(Text.from_markup(f"\n[bold #38bdf8]❯[/] [bold #e2e8f0]{escape(cmd_display)}[/]\n"))

            buf = self.app.power_facade.get_job_buffer(j_uuid)
            if buf:
                log.write(Text.from_ansi(buf))

            if is_running:
                async def _on_chunk(chunk: str):
                    try:
                        log.write(Text.from_ansi(chunk))
                    except Exception:
                        pass
                self._active_subscriptions[j_uuid] = _on_chunk
                self.app.power_facade.subscribe_job_output(j_uuid, _on_chunk)
        except Exception:
            pass


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

        job_log = RichLog(id=f"log_{tab_id}", highlight=False, markup=True, max_lines=10000)
        tabs = self.query_one("#job_tabs", TabbedContent)
        await tabs.add_pane(TabPane(display_title, job_log, id=tab_id))
        tabs.active = tab_id
        return tab_id

    async def on_command_palette_submitted(self, event: CommandPalette.Submitted) -> None:
        self.run_worker(self._handle_submission(event))

    async def _handle_submission(self, event: CommandPalette.Submitted) -> None:
        session_data = await self.app.store.get_session(self.active_session_id)
        if session_data and session_data.get("status") == "CLOSED":
            self.notify("This session is archived (read-only). Press Ctrl+R to reopen.", severity="warning")
            return

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
            self.refresh(repaint=True, layout=True)
            return

        try:
            await self.app.power_facade.gateway.validate_action(action)
        except Exception as e:
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if not active_tab_id:
                active_tab_id = await self.action_new_terminal_tab(title=f"Error: {tool_name}")

            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            job_log.write(Text.from_markup(f"\n[bold #f85149]Validation Error:[/] [red]{escape(str(e))}[/]\n"))
            return

        is_sudo = tool_name == "sudo"
        if is_sudo and not is_builtin:
            tabs = self.query_one("#job_tabs", TabbedContent)
            active_tab_id = tabs.active
            if not active_tab_id:
                active_tab_id = await self.action_new_terminal_tab(title=f"sudo {expanded_params[0] if expanded_params else ''}")

            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            params_str = " ".join(expanded_params)
            job_log.write(Text.from_markup(f"\n[bold #38bdf8]❯[/] [bold #e2e8f0]sudo[/] [dim #8b949e]{escape(params_str)}[/]\n"))
            job_log.write(Text.from_markup("[italic #8b949e]Suspending for sudo password entry...[/]\n"))

            from cyguide.engine.executor import sanitize_subprocess_env
            clean_env = sanitize_subprocess_env(self.app.user_env)
            with self.app.suspend():
                import shlex
                import subprocess
                cmd_args = ["sudo"] + shlex.split(' '.join(expanded_params))
                subprocess.run(cmd_args, shell=False, env=clean_env)

            job_log.write(Text.from_markup("[italic #3fb950]Resumed from sudo.[/]\n"))

            await self.refresh_ui()
            return

        # BACKGROUND MODE: Tab reuse logic
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active

        title_prefix = "sh › " if action.is_explicit_shell else ""
        short_id = action.action_id.hex[:4]
        title = f"◌ {title_prefix}{tool_name} {short_id}"
        clean_title = f"{title_prefix}{tool_name} {short_id}"

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
                        tab_widget = tabs.get_tab(active_tab_id)
                        if tab_widget:
                            tab_widget.label = title
                    except Exception:
                        pass
                    break
            job_log = self.query_one(f"#log_{active_tab_id}", RichLog)
            # We explicitly do not clear the log here so that consecutive commands
            # in the same tab appear below the previous ones, mimicking a real shell.

        self.tab_to_job[active_tab_id] = str(action.action_id)
        params_str = " ".join(p for p in expanded_params if p).strip()
        cmd_display = f"{tool_name} {params_str}".strip() if params_str else tool_name
        job_log.write(Text.from_markup(f"\n[bold #38bdf8]❯[/] [bold #e2e8f0]{escape(cmd_display)}[/]\n"))

        flag_pattern = re.compile(r'(?:flag|FLAG|ctf|CTF|htb|HTB|thm|THM)\{[A-Za-z0-9_!@#$%^&*+=?.-]+\}')
        detected_flags = set()
        start_time = asyncio.get_event_loop().time()

        try:
            async def stream_output(text: str):
                job_log.write(Text.from_ansi(text))
                # CTF Flag Auto-Detection
                for match in flag_pattern.finditer(text):
                    flag_str = match.group(0)
                    if flag_str not in detected_flags:
                        detected_flags.add(flag_str)
                        job_log.write(Text.from_markup(f"\n[bold black on #eab308] 🚩 CTF FLAG DETECTED [/] [bold #facc15]{escape(flag_str)}[/]\n"))
                        self.notify(f"Captured: {flag_str}", title="🚩 Flag Detected!", severity="warning")
                await asyncio.sleep(0)

            async def stream_error(text: str):
                job_log.write(Text.from_ansi(text))
                await asyncio.sleep(0)

            async def on_complete():
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= 15.0:
                    try:
                        self.app.bell()
                    except Exception:
                        pass
                    dur_str = f"{elapsed:.1f}s"
                    asyncio.create_task(self._send_desktop_notification(
                        f"Job Finished ({dur_str})",
                        f"'{tool_name}' completed in session"
                    ))
                    self.notify(f"'{tool_name}' finished in {dur_str}", title="Long Job Complete")

                try:
                    tabs = self.query_one("#job_tabs", TabbedContent)
                    tab_w = tabs.get_tab(active_tab_id)
                    if tab_w:
                        tab_w.label = clean_title
                    for pane in tabs.query(TabPane):
                        if pane.id == active_tab_id:
                            pane.title = clean_title
                            break
                except Exception:
                    pass
                await self.refresh_ui()

            await self.app.power_facade.submit_action(
                action,
                on_output=stream_output,
                on_complete=on_complete,
                on_error_output=stream_error
            )
            await self.refresh_ui()
        except Exception as e:
            job_log.write(Text.from_markup(f"[bold #f85149]Error:[/] [red]{escape(str(e))}[/]"))
            await self.refresh_ui()

    def on_click(self, event: events.Click) -> None:
        if event.widget and event.widget.id in ("command_palette", "palette_header"):
            try:
                self.query_one("#command_input", Input).focus()
            except Exception:
                pass

    def on_blur(self) -> None:
        pass

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#power_sidebar")
        is_collapsed = not sidebar.has_class("collapsed")
        sidebar.set_class(is_collapsed, "collapsed")
        sidebar.display = not is_collapsed
        try:
            resizer = self.query_one("#sidebar_resizer")
            resizer.set_class(is_collapsed, "hidden")
            resizer.display = not is_collapsed
        except Exception:
            pass



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
            try:
                j_uuid = UUID(target_job_id)
                cb = self._active_subscriptions.pop(j_uuid, None)
                if cb and hasattr(self.app, "power_facade"):
                    self.app.power_facade.unsubscribe_job_output(j_uuid, cb)
            except Exception:
                pass
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
                job_log.write(Text.from_markup("\n[bold #f85149]SIGTERM: Job terminated by operator.[/]\n"))

                # Refresh to update status icon in sidebar
                await self.refresh_ui()
            except Exception as e:
                # Silently fail if log isn't found or other UI issues
                pass

    def action_show_shortcuts(self) -> None:
        """Open the keyboard shortcuts help dialog."""
        self.app.push_screen(ShortcutsDialog())

    async def on_command_palette_show_shortcuts_request(self, event: CommandPalette.ShowShortcutsRequest) -> None:
        """Handle Show Shortcuts request from the command palette (bypassing Input widget)."""
        self.action_show_shortcuts()

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

    async def on_command_palette_copy_tab_request(self, event: CommandPalette.CopyTabRequest) -> None:
        """Handle Copy Tab request from the command palette."""
        self.action_copy_active_tab()

    def action_copy_active_tab(self) -> None:
        """Copy the active terminal tab's log output to the system clipboard."""
        tabs = self.query_one("#job_tabs", TabbedContent)
        active_tab_id = tabs.active
        if not active_tab_id:
            self.notify("No active terminal tab to copy.", severity="warning")
            return

        try:
            log = self.query_one(f"#log_{active_tab_id}", RichLog)
            lines = [line.text if hasattr(line, "text") else str(line) for line in log.lines]
            full_text = "\n".join(lines).strip()
            if not full_text:
                self.notify("Active tab is empty.", severity="information")
                return

            self.app.copy_to_clipboard(full_text)
            self.notify("Active tab log copied to clipboard! (Ctrl+Y)", title="Clipboard")
        except Exception as e:
            self.notify(f"Failed to copy log: {e}", severity="error")

    async def _send_desktop_notification(self, title: str, message: str) -> None:
        """Send a desktop notification using notify-send if available."""
        try:
            import shutil
            if shutil.which("notify-send"):
                proc = await asyncio.create_subprocess_exec(
                    "notify-send", "-a", "CyGuide", title, message,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
        except Exception:
            pass

    def _load_scratchpad(self) -> None:
        try:
            if self.scratchpad_file == ":memory:":
                return
            if os.path.exists(self.scratchpad_file):
                with open(self.scratchpad_file, "r") as f:
                    content = f.read()
                self.query_one("#scratchpad_textarea", TextArea).load_text(content)
        except Exception:
            pass

    def _save_scratchpad(self) -> None:
        try:
            if self.scratchpad_file == ":memory:":
                return
            content = self.query_one("#scratchpad_textarea", TextArea).text
            scratch_dir = os.path.dirname(os.path.abspath(self.scratchpad_file))
            if scratch_dir:
                os.makedirs(scratch_dir, exist_ok=True)
            fd = os.open(self.scratchpad_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "w", encoding="utf-8", closefd=False) as f:
                    f.write(content)
            finally:
                os.close(fd)
            try:
                os.chmod(self.scratchpad_file, 0o600)
            except OSError:
                pass
        except Exception:
            pass

    async def action_toggle_global_graph(self) -> None:
        self.show_global_graph = not self.show_global_graph
        status = "Global (Workspace)" if self.show_global_graph else "Local (Session)"
        self.notify(f"Entity Graph scoped to: {status}")
        await self.refresh_ui()

    def action_toggle_scratchpad(self) -> None:
        pane = self.query_one("#scratchpad_pane")
        try:
            resizer = self.query_one("#scratchpad_resizer")
        except Exception:
            resizer = None

        if pane.has_class("hidden") or not pane.display:
            self._load_scratchpad()
            pane.remove_class("hidden")
            pane.display = True
            if resizer:
                resizer.remove_class("hidden")
                resizer.display = True
            self.query_one("#scratchpad_textarea", TextArea).focus()
        else:
            self._save_scratchpad()
            pane.add_class("hidden")
            pane.display = False
            if resizer:
                resizer.add_class("hidden")
                resizer.display = False
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
            exports_dir = self.app.get_exports_dir() if hasattr(self.app, "get_exports_dir") else get_default_exports_dir()
            reports_dir = self.app.get_reports_dir() if hasattr(self.app, "get_reports_dir") else get_default_reports_dir()
            os.makedirs(reports_dir, exist_ok=True)
            os.makedirs(exports_dir, exist_ok=True)

            session = await self.app.store.get_session(self.active_session_id)
            if not session:
                self.notify("Session not found.", severity="error")
                return

            session_name = session["name"]
            import re
            slug = re.sub(r'[^a-zA-Z0-9_-]', '_', session_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            report_path = os.path.join(reports_dir, f"report_{slug}_{timestamp}.md")
            db_path = os.path.join(exports_dir, f"archive_{slug}_{timestamp}.db")

            # Generate Report
            from cyguide.engine.reporter import generate_markdown_report
            report_content = await generate_markdown_report(self.app.store, self.active_session_id)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            # Export DB
            await self.app.power_facade.export_session(self.active_session_id, db_path)

            self.notify(f"Report: {report_path}")
            self.notify(f"Database: {db_path}")
        except Exception as e:
            self.notify(f"Export failed: {str(e)}", severity="error")

    async def action_reopen_session(self) -> None:
        """Reopen an archived session back to ACTIVE status."""
        if not self.active_session_id:
            return
        session = await self.app.store.get_session(self.active_session_id)
        if not session:
            return
        if session.get("status") == "CLOSED":
            await self.app.power_facade.reopen_session(self.active_session_id)
            self.notify(f"Reopened session '{session.get('name')}' to ACTIVE.")
            await self.refresh_ui()
        else:
            self.notify("Session is already active.")
