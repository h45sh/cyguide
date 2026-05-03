"""Power Mode screen implementation."""
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, Input, ListItem, ListView
from textual.containers import Vertical, Horizontal
from cyguide.schemas.network import NetworkHost

class PowerModeScreen(Screen):
    """An advanced, flexible workspace."""

    BINDINGS = [
        ("escape", "nav_dashboard", "Dashboard"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("ctrl+d", "nav_dashboard", "Dashboard"),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self):
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="power_sidebar"):
                yield Label("SESSION GRAPH", classes="section_header")
                with ListView(classes="tool_list"):
                    yield ListItem(Static("127.0.0.1 (Target)"), id="node_local")

            with Vertical(id="power_workspace"):
                yield Label("COMMAND ORCHESTRATOR", classes="section_header")
                yield Static("Ready for multi-tool workflow commands...\n\nExample: nmap | whois", id="terminal_mock")
                yield Vertical(id="power_log_container")
                yield Input(placeholder="Enter tool name (e.g., nmap)...", id="power_input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        tool_name = event.value.strip().lower()
        if not tool_name:
            return

        event.input.value = ""
        log_container = self.query_one("#power_log_container", Vertical)

        if tool_name not in self.app.registry.tools:
            await log_container.mount(Label(f"Error: Tool '{tool_name}' not found.", classes="error"))
            return

        await log_container.mount(Label(f"Executing {tool_name}..."))

        # Power Mode currently uses a default target for demonstration
        target = NetworkHost.create(ip="127.0.0.1")

        try:
            # We use the power engine if available, or direct executor
            async for finding in self.app.power_engine.execute(tool_name, target, {}):
                await log_container.mount(Static(f"[+] {finding.schema_type}: {finding.pik}"))
                self.notify(f"Power Mode: Discovered {finding.schema_type}")
        except Exception as e:
            await log_container.mount(Label(f"Command Error: {str(e)}", classes="error"))

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        sidebar = self.query_one("#power_sidebar")
        sidebar.toggle_class("collapsed")

    def action_nav_dashboard(self) -> None:
        """Go back to the Workspace Manager."""
        self.app.switch_screen("dashboard")
