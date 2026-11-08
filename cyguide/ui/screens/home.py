"""Workspace and Session Management Dashboard with refined Delete/Organize flows."""

from textual import events
from textual.screen import Screen, ModalScreen
from textual.widgets import Footer, Static, Button, ListItem, ListView, Label, Input
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from textual.binding import Binding
from datetime import datetime
from typing import Set, Optional, Dict, Any

def format_activity(session_name: str, schema_type: str, human_readable: str, finding_json: Optional[str] = None, finding_obj: Optional[Any] = None) -> str:
    # 1. Shorten session name
    s_name = session_name
    if s_name.startswith("Session "):
        s_name = s_name[8:]
    if len(s_name) > 10:
        s_name = s_name[:8] + ".."

    message = human_readable
    # 2. Extract description for findings
    if schema_type != "system.event":
        try:
            import json
            if finding_obj:
                pik = finding_obj.pik
                data = finding_obj.data
            else:
                finding_data = json.loads(finding_json) if finding_json else {}
                pik = finding_data.get("pik", {})
                data = finding_data.get("data", {})

            if schema_type == "network.host" and "ip" in pik:
                message = f"Host: {pik['ip']}"
            elif schema_type == "network.service" and "port" in pik:
                service_name = data.get("service_name") or pik.get("service") or "unknown"
                message = f"Port: {pik['port']} ({service_name})"
            elif "cidr" in pik:
                message = f"Netblock: {pik['cidr']}"
            elif "vuln_type" in pik:
                message = f"Vuln: {pik['vuln_type']}"
            elif "vuln_id" in pik:
                message = f"Vuln: {pik['vuln_id']}"
            elif "url" in pik:
                url = pik["url"]
                if url.startswith("http://"):
                    url = url[7:]
                elif url.startswith("https://"):
                    url = url[8:]
                message = f"URL: {url}"
            elif "domain" in pik:
                message = f"Domain: {pik['domain']}"
            elif "endpoint" in pik:
                message = f"Endpoint: {pik['endpoint']}"
            else:
                short_type = schema_type.split(".")[-1] if "." in schema_type else schema_type
                message = f"New {short_type}"
        except Exception:
            pass

    # 3. Shorten system event labels
    if message.startswith("Ran "):
        message = f"Run: {message[4:]}"

    return f"[{s_name}] {message}"


SCHEMA_DISPLAY_MAP: Dict[str, tuple[str, str, str]] = {
    # schema_type: (bullet_symbol, color_hex, display_name)
    "network.host": ("●", "#38bdf8", "Hosts"),
    "network.service": ("●", "#34d399", "Services"),
    "network.netblock": ("●", "#a78bfa", "Netblocks"),
    "web.endpoint": ("●", "#f59e0b", "Web Endpoints"),
    "web.resource": ("●", "#fbbf24", "Web Resources"),
    "web.vulnerability": ("▲", "#f87171", "Web Vulnerabilities"),
    "vulnerability.found": ("▲", "#f87171", "Vulnerabilities"),
    "domain.info": ("●", "#ec4899", "Domains"),
    "dns.record": ("●", "#60a5fa", "DNS Records"),
    "tls.certificate": ("●", "#2dd4bf", "TLS Certificates"),
    "credential.found": ("◆", "#fbbf24", "Credentials"),
    "process.running": ("●", "#4ade80", "Processes"),
    "file.system_object": ("●", "#94a3b8", "Files"),
    "software.package": ("●", "#818cf8", "Packages"),
    "entity.alias": ("●", "#c084fc", "Aliases"),
}


SCHEMA_CANONICAL_ORDER: list[str] = [
    # Infrastructure: Device -> Netblock -> Services
    "network.host",          # Hosts / Devices / IPs
    "network.netblock",      # Netblocks / CIDRs
    "network.service",       # Services / Ports
    # Web & Application Layer
    "web.endpoint",          # Web Endpoints
    "web.resource",          # Web Resources
    # Domains & DNS Layer
    "domain.info",           # Domains
    "dns.record",            # DNS Records
    "tls.certificate",       # TLS Certificates
    # Security Findings & Credentials
    "vulnerability.found",   # Vulnerabilities
    "web.vulnerability",     # Web Vulnerabilities
    "credential.found",      # Credentials
    # Internal Host & Processes
    "process.running",       # Processes
    "software.package",      # Packages
    "file.system_object",    # Files
    "entity.alias",          # Aliases
]


def format_schema_label(schema_type: str) -> tuple[str, str, str]:
    """Return a bullet symbol, color, and human-friendly name for a schema type."""
    if schema_type in SCHEMA_DISPLAY_MAP:
        return SCHEMA_DISPLAY_MAP[schema_type]
    clean_name = schema_type.split(".")[-1].replace("_", " ").title() if "." in schema_type else schema_type.replace("_", " ").title()
    return ("◆", "#94a3b8", clean_name)


def get_schema_sort_key(schema_type: str) -> tuple[int, str]:
    """Sort key for canonical entity ordering across sessions (device -> netblock -> service -> etc.)."""
    try:
        return (SCHEMA_CANONICAL_ORDER.index(schema_type), schema_type)
    except ValueError:
        return (len(SCHEMA_CANONICAL_ORDER), schema_type)


class ConfirmationDialog(ModalScreen[bool]):
    """A generic centered confirmation dialog."""
    def __init__(self, message: str, confirm_label: str = "Confirm", cancel_label: str = "Cancel", is_destructive: bool = True):
        super().__init__()
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.is_destructive = is_destructive

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_dialog_card"):
            yield Label(self.message, id="dialog_message")
            with Horizontal(classes="dialog_buttons"):
                variant = "error" if self.is_destructive else "primary"
                yield Button(self.confirm_label, variant=variant, id="confirm")
                yield Button(self.cancel_label, variant="default", id="cancel")

    def on_mount(self) -> None:
        def focus_default():
            try:
                # Default focus to cancel for safety on destructive dialogs, else confirm
                target_id = "#cancel" if self.is_destructive else "#confirm"
                self.query_one(target_id, Button).focus()
            except Exception:
                pass
        self.call_after_refresh(focus_default)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("left", "right", "up", "down"):
            event.stop()
            if self.query_one("#confirm", Button).has_focus:
                self.query_one("#cancel", Button).focus()
            else:
                self.query_one("#confirm", Button).focus()
        elif event.key == "escape":
            event.stop()
            self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

class RenameDialog(ModalScreen[str]):
    """A modal dialog to rename a workspace or session."""
    def __init__(self, prompt: str, initial_value: str):
        super().__init__()
        self.prompt = prompt
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Vertical(id="rename_dialog"):
            yield Label(self.prompt, id="rename_prompt")
            yield Input(value=self.initial_value, id="rename_input")
            with Horizontal(classes="dialog_buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        def focus_input():
            try:
                inp = self.query_one("#rename_input", Input)
                inp.focus()
                inp.action_select_all()
            except Exception:
                pass
        self.call_after_refresh(focus_input)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
            return

        try:
            inp = self.query_one("#rename_input", Input)
            btn_save = self.query_one("#save", Button)
            btn_cancel = self.query_one("#cancel", Button)
        except Exception:
            return

        if inp.has_focus:
            if event.key == "down":
                event.stop()
                btn_save.focus()
        else:
            if event.key == "up":
                event.stop()
                inp.focus()
            elif event.key in ("left", "right"):
                event.stop()
                if btn_save.has_focus:
                    btn_cancel.focus()
                else:
                    btn_save.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.dismiss(self.query_one("#rename_input").value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

class DashboardScreen(Screen):
    """The central hub for managing engagements and investigations."""

    BINDINGS = [
        Binding("f1", "show_shortcuts", "Help"),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False),
        Binding("ctrl+n", "new_workspace", "New WS"),
        Binding("ctrl+s", "new_session", "New Session"),
        Binding("ctrl+h", "toggle_history_mode", "History", show=False),
        Binding("h", "toggle_history_mode", "History", show=False),
        Binding("ctrl+a", "toggle_archive_session", "Archive", show=False),
        Binding("c", "toggle_archive_session", "Archive", show=False),
        Binding("ctrl+l", "nav_learning", "Learning"),
        Binding("ctrl+d", "toggle_delete_mode", "Delete", show=False),
        Binding("ctrl+m", "toggle_organize_mode", "Organize", show=False),
        Binding("f2", "rename_item", "Rename", show=False),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("escape", "cancel_mode", "Cancel", show=False),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.mode = "NORMAL"
        self.session_filter = "ACTIVE"
        self.selected_workspaces: Set[str] = set()
        self.selected_sessions: Set[str] = set()
        self.organize_step = 1
        self.selected_ws_id: Optional[str] = None
        self.selected_session_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="workspace_manager"):
            with Vertical(id="workspace_sidebar"):
                with Horizontal(classes="pane_header"):
                    yield Label("◆ WORKSPACES", classes="pane_title")
                yield ListView(id="workspace_list")

            with Vertical(id="workspace_details"):
                with Horizontal(id="ws_header"):
                    with Horizontal(id="ws_title_group"):
                        yield Label("◆", id="ws_brand_icon")
                        yield Label("Select a workspace", id="ws_title")
                    with Horizontal(id="ws_metrics_inline"):
                        yield Static("Sessions: 0", id="metric_sessions", classes="metric_badge")
                        yield Static("·", id="metric_sep")
                        yield Static("Hosts: 0", id="metric_hosts", classes="metric_badge")
                        yield Static("·", id="metric_sep_2")
                        yield Static("Services: 0", id="metric_services", classes="metric_badge")
                        yield Static("·", id="metric_sep_3")
                        yield Static("Running: 0", id="metric_active", classes="metric_badge")
                    yield Label("", id="ws_status_badge")

                with Horizontal(id="session_container"):
                    with Vertical(id="session_sidebar"):
                        with Horizontal(classes="pane_header"):
                            yield Label("◆ SESSIONS", classes="pane_title", id="sessions_pane_title")
                            yield Label("[Active]", id="session_filter_badge", classes="pane_filter_badge")
                        yield ListView(id="session_list")

                        with Vertical(id="tool_health_container", classes="hidden"):
                            with Horizontal(classes="pane_header"):
                                yield Label("◆ TOOL ALERTS", classes="pane_title")
                            yield ListView(id="diagnostics_list")

                    with Vertical(id="session_details_area"):
                        with Horizontal(classes="pane_header"):
                            yield Label("◆ SESSION OVERVIEW", classes="pane_title")
                        with Vertical(id="session_details_content"):
                            yield Label("Select a session to view details", classes="placeholder_text")

                with Vertical(id="activity_container"):
                    with Horizontal(classes="pane_header"):
                        yield Label("◆ LIVE TELEMETRY & ACTIVITY", classes="pane_title")
                    yield ListView(id="activity_list")

        yield Label("", id="mode_status_label", classes="hidden")
        yield Footer()

    async def on_mount(self) -> None:
        self.app.store.on_upsert(self.handle_new_finding)
        self.app.power_facade.on_job_status_change(self._handle_job_status_change)
        self.set_interval(5.0, self._poll_live_status)
        await self.refresh_workspaces()
        await self.refresh_diagnostics()

    def on_unmount(self) -> None:
        self.app.power_facade.remove_job_status_change(self._handle_job_status_change)

    def _handle_job_status_change(self, job: Any) -> None:
        self.run_worker(self._refresh_live_status())

    async def _poll_live_status(self) -> None:
        await self._refresh_live_status()

    async def _refresh_live_status(self) -> None:
        try:
            await self.refresh_workspaces()
            if self.selected_ws_id:
                if self.selected_session_id:
                    await self.show_session_details(self.selected_session_id, force=True)
                await self.refresh_session_list()
        except Exception:
            pass

    async def on_screen_resume(self) -> None:
        """Refresh diagnostics and live status when dashboard is resumed (e.g. closing modals or returning from Power mode)."""
        health = self.app.check_and_update_tool_health()
        self.run_worker(self.apply_tool_health(health))
        await self.refresh_workspaces()
        if self.selected_ws_id:
            await self.refresh_session_list()

    async def on_tool_health_changed(self, event: Any) -> None:
        """Handle real-time tool health updates broadcast from the app."""
        await self.apply_tool_health(event.health)

    async def on_cy_guide_app_tool_health_changed(self, event: Any) -> None:
        """Fallback handler for nested event class names."""
        await self.apply_tool_health(event.health)

    async def refresh_diagnostics(self) -> None:
        """Check tool health and update dashboard alert panel."""
        health = self.app.check_and_update_tool_health()
        await self.apply_tool_health(health)

    async def apply_tool_health(self, health: Dict[str, Dict[str, Any]]) -> None:
        """Show tool health on dashboard ONLY if any tool is missing or has a negative status."""
        try:
            container = self.query_one("#tool_health_container", Vertical)
            diag_list = self.query_one("#diagnostics_list", ListView)
        except Exception:
            return

        issues = {name: info for name, info in health.items() if not info.get("healthy", False)}
        await diag_list.clear()

        if not issues:
            # When all tools are present and healthy, tool health is kept off the dashboard
            container.add_class("hidden")
        else:
            # In case the tool is not there, or any other negative status, show on dashboard
            container.remove_class("hidden")
            for tool, info in sorted(issues.items()):
                if info.get("status") == "missing":
                    diag_list.append(ListItem(Static(f"×  {tool}: Not installed", classes="diagnostics_error")))
                else:
                    diag_list.append(ListItem(Static(f"▲  {tool}: {info.get('message', 'Issue detected')}", classes="diagnostics_error")))

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

        msg = format_activity(session["name"], finding.schema_type, f"Discovered {finding.schema_type}", finding_obj=finding)
        new_item = ListItem(Static(f"{ts} {msg}"))
        await act_list.insert(0, [new_item])
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
        status_label.add_class("hidden")
        status_label.update("")

        if self.mode == "DELETE":
            sidebar.add_class("delete-mode-border")
            status_label.remove_class("hidden")
            status_label.add_class("delete-status")
            status_label.update(r"[bold #f85149]DELETE MODE:[/] \[Space] Toggle | \[Ctrl+D] Confirm | \[Esc] Cancel")
        elif self.mode == "ORGANIZE":
            status_label.remove_class("hidden")
            status_label.add_class("organize-status")
            if self.organize_step == 1:
                status_label.update(r"[bold #eab308]ORGANIZE MODE:[/] Step 1: Select sessions | \[Space] Toggle | \[Ctrl+M] Next | \[Esc] Cancel")
            else:
                status_label.update(r"[bold #eab308]ORGANIZE MODE:[/] Step 2: Choose destination | \[Enter] Move | \[Esc] Cancel")

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
            if self.organize_step == 1:
                if not self.selected_sessions:
                    self.notify("Select at least one session to move.", severity="warning")
                    return
                self.organize_step = 2
                self.update_mode_ui()
                self.query_one("#workspace_list").focus()
                await self.refresh_workspaces()
            else:
                await self.action_confirm_action()
        else:
            self.mode = "ORGANIZE"
            self.organize_step = 1
            self.selected_sessions.clear()
            self.update_mode_ui()
            await self.refresh_all()

    async def action_rename_item(self) -> None:
        """Rename the currently highlighted workspace or session."""
        ws_list = self.query_one("#workspace_list", ListView)
        sess_list = self.query_one("#session_list", ListView)

        if ws_list.has_focus and ws_list.index is not None:
            workspaces = await self.app.store.list_workspaces()
            workspaces = [ws for ws in workspaces if ws.get("status") != "SYSTEM"]
            if ws_list.index < len(workspaces):
                ws = workspaces[ws_list.index]
                old_name = ws["name"]

                async def handle_ws_rename(new_name: str) -> None:
                    if new_name and new_name.strip() and new_name != old_name:
                        try:
                            await self.app.power_facade.rename_workspace(ws["id"], new_name.strip())
                            await self.refresh_workspaces()
                            self.notify(f"Workspace renamed to {new_name.strip()}")
                        except ValueError as e:
                            self.notify(str(e), severity="error")

                self.app.push_screen(RenameDialog("Rename Workspace", old_name), handle_ws_rename)

        elif sess_list.has_focus and sess_list.index is not None:
            if not self.selected_ws_id: return
            sessions = await self.app.store.list_sessions(self.selected_ws_id)
            if sess_list.index < len(sessions):
                sess = sessions[sess_list.index]
                old_name = sess["name"]

                async def handle_sess_rename(new_name: str) -> None:
                    if new_name and new_name.strip() and new_name != old_name:
                        try:
                            await self.app.power_facade.rename_session(sess["id"], new_name.strip())
                            await self.refresh_session_list()
                            self.notify(f"Session renamed to {new_name.strip()}")
                        except ValueError as e:
                            self.notify(str(e), severity="error")

                self.app.push_screen(RenameDialog("Rename Session", old_name), handle_sess_rename)

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
            if ws_list.has_focus:
                if ws_list.index is None and ws_list.children:
                    ws_list.index = 0
                if ws_list.index is not None and ws_list.index < len(ws_list.children):
                    item_id = ws_list.children[ws_list.index].id
                    if item_id and item_id.startswith("ws_"):
                        ws_id = item_id[3:] # Remove prefix
                        if ws_id in self.selected_workspaces:
                            self.selected_workspaces.remove(ws_id)
                        else:
                            self.selected_workspaces.add(ws_id)
                        await self.refresh_workspaces()
            elif sess_list.has_focus:
                if sess_list.index is None and sess_list.children:
                    sess_list.index = 0
                if sess_list.index is not None and sess_list.index < len(sess_list.children):
                    item_id = sess_list.children[sess_list.index].id
                    if item_id and item_id.startswith("sess_"):
                        sess_id = item_id[5:] # Remove prefix
                        if sess_id in self.selected_sessions:
                            self.selected_sessions.remove(sess_id)
                        else:
                            self.selected_sessions.add(sess_id)
                        await self.refresh_session_list()

        elif self.mode == "ORGANIZE" and self.organize_step == 1:
            if sess_list.has_focus:
                if sess_list.index is None and sess_list.children:
                    sess_list.index = 0
                if sess_list.index is not None and sess_list.index < len(sess_list.children):
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
                self.notify("No items selected for deletion.", severity="warning")
                return

            ws_count = len(self.selected_workspaces)
            sess_count = len(self.selected_sessions)
            parts = []
            if ws_count:
                parts.append(f"{ws_count} workspace(s)")
            if sess_count:
                parts.append(f"{sess_count} session(s)")
            msg = f"Delete {' and '.join(parts)}?"

            async def check_confirm(confirmed: bool) -> None:
                if confirmed:
                    for wid in list(self.selected_workspaces):
                        ws = await self.app.store.get_workspace(wid)
                        if ws and ws.get("status") == "SYSTEM":
                            self.notify(f"Cannot delete system workspace: {ws['name']}", severity="error")
                            continue
                        await self.app.power_facade.delete_workspace(wid)
                    for sid in self.selected_sessions:
                        await self.app.power_facade.delete_session(sid)
                    self.notify(f"Deleted {' and '.join(parts)}.")
                    self.mode = "NORMAL"
                    self.selected_workspaces.clear()
                    self.selected_sessions.clear()
                    self.update_mode_ui()
                    await self.refresh_all()

            self.app.push_screen(
                ConfirmationDialog(msg, confirm_label="Delete", cancel_label="Cancel", is_destructive=True),
                check_confirm
            )

        elif self.mode == "ORGANIZE":
            if self.organize_step == 1:
                if not self.selected_sessions:
                    self.notify("Select at least one session to move.", severity="warning")
                    return
                self.organize_step = 2
                self.update_mode_ui()
                self.query_one("#workspace_list").focus()
                await self.refresh_workspaces()
            else:
                ws_list = self.query_one("#workspace_list", ListView)
                if ws_list.index is None: return
                dest_id = ws_list.children[ws_list.index].id[3:]

                dest_ws = await self.app.store.get_workspace(dest_id)
                dest_name = dest_ws["name"] if dest_ws else "workspace"
                count = len(self.selected_sessions)

                async def check_move(confirmed: bool) -> None:
                    if confirmed:
                        for sid in self.selected_sessions:
                            try:
                                await self.app.power_facade.move_session(sid, dest_id)
                            except ValueError as e:
                                self.notify(str(e), severity="error")
                        self.notify(f"Moved {count} session(s) to '{dest_name}'.")
                        self.mode = "NORMAL"
                        self.selected_sessions.clear()
                        self.update_mode_ui()
                        await self.refresh_all()

                self.app.push_screen(
                    ConfirmationDialog(
                        f"Move {count} session(s) to '{dest_name}'?",
                        confirm_label="Move",
                        cancel_label="Cancel",
                        is_destructive=False
                    ),
                    check_move
                )

    async def refresh_all(self):
        # Reset selected_ws_id to force a full re-load of details for the currently selected index
        self.selected_ws_id = None
        await self.refresh_workspaces()
        await self.refresh_session_list()

    def _format_workspace_label(self, prefix: str, ws_name: str, running_cnt: int) -> str:
        max_width = 28
        prefix_plain_len = 3

        if running_cnt > 0:
            full_badge = f" [bold #34d399]({running_cnt} running)[/]"
            full_badge_len = len(f" ({running_cnt} running)")
            compact_badge = f" [bold #34d399]({running_cnt})[/]"
            compact_badge_len = len(f" ({running_cnt})")

            if len(ws_name) + full_badge_len <= (max_width - prefix_plain_len):
                badge = full_badge
                badge_len = full_badge_len
            else:
                badge = compact_badge
                badge_len = compact_badge_len
        else:
            badge = ""
            badge_len = 0

        avail_name = max_width - prefix_plain_len - badge_len
        if len(ws_name) > avail_name and avail_name > 3:
            display_name = ws_name[:avail_name - 1] + "…"
        else:
            display_name = ws_name

        return f"{prefix}{display_name}{badge}"

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

        # Calculate running job counts per workspace
        ws_running_counts: Dict[str, int] = {}
        for ws in workspaces:
            try:
                cnt = await self.app.power_facade.get_workspace_running_jobs_count(ws["id"])
                if cnt > 0:
                    ws_running_counts[ws["id"]] = cnt
            except Exception:
                pass

        # Surgical update: if IDs match, update labels in-place
        current_ids = [c.id for c in ws_list.children if c.id]
        expected_ids = [f"ws_{ws['id']}" for ws in workspaces]

        if current_ids == expected_ids:
            for i, ws in enumerate(workspaces):
                if self.mode == "DELETE":
                    prefix = r"[bold #f85149]\[x][/]  " if ws["id"] in self.selected_workspaces else r"[#94a3b8]\[ ][/]  "
                elif self.mode == "ORGANIZE" and self.organize_step == 2:
                    prefix = r"[bold #eab308]->[/]  " if i == old_index else "    "
                else:
                    prefix = r"[#38bdf8]▸[/]  " if (ws_list.index == i) else r"[#94a3b8]▪[/]  "

                cnt = ws_running_counts.get(ws["id"], 0)
                formatted_label = self._format_workspace_label(prefix, ws["name"], cnt)
                try:
                    label = ws_list.children[i].query_one(Static)
                    label.update(formatted_label)
                except Exception:
                    pass
        else:
            await ws_list.remove_children()
            for i, ws in enumerate(workspaces):
                if self.mode == "DELETE":
                    prefix = r"[bold #f85149]\[x][/]  " if ws["id"] in self.selected_workspaces else r"[#94a3b8]\[ ][/]  "
                elif self.mode == "ORGANIZE" and self.organize_step == 2:
                    prefix = r"[bold #eab308]->[/]  " if i == old_index else "    "
                else:
                    prefix = r"[#38bdf8]▸[/]  " if (old_index == i or (old_index is None and i == 0)) else r"[#94a3b8]▪[/]  "
                cnt = ws_running_counts.get(ws["id"], 0)
                formatted_label = self._format_workspace_label(prefix, ws["name"], cnt)
                ws_list.append(ListItem(Static(formatted_label), id=f"ws_{ws['id']}"))

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
            self.app.selected_session_id = None
            details_area = self.query_one("#session_details_content", Vertical)
            await details_area.remove_children()
            await details_area.mount(Label("Select a session to view details", classes="placeholder_text"))

        self.selected_ws_id = ws_id
        self.app.selected_workspace_id = ws_id
        store = self.app.store
        ws = await store.get_workspace(ws_id)
        if not ws: return

        self.query_one("#ws_title", Label).update(ws["name"].upper())
        ws_status = ws.get("status", "ACTIVE")
        if ws_status == "CLOSED":
            self.query_one("#ws_status_badge", Label).update("[dim #64748b][ARCHIVED][/]")
        else:
            self.query_one("#ws_status_badge", Label).update("")

        all_sessions = await store.list_sessions(ws_id)
        active_sessions = [s for s in all_sessions if s.get("status") == "ACTIVE"]
        closed_sessions = [s for s in all_sessions if s.get("status") == "CLOSED"]
        active_count = len(active_sessions)
        closed_count = len(closed_sessions)
        running_jobs_total = sum(self.app.power_facade.get_active_jobs_count(s["id"]) for s in all_sessions)

        if self.session_filter == "HISTORY":
            display_sessions = closed_sessions
            try:
                self.query_one("#sessions_pane_title", Label).update("◆ ARCHIVED SESSIONS")
                self.query_one("#session_filter_badge", Label).update(f"[History: {closed_count}]")
            except Exception: pass
        else:
            display_sessions = active_sessions
            try:
                self.query_one("#sessions_pane_title", Label).update("◆ ACTIVE SESSIONS")
                self.query_one("#session_filter_badge", Label).update(f"[Active: {active_count}]")
            except Exception: pass

        sess_list = self.query_one("#session_list", ListView)
        old_index = sess_list.index
        was_focused = sess_list.has_focus

        current_sess_ids = [c.id for c in sess_list.children if c.id]
        expected_sess_ids = [f"sess_{s['id']}" for s in display_sessions]

        def get_session_display(s: Dict) -> str:
            is_active = s.get("status") == "ACTIVE"
            active_jobs = self.app.power_facade.get_active_jobs_count(s["id"])
            if is_active:
                if active_jobs > 0:
                    status_icon = "[bold #34d399]●[/]"
                    suffix = f" [#34d399]({active_jobs} running)[/]"
                else:
                    status_icon = "[#38bdf8]●[/]"
                    suffix = ""
            else:
                status_icon = "[#94a3b8]■[/]"
                closed_date = s.get("closed_at", "")[:10] if s.get("closed_at") else "archived"
                suffix = f" [#94a3b8]({closed_date})[/]"


            if self.mode == "DELETE":
                prefix = r"[bold #f85149]\[x][/]  " if s["id"] in self.selected_sessions else r"[#94a3b8]\[ ][/]  "
            elif self.mode == "ORGANIZE" and self.organize_step == 1:
                prefix = r"[bold #eab308]\[x][/]  " if s["id"] in self.selected_sessions else r"[#94a3b8]\[ ][/]  "
            else:
                prefix = f"{status_icon}  "
            return f"{prefix}{s['name']}{suffix}"

        if current_sess_ids == expected_sess_ids:
            for i, s in enumerate(display_sessions):
                try:
                    label = sess_list.children[i].query_one(Static)
                    label.update(get_session_display(s))
                except Exception:
                    pass
        else:
            await sess_list.remove_children()
            for s in display_sessions:
                sess_list.append(ListItem(Static(get_session_display(s)), id=f"sess_{s['id']}"))

        if display_sessions and old_index is None:
             sess_list.index = 0
             await self.show_session_details(display_sessions[0]["id"], force=False)
        elif display_sessions and old_index is not None:
            sess_list.index = old_index if old_index < len(display_sessions) else 0
            await self.show_session_details(display_sessions[sess_list.index]["id"], force=False)
        elif not display_sessions:
            await sess_list.remove_children()
            placeholder = "[dim #94a3b8]No archived sessions[/]" if self.session_filter == "HISTORY" else "[dim #94a3b8]No active sessions · [Ctrl+S][/]"
            sess_list.append(ListItem(Static(f"  {placeholder}"), id="empty_sess_placeholder", disabled=True))
            self.selected_session_id = None
            self.app.selected_session_id = None
            details_area = self.query_one("#session_details_content", Vertical)
            await details_area.remove_children()
            if self.session_filter == "HISTORY":
                title = "No archived sessions in this workspace"
                hint = "Press [Ctrl+A] on an active session to archive it."
            else:
                title = "No active sessions in this workspace"
                hint = "Press [Ctrl+S] to create a session or [Ctrl+H] for History."
            await details_area.mount(
                Vertical(
                    Label(title, classes="session_empty_title"),
                    Label(hint, classes="session_empty_hint"),
                    classes="session_empty_card",
                )
            )

        if was_focused: sess_list.focus()

        self.query_one("#metric_sessions", Static).update(f"Sessions: {active_count} Active · {closed_count} Archived")
        self.query_one("#metric_active", Static).update(f"Running Jobs: {running_jobs_total}")

        # Update Host/Service counts for the workspace
        ws_stats = await store.get_stats()
        self.query_one("#metric_hosts", Static).update(f"Hosts: {ws_stats.get('network.host', 0)}")
        self.query_one("#metric_services", Static).update(f"Services: {ws_stats.get('network.service', 0)}")

        # Activity list: Only update if the recent activities actually changed
        activity = await store.get_recent_activity(ws_id, limit=10)
        act_list = self.query_one("#activity_list", ListView)
        new_act_keys = [f"{a.get('id', '')}_{a.get('timestamp', '')}" for a in activity]
        if getattr(self, "_last_act_keys", None) != new_act_keys:
            self._last_act_keys = new_act_keys
            await act_list.clear()
            for a in activity:
                ts = a["timestamp"][11:16] if a["timestamp"] else "--:--"
                msg = format_activity(a["session_name"], a["schema_type"], a["human_readable"], finding_json=a["finding_json"])
                act_list.append(ListItem(Static(f"{ts} {msg}")))

    async def on_key(self, event: events.Key) -> None:
        """Handle left/right arrow keys to navigate between workspace and session lists across all modes."""
        ws_list = self.query_one("#workspace_list", ListView)
        sess_list = self.query_one("#session_list", ListView)

        if event.key == "right":
            if ws_list.has_focus:
                # Move IN from workspace list to session list
                event.stop()
                if sess_list.children:
                    sess_list.focus()
                    if sess_list.index is None:
                        sess_list.index = 0
            elif sess_list.has_focus and self.mode == "NORMAL":
                # Move IN from session list to execute/enter the session (only in NORMAL mode)
                event.stop()
                if sess_list.index is not None and sess_list.children and self.selected_session_id:
                    self.app.switch_screen("power_mode")
        elif event.key == "left":
            if sess_list.has_focus:
                # Move OUT from session list back to workspace list, preserving highlighted workspace
                event.stop()
                ws_list.focus()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.mode in ("NORMAL", "DELETE") or (self.mode == "ORGANIZE" and self.organize_step == 1):
            if event.list_view.id == "workspace_list":
                if event.item and event.item.id and event.item.id.startswith("ws_"):
                    ws_id = event.item.id[3:]
                    await self.show_workspace_details(ws_id)
            elif event.list_view.id == "session_list":
                if event.item and event.item.id and event.item.id.startswith("sess_"):
                    sess_id = event.item.id[5:]
                    await self.show_session_details(sess_id)
        elif self.mode == "ORGANIZE" and self.organize_step == 2:
            if event.list_view.id == "workspace_list":
                await self.refresh_workspaces()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.mode == "NORMAL":
            if event.list_view.id == "workspace_list":
                if event.item and event.item.id and event.item.id.startswith("ws_"):
                    ws_id = event.item.id[3:]
                    await self.show_workspace_details(ws_id)
            elif event.list_view.id == "session_list":
                if event.item and event.item.id and event.item.id.startswith("sess_"):
                    self.app.switch_screen("power_mode")
        elif self.mode == "DELETE":
            await self.action_toggle_selection()
        elif self.mode == "ORGANIZE":
            if self.organize_step == 1 and event.list_view.id == "session_list":
                 await self.action_toggle_selection()
            elif self.organize_step == 2 and event.list_view.id == "workspace_list":
                await self.action_confirm_action()

    async def show_session_details(self, sess_id: str, force: bool = False) -> None:
        """Display metadata and stats for a selected session with clear visual hierarchy."""
        if self.selected_session_id == sess_id and not force:
            return

        is_same_session = (self.selected_session_id == sess_id)
        self.selected_session_id = sess_id
        self.app.selected_session_id = sess_id
        store = self.app.store
        session = await store.get_session(sess_id)
        if not session: return

        stats = await store.get_stats(sess_id)

        container = self.query_one("#session_details_content", Vertical)

        active_jobs_count = self.app.power_facade.get_active_jobs_count(sess_id)
        closed_jobs_count = await store.get_closed_events_count(sess_id)
        total_entities = stats.get("total", sum(v for k, v in stats.items() if k != "total"))

        # 1. Session Identity Card
        is_active = session.get("status") == "ACTIVE"
        if is_active:
            if active_jobs_count > 0:
                status_text = f"[bold #34d399]● RUNNING ({active_jobs_count})[/]"
            else:
                status_text = "[dim #34d399]● ACTIVE[/]"
        else:
            status_text = "[dim #64748b][ARCHIVED / CLOSED][/]"

        entity_stats = {k: v for k, v in stats.items() if k != "total" and v > 0}
        if not hasattr(self, "_last_rendered_entity_stats"):
            self._last_rendered_entity_stats = {}
        last_entity_stats = self._last_rendered_entity_stats.get(sess_id)

        # If the session card is already mounted and entity stats haven't changed, update in place!
        if is_same_session and container.children and last_entity_stats == entity_stats:
            try:
                pill = self.query_one("#session_status_pill", Static)
                pill.update(status_text)

                act_lbl = self.query_one("#session_stat_active_val", Label)
                act_lbl.update(str(active_jobs_count))
                act_lbl.set_class(active_jobs_count > 0, "active-val")
                act_lbl.set_class(active_jobs_count == 0, "dim-val")

                self.query_one("#session_stat_closed_val", Label).update(str(closed_jobs_count))
                self.query_one("#session_stat_entities_val", Label).update(str(total_entities))
                self.query_one("#session_graph_total_badge", Label).update(f"{total_entities} Total")
                return
            except Exception:
                pass

        self._last_rendered_entity_stats[sess_id] = dict(entity_stats)
        await container.remove_children()

        created_str = session.get("created_at", "")[:16] if session.get("created_at") else "--:--"
        closed_str = f" · Archived: {session.get('closed_at', '')[:16]}" if session.get("closed_at") else ""
        short_id = session.get("id", "")[:8]

        header_card = Vertical(
            Horizontal(
                Label(session.get("name", "Untitled Session"), classes="session_title_text"),
                Static(status_text, classes="session_status_pill", id="session_status_pill"),
                classes="session_title_row"
            ),
            Horizontal(
                Label(f"Created: {created_str}{closed_str}", classes="session_meta_text"),
                Label(f"ID: {short_id}", classes="session_meta_id"),
                classes="session_meta_row"
            ),
            classes="session_id_card"
        )
        await container.mount(header_card)

        # 2. Activity & Workload Metrics (3-box summary grid)
        active_cls = "active-val" if active_jobs_count > 0 else "dim-val"
        metrics_grid = Horizontal(
            Vertical(
                Label("ACTIVE JOBS", classes="session_stat_box_label"),
                Label(str(active_jobs_count), classes=f"session_stat_box_val {active_cls}", id="session_stat_active_val"),
                classes="session_stat_box"
            ),
            Vertical(
                Label("CLOSED TABS", classes="session_stat_box_label"),
                Label(str(closed_jobs_count), classes="session_stat_box_val", id="session_stat_closed_val"),
                classes="session_stat_box"
            ),
            Vertical(
                Label("ENTITIES", classes="session_stat_box_label"),
                Label(str(total_entities), classes="session_stat_box_val discoveries-val", id="session_stat_entities_val"),
                classes="session_stat_box"
            ),
            classes="session_metrics_grid"
        )
        await container.mount(metrics_grid)

        # 3. Discovered Graph Entities Card
        entity_stats = {k: v for k, v in stats.items() if k != "total" and v > 0}

        graph_children = [
            Horizontal(
                Label("◆ GRAPH ENTITIES", classes="session_graph_header_title"),
                Label(f"{total_entities} Total", classes="session_graph_header_badge", id="session_graph_total_badge"),
                classes="session_graph_header_row"
            )
        ]

        if not entity_stats:
            graph_children.append(
                Vertical(
                    Label("No graph entities discovered yet", classes="entity_empty_notice"),
                    Label("Execute tools in Power Mode to populate graph", classes="entity_empty_hint"),
                    classes="entity_empty_box"
                )
            )
        else:
            list_rows = []
            for schema, count in sorted(entity_stats.items(), key=lambda x: get_schema_sort_key(x[0])):
                symbol, color, display_name = format_schema_label(schema)
                list_rows.append(
                    Horizontal(
                        Label(f"[{color}]{symbol}[/]  {display_name}", classes="entity_stat_label"),
                        Label(" ···········································································", classes="entity_stat_dots"),
                        Static(f"[{color}]{count}[/]", classes="entity_stat_badge"),
                        classes="entity_stat_row"
                    )
                )
            graph_children.append(Vertical(*list_rows, classes="entity_stats_list"))

        graph_card = Vertical(*graph_children, classes="session_graph_card")
        await container.mount(graph_card)

        # 4. Action Card
        if is_active:
            actions_card = Vertical(
                Label("Press [Enter] to launch workspace · [Ctrl+A] Archive Session", classes="session_quick_hint", markup=False),
                Button("❯  ENTER POWER MODE", classes="enter_session_btn", variant="primary"),
                classes="session_actions_card"
            )
        else:
            actions_card = Vertical(
                Label("Press [Enter] for Audit Log · [Ctrl+A] Reopen Engagement", classes="session_quick_hint", markup=False),
                Horizontal(
                    Button("›  VIEW AUDIT LOG", id="view_audit_btn", classes="enter_session_btn", variant="default"),
                    Button("↺  REOPEN ENGAGEMENT", id="reopen_session_btn", variant="success"),
                    classes="archived_actions_row"
                ),
                classes="session_actions_card"
            )
        await container.mount(actions_card)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.has_class("enter_session_btn"):
            self.app.switch_screen("power_mode")
        elif event.button.id == "reopen_session_btn":
            self.run_worker(self.action_toggle_archive_session())

    async def action_toggle_history_mode(self) -> None:
        """Toggle session view between ACTIVE and HISTORY (archived)."""
        self.session_filter = "HISTORY" if self.session_filter == "ACTIVE" else "ACTIVE"
        filter_name = "Archived / History" if self.session_filter == "HISTORY" else "Active Sessions"
        self.notify(f"Switched session view to: {filter_name}")
        if self.selected_ws_id:
            await self.show_workspace_details(self.selected_ws_id)

    async def action_toggle_archive_session(self) -> None:
        """Archive or reopen the currently selected session."""
        if not self.selected_session_id:
            self.notify("No session selected.", severity="warning")
            return
        session = await self.app.store.get_session(self.selected_session_id)
        if not session:
            return
        if session.get("status") == "ACTIVE":
            await self.app.power_facade.close_session(self.selected_session_id)
            self.notify(f"Archived session '{session.get('name')}' (audit trail preserved).")
        else:
            await self.app.power_facade.reopen_session(self.selected_session_id)
            self.notify(f"Reopened session '{session.get('name')}' to ACTIVE.")

        if self.selected_ws_id:
            await self.show_workspace_details(self.selected_ws_id)

    async def load_workspace_sessions(self, ws_id: str) -> None:
        """Convenience alias for show_workspace_details."""
        await self.show_workspace_details(ws_id)

    def action_show_shortcuts(self) -> None:
        from cyguide.ui.screens.power import ShortcutsDialog
        self.app.push_screen(ShortcutsDialog())

    def action_nav_learning(self) -> None:
        self.app.switch_screen("tool_browser")

    async def action_new_workspace(self) -> None:
        default_name = datetime.now().strftime("%H:%M:%S")

        async def handle_create_workspace(name: Optional[str]) -> None:
            if name is None:
                return
            name = name.strip() or default_name
            try:
                ws_id = await self.app.power_facade.create_workspace(name)
                await self.refresh_workspaces()
                ws_list = self.query_one("#workspace_list", ListView)
                for i, child in enumerate(ws_list.children):
                    if child.id == f"ws_{ws_id}":
                        ws_list.index = i
                        break
                await self.show_workspace_details(ws_id)
                self.notify(f"Created workspace '{name}'")
            except ValueError as e:
                self.notify(str(e), severity="error")

        self.app.push_screen(RenameDialog("New Workspace Name", default_name), handle_create_workspace)

    async def action_new_session(self) -> None:
        if not self.selected_ws_id:
            self.notify("Select a workspace first.", severity="error")
            return
        default_name = datetime.now().strftime("%H:%M:%S")

        async def handle_create_session(name: Optional[str]) -> None:
            if name is None:
                return
            name = name.strip() or default_name
            try:
                sess_id = await self.app.power_facade.create_session(self.selected_ws_id, name)
                await self.refresh_session_list()
                sess_list = self.query_one("#session_list", ListView)
                for i, child in enumerate(sess_list.children):
                    if child.id == f"sess_{sess_id}":
                        sess_list.index = i
                        break
                await self.show_session_details(sess_id)
                self.notify(f"Created session '{name}'")
            except ValueError as e:
                self.notify(str(e), severity="error")

        self.app.push_screen(RenameDialog("New Session Name", default_name), handle_create_session)
