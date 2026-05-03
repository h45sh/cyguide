"""Workspace and Session Management Dashboard with refined Delete/Organize flows."""

import logging
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Static, Button, ListItem, ListView, Label
from textual.containers import Vertical, Horizontal, Grid
from textual.app import ComposeResult
from textual.binding import Binding
from datetime import datetime
from typing import Set, Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class ConfirmationDialog(ModalScreen[bool]):
    """A generic centered confirmation dialog."""
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Grid(id="dialog_grid"):
            yield Label(self.message, id="dialog_message")
            yield Button("Confirm", variant="error", id="confirm")
            yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

class DashboardScreen(Screen):
    """The central hub for managing engagements and investigations."""
    
    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+n", "new_workspace", "New Workspace"),
        Binding("ctrl+s", "new_session", "New Session"),
        Binding("ctrl+l", "nav_learning", "Learning Mode"),
        Binding("ctrl+d", "toggle_delete_mode", "Delete Mode"),
        Binding("ctrl+m", "toggle_organize_mode", "Organize Mode"),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("escape", "cancel_mode", "Cancel", show=False),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.mode = "NORMAL"
        self.selected_workspaces: Set[str] = set()
        self.selected_sessions: Set[str] = set()
        self.organize_step = 1 
        self.selected_ws_id: Optional[str] = None
        self.selected_session_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace_manager"):
            with Vertical(id="workspace_sidebar"):
                yield Label("WORKSPACES", classes="section_header")
                yield ListView(id="workspace_list")
            
            with Vertical(id="workspace_details"):
                with Horizontal(id="ws_header"):
                    with Vertical():
                        yield Label("Select a workspace", id="ws_title")
                        with Horizontal(id="ws_metrics_inline"):
                            yield Static("Sessions: 0", id="metric_sessions")
                            yield Static(" | ", id="metric_sep")
                            yield Static("Hosts: 0", id="metric_hosts")
                            yield Static(" | ", id="metric_sep_2")
                            yield Static("Services: 0", id="metric_services")
                            yield Static(" | ", id="metric_sep_3")
                            yield Static("Active: 0", id="metric_active")
                    yield Label("", id="ws_status_badge")
                
                with Horizontal(id="session_container"):
                    with Vertical(id="session_sidebar"):
                        yield Label("SESSIONS", classes="section_header")
                        yield ListView(id="session_list")
                        
                        yield Label("RECENT ACTIVITY", classes="section_header")
                        yield ListView(id="activity_list")

                        yield Label("TOOL HEALTH", classes="section_header")
                        yield ListView(id="diagnostics_list")
                    
                    with Vertical(id="session_details_area"):
                        yield Label("SESSION DETAILS", classes="section_header")
                        with Vertical(id="session_details_content"):
                            yield Label("Select a session to view details", id="session_placeholder")
        
        yield Label("", id="mode_status_label")
        yield Footer()

    async def on_mount(self) -> None:
        self.app.store.on_upsert(self.handle_new_finding)
        await self.refresh_workspaces()
        await self.refresh_diagnostics()

    async def refresh_diagnostics(self) -> None:
        """Populate the TOOL HEALTH list with errors from the registry."""
        diag_list = self.query_one("#diagnostics_list", ListView)
        await diag_list.clear()
        
        errors = self.app.registry.load_errors
        if not errors:
            diag_list.append(ListItem(Static("● All systems green", classes="diagnostics_green")))
        else:
            for tool, error in errors.items():
                diag_list.append(ListItem(Static(f"○ {tool}: {error}", classes="diagnostics_error")))

    async def handle_new_finding(self, session_id: str, finding: Any) -> None:
        """Reactive callback triggered by the GraphStore on every finding."""
        if not self.selected_ws_id:
            return
            
        # 1. Verify finding belongs to active workspace
        session = await self.app.store.get_session(session_id)
        if not session or session["workspace_id"] != self.selected_ws_id:
            return

        # 2. Surgical Metrics Update
        ws_stats = await self.app.store.get_stats()
        self.query_one("#metric_hosts", Static).update(f"Hosts: {ws_stats.get('network.host', 0)}")
        self.query_one("#metric_services", Static).update(f"Services: {ws_stats.get('network.service', 0)}")

        # 3. Surgical Activity Prepend
        act_list = self.query_one("#activity_list", ListView)
        ts = datetime.utcnow().strftime("%H:%M")
        new_item = ListItem(Static(f"{ts} [{session['name']}] {finding.schema_type} discovered"))
        act_list.insert(0, new_item)
        if len(act_list.children) > 15:
            await act_list.children[-1].remove()

        # 4. If current session is selected, refresh its details (stats)
        if self.selected_session_id == session_id:
            await self.show_session_details(session_id, force=True)

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#workspace_sidebar")
        sidebar.toggle_class("collapsed")

    def update_mode_ui(self):
        sidebar = self.query_one("#workspace_sidebar")
        status_label = self.query_one("#mode_status_label", Label)
        
        sidebar.remove_class("delete-mode-border")
        status_label.remove_class("delete-status")
        status_label.remove_class("organize-status")
        status_label.update("")

        if self.mode == "DELETE":
            sidebar.add_class("delete-mode-border")
            status_label.add_class("delete-status")
            status_label.update("DELETE MODE: [Space] Toggle | [Ctrl+D] Confirm | [Esc] Cancel")
        elif self.mode == "ORGANIZE":
            status_label.add_class("organize-status")
            status_label.update(f"ORGANIZE MODE: Step {self.organize_step}")

    async def action_toggle_delete_mode(self) -> None:
        if self.mode == "DELETE":
            # If already in DELETE mode, Ctrl+D triggers the confirmation
            await self.action_confirm_action()
        else:
            self.mode = "DELETE"
            self.selected_workspaces.clear()
            self.selected_sessions.clear()
            self.update_mode_ui()
            await self.refresh_all()

    async def action_toggle_organize_mode(self) -> None:
        if self.mode == "ORGANIZE":
            await self.action_confirm_action()
        else:
            self.mode = "ORGANIZE"
            self.organize_step = 1
            self.selected_sessions.clear()
            self.update_mode_ui()
            await self.refresh_all()

    async def action_cancel_mode(self) -> None:
        if self.mode == "NORMAL":
            return
        self.mode = "NORMAL"
        self.selected_workspaces.clear()
        self.selected_sessions.clear()
        self.update_mode_ui()
        await self.refresh_all()

    async def action_toggle_selection(self) -> None:
        ws_list = self.query_one("#workspace_list", ListView)
        sess_list = self.query_one("#session_list", ListView)

        if self.mode == "DELETE":
            if ws_list.has_focus and ws_list.index is not None:
                item_id = ws_list.children[ws_list.index].id
                if item_id and item_id.startswith("ws_"):
                    ws_id = item_id[3:] # Remove prefix
                    if ws_id in self.selected_workspaces:
                        self.selected_workspaces.remove(ws_id)
                    else:
                        self.selected_workspaces.add(ws_id)
                    await self.refresh_workspaces()
            elif sess_list.has_focus and sess_list.index is not None:
                item_id = sess_list.children[sess_list.index].id
                if item_id and item_id.startswith("sess_"):
                    sess_id = item_id[5:] # Remove prefix
                    if sess_id in self.selected_sessions:
                        self.selected_sessions.remove(sess_id)
                    else:
                        self.selected_sessions.add(sess_id)
                    await self.refresh_session_list()
        
        elif self.mode == "ORGANIZE" and self.organize_step == 1:
            if sess_list.has_focus and sess_list.index is not None:
                item_id = sess_list.children[sess_list.index].id
                if item_id and item_id.startswith("sess_"):
                    sess_id = item_id[5:]
                    if sess_id in self.selected_sessions:
                        self.selected_sessions.remove(sess_id)
                    else:
                        self.selected_sessions.add(sess_id)
                    await self.refresh_session_list()

    async def action_confirm_action(self) -> None:
        if self.mode == "DELETE":
            if not self.selected_workspaces and not self.selected_sessions:
                self.notify("No items selected for deletion.")
                return
            
            msg = f"Delete {len(self.selected_workspaces)} workspace(s) and {len(self.selected_sessions)} session(s)?"
            
            async def check_confirm(confirmed: bool) -> None:
                if confirmed:
                    for wid in list(self.selected_workspaces):
                        ws = await self.app.store.get_workspace(wid)
                        if ws and ws.get("status") == "SYSTEM":
                            self.notify(f"Cannot delete system workspace: {ws['name']}", severity="error")
                            continue
                        await self.app.store.delete_workspace(wid)
                    for sid in self.selected_sessions:
                        await self.app.store.delete_session(sid)
                    self.notify("Deletion complete.")
                    self.mode = "NORMAL"
                    self.selected_workspaces.clear()
                    self.selected_sessions.clear()
                    self.update_mode_ui()
                    await self.refresh_all()
            
            self.app.push_screen(ConfirmationDialog(msg), check_confirm)

        elif self.mode == "ORGANIZE":
            if self.organize_step == 1:
                if not self.selected_sessions:
                    self.notify("Select sessions first.")
                    return
                self.organize_step = 2
                self.update_mode_ui()
                self.query_one("#workspace_list").focus()
            else:
                ws_list = self.query_one("#workspace_list", ListView)
                if ws_list.index is None: return
                dest_id = ws_list.children[ws_list.index].id[3:]
                
                async def check_move(confirmed: bool) -> None:
                    if confirmed:
                        for sid in self.selected_sessions:
                            await self.app.store.move_session(sid, dest_id)
                        self.mode = "NORMAL"
                        self.update_mode_ui()
                        await self.refresh_all()
                
                self.app.push_screen(ConfirmationDialog(f"Move sessions to workspace?"), check_move)

    async def refresh_all(self):
        # Reset selected_ws_id to force a full re-load of details for the currently selected index
        self.selected_ws_id = None
        await self.refresh_workspaces()
        await self.refresh_session_list()

    async def refresh_workspaces(self) -> None:
        store = self.app.store
        all_workspaces = await store.list_workspaces()
        
        # Filter out the SYSTEM Learning Sandbox from the sidebar list
        workspaces = [ws for ws in all_workspaces if ws.get("status") != "SYSTEM"]
        
        ws_list = self.query_one("#workspace_list", ListView)
        
        old_index = ws_list.index
        was_focused = ws_list.has_focus

        if not workspaces:
            await store.create_workspace("Default Project")
            all_workspaces = await store.list_workspaces()
            workspaces = [ws for ws in all_workspaces if ws.get("status") != "SYSTEM"]

        # Surgical update: if count matches, just update labels
        if len(ws_list.children) == len(workspaces):
            for i, ws in enumerate(workspaces):
                prefix = ""
                if self.mode == "DELETE":
                    prefix = "[X] " if ws["id"] in self.selected_workspaces else "[ ] "
                elif self.mode == "ORGANIZE" and self.organize_step == 2:
                    prefix = "-> " if i == old_index else "   "
                
                try:
                    label = ws_list.children[i].query_one(Static)
                    label.update(f"{prefix}{ws['name']}")
                except:
                    pass
        else:
            await ws_list.clear()
            for ws in workspaces:
                prefix = ""
                if self.mode == "DELETE":
                    prefix = "[X] " if ws["id"] in self.selected_workspaces else "[ ] "
                ws_list.append(ListItem(Static(f"{prefix}{ws['name']}"), id=f"ws_{ws['id']}"))
        
        if old_index is not None:
            ws_list.index = old_index if old_index < len(workspaces) else 0
        if was_focused: ws_list.focus()
            
        if workspaces and ws_list.index is not None:
            try:
                target_id = workspaces[ws_list.index]["id"]
                if not self.selected_ws_id:
                    await self.show_workspace_details(target_id)
            except (IndexError, KeyError):
                pass

    async def refresh_session_list(self) -> None:
        if not self.selected_ws_id: return
        await self.show_workspace_details(self.selected_ws_id)

    async def show_workspace_details(self, ws_id: str) -> None:
        # If workspace changed, clear session details
        if self.selected_ws_id != ws_id:
            self.selected_session_id = None
            details_area = self.query_one("#session_details_content", Vertical)
            await details_area.query("*").remove()
            await details_area.mount(Label("Select a session to view details", id="session_placeholder"))

        self.selected_ws_id = ws_id
        store = self.app.store
        ws = await store.get_workspace(ws_id)
        if not ws: return

        self.query_one("#ws_title", Label).update(ws["name"].upper())
        self.query_one("#ws_status_badge", Label).update(ws["status"])

        sessions = await store.list_sessions(ws_id)
        sess_list = self.query_one("#session_list", ListView)
        
        old_index = sess_list.index
        was_focused = sess_list.has_focus

        active_count = 0
        if len(sess_list.children) == len(sessions):
            for i, s in enumerate(sessions):
                status_icon = "●" if s["status"] == "ACTIVE" else "○"
                if s["status"] == "ACTIVE": active_count += 1
                prefix = ""
                if self.mode in ("DELETE", "ORGANIZE"):
                    prefix = "[X] " if s["id"] in self.selected_sessions else "[ ] "
                
                try:
                    label = sess_list.children[i].query_one(Static)
                    label.update(f"{prefix}{s['name']} {status_icon}")
                except:
                    pass
        else:
            await sess_list.clear()
            for s in sessions:
                status_icon = "●" if s["status"] == "ACTIVE" else "○"
                if s["status"] == "ACTIVE": active_count += 1
                prefix = ""
                if self.mode in ("DELETE", "ORGANIZE"):
                    prefix = "[X] " if s["id"] in self.selected_sessions else "[ ] "
                sess_list.append(ListItem(Static(f"{prefix}{s['name']} {status_icon}"), id=f"sess_{s['id']}"))

        # If we have sessions but none selected, highlight first and show details
        if sessions and old_index is None:
             sess_list.index = 0
             await self.show_session_details(sessions[0]["id"], force=True)
        elif old_index is not None:
            sess_list.index = old_index if old_index < len(sessions) else 0
            # If valid, refresh details for the currently highlighted one too
            if sess_list.index is not None and sess_list.index < len(sessions):
                await self.show_session_details(sessions[sess_list.index]["id"], force=True)

        if was_focused: sess_list.focus()

        self.query_one("#metric_sessions", Static).update(f"Sessions: {len(sessions)}")
        self.query_one("#metric_active", Static).update(f"Active: {active_count}")

        # Update Host/Service counts for the workspace
        # Note: In a large DB, we'd optimize this, but for Phase 3, get_stats is fine.
        ws_stats = await store.get_stats() # Get global stats, or we could filter by WS
        self.query_one("#metric_hosts", Static).update(f"Hosts: {ws_stats.get('network.host', 0)}")
        self.query_one("#metric_services", Static).update(f"Services: {ws_stats.get('network.service', 0)}")

        # Activity list: Prepend new findings to show latest at top without full clear if possible
        activity = await store.get_recent_activity(ws_id, limit=10)
        act_list = self.query_one("#activity_list", ListView)
        
        # Simple length check for activity - usually small enough to clear
        # but prepend is better for live feel
        await act_list.clear()
        for a in activity:
            ts = a["timestamp"][11:16] if a["timestamp"] else "--:--"
            act_list.append(ListItem(Static(f"{ts} [{a['session_name']}] {a['schema_type']} discovered")))

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.mode in ("NORMAL", "DELETE") or (self.mode == "ORGANIZE" and self.organize_step == 2):
            if event.list_view.id == "workspace_list":
                if event.item and event.item.id:
                    ws_id = event.item.id[3:]
                    await self.show_workspace_details(ws_id)
            elif event.list_view.id == "session_list":
                if event.item and event.item.id:
                    sess_id = event.item.id[5:]
                    await self.show_session_details(sess_id)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.mode == "NORMAL":
            if event.list_view.id == "workspace_list":
                ws_id = event.item.id[3:]
                await self.show_workspace_details(ws_id)
            elif event.list_view.id == "session_list":
                self.app.switch_screen("power_mode")
        elif self.mode == "DELETE":
            await self.action_toggle_selection()
        elif self.mode == "ORGANIZE":
            if self.organize_step == 1 and event.list_view.id == "session_list":
                 await self.action_toggle_selection()
            elif self.organize_step == 2 and event.list_view.id == "workspace_list":
                await self.action_confirm_action()

    async def show_session_details(self, sess_id: str, force: bool = False) -> None:
        """Display metadata and stats for a selected session."""
        if self.selected_session_id == sess_id and not force:
            return
            
        self.selected_session_id = sess_id
        store = self.app.store
        session = await store.get_session(sess_id)
        if not session: return

        stats = await store.get_stats(sess_id)
        
        container = self.query_one("#session_details_content", Vertical)
        await container.query("*").remove()
        
        # Mount new content
        await container.mount(Horizontal(Label("Name:", classes="detail_label"), Label(session["name"], classes="detail_value"), classes="detail_row"))
        await container.mount(Horizontal(Label("Status:", classes="detail_label"), Label(session["status"], classes="detail_value"), classes="detail_row"))
        await container.mount(Horizontal(Label("Created:", classes="detail_label"), Label(session["created_at"][:16], classes="detail_value"), classes="detail_row"))
        
        await container.mount(Label("\nGRAPH STATISTICS", classes="section_header"))
        
        for schema, count in stats.items():
            if schema == "total": continue
            await container.mount(Horizontal(Label(f"{schema}:", classes="detail_label"), Label(str(count), classes="detail_value"), classes="detail_row"))
        
        await container.mount(Horizontal(Label("Total Entities:", classes="detail_label"), Label(str(stats.get("total", 0)), classes="detail_value"), classes="detail_row"))
        
        await container.mount(Button("ENTER POWER MODE", classes="enter_session_btn", variant="primary"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.has_class("enter_session_btn"):
            self.app.switch_screen("power_mode")

    def action_nav_learning(self) -> None:
        self.app.switch_screen("tool_browser")

    async def action_new_workspace(self) -> None:
        name = f"Project {datetime.now().strftime('%H:%M:%S')}"
        await self.app.store.create_workspace(name)
        await self.refresh_workspaces()

    async def action_new_session(self) -> None:
        if not self.selected_ws_id:
            self.notify("Select a workspace first.", severity="error")
            return
        name = f"Session {datetime.now().strftime('%H:%M:%S')}"
        await self.app.store.create_session(self.selected_ws_id, name)
        await self.refresh_session_list()
