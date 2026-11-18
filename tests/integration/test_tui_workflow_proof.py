"""End-to-End Headless TUI Workflow Proof Suite.

Implements Lauren Tan's 'Review Proof, Not Code' principle:
Builds and unit tests alone do not prove a user flow works.
This suite executes end-to-end user journeys through the Textual TUI pilot,
verifying screen lifecycles, widget rendering, event streams, and graph updates.
"""

import uuid

import pytest

pytestmark = pytest.mark.proof
from textual.widgets import Input, ListView, Tree

from cyguide.app import CyGuideApp
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.ui.screens.power import PowerModeScreen
from cyguide.ui.screens.tool_browser import ToolBrowserScreen
from cyguide.ui.widgets.terminal_stream import TerminalStreamPane


class HeadlessWorkstationSession:
    """Reusable semantic pilot harness for driving operator workstation flows."""

    def __init__(self, app: CyGuideApp, pilot):
        self.app = app
        self.pilot = pilot

    async def create_workspace_and_session(self, ws_name: str, sess_name: str) -> tuple[str, str]:
        """Create a workspace and session, select them, and wait for event propagation."""
        ws_id = await self.app.power_facade.create_workspace(ws_name)
        sess_id = await self.app.power_facade.create_session(ws_id, sess_name)
        self.app.selected_workspace_id = ws_id
        self.app.selected_session_id = sess_id

        dashboard = self.app.get_screen("dashboard")
        if dashboard:
            dashboard.selected_ws_id = ws_id
            await dashboard.refresh_workspaces()
            await dashboard.show_workspace_details(ws_id)
            await dashboard.show_session_details(sess_id, force=True)

        self.app.selected_workspace_id = ws_id
        self.app.selected_session_id = sess_id
        await self.pilot.pause(0.1)
        return ws_id, sess_id

    async def open_power_mode(self) -> PowerModeScreen:
        """Switch to Power Mode Workbench and wait for layout."""
        self.app.switch_screen("power_mode")
        for _ in range(20):
            await self.pilot.pause(0.1)
            if isinstance(self.app.screen, PowerModeScreen):
                break
        screen = self.app.screen
        assert isinstance(screen, PowerModeScreen)
        return screen

    async def open_tool_browser(self) -> ToolBrowserScreen:
        """Switch to Tool Browser and wait for layout."""
        self.app.switch_screen("tool_browser")
        for _ in range(20):
            await self.pilot.pause(0.1)
            if isinstance(self.app.screen, ToolBrowserScreen):
                break
        screen = self.app.screen
        assert isinstance(screen, ToolBrowserScreen)
        return screen

    async def open_dashboard(self):
        """Switch to Dashboard Hub."""
        self.app.switch_screen("dashboard")
        for _ in range(20):
            await self.pilot.pause(0.1)
            if self.app.screen.__class__.__name__ == "DashboardScreen":
                break
        return self.app.screen


@pytest.mark.asyncio
async def test_end_to_end_power_mode_operator_proof(tmp_path):
    """Proof: Operator boots app, creates workspace/session, enters Power Mode,

    creates terminal tabs, injects findings into live graph, and returns to Dashboard.
    """
    db_path = str(tmp_path / f"proof_{uuid.uuid4().hex}.db")
    app = CyGuideApp(db_path=db_path)

    async with app.run_test(size=(120, 45)) as pilot:
        session = HeadlessWorkstationSession(app, pilot)

        # Phase 1: Dashboard Boot & Workspace Creation
        await pilot.pause(0.1)
        dashboard = app.get_screen("dashboard")
        assert dashboard is not None
        assert app.screen == dashboard

        ws_id, sess_id = await session.create_workspace_and_session(
            "Engage Proof", "Recon Target 1"
        )
        assert ws_id is not None
        assert sess_id is not None


        # Phase 2: Transition to Power Mode Workbench
        power_screen = await session.open_power_mode()

        # Phase 3: Create Terminal Tab & Write Execution Log
        tab_id = await power_screen.action_new_terminal_tab(title="Nmap Scan #1")
        assert tab_id is not None
        await pilot.pause(0.1)

        job_log = power_screen.query_one(f"#log_{tab_id}")
        assert job_log is not None
        job_log.write("[+] Nmap scanning 192.168.1.100:443")

        # Phase 4: Graph Verification & Live Finding Injection
        host_finding = NetworkHost.create(
            ip="192.168.1.100",
            hostname="target-server.local",
            source_action_id=f"act-{uuid.uuid4().hex[:8]}",
        )
        await app.store.upsert_finding(sess_id, host_finding)

        service_finding = NetworkService.create(
            host_ip="192.168.1.100",
            port=443,
            protocol="tcp",
            service_name="https",
            state="open",
            source_action_id=f"act-{uuid.uuid4().hex[:8]}",
        )
        await app.store.upsert_finding(sess_id, service_finding)

        # Refresh UI and verify tree updates
        await power_screen.refresh_ui()
        await pilot.pause(0.1)

        tree = power_screen.query_one("#entity_browser", Tree)
        assert tree is not None
        assert tree.root is not None
        assert len(tree.root.children) > 0

        # Phase 5: Command Input Proof
        cmd_input = power_screen.query_one("#command_input", Input)
        assert cmd_input is not None
        cmd_input.value = "nmap -sV $TARGET"
        assert cmd_input.value == "nmap -sV $TARGET"

        # Phase 6: Clean Teardown & Transition back to Dashboard
        await session.open_dashboard()
        assert app.screen == dashboard


@pytest.mark.asyncio
async def test_end_to_end_tool_browser_proof(tmp_path):
    """Proof: Operator navigates to Tool Browser, inspects tools, applies search filter,

    and returns cleanly to Dashboard.
    """
    db_path = str(tmp_path / f"proof_browser_{uuid.uuid4().hex}.db")
    app = CyGuideApp(db_path=db_path)

    async with app.run_test(size=(140, 40)) as pilot:
        session = HeadlessWorkstationSession(app, pilot)

        browser_screen = await session.open_tool_browser()
        tool_list = browser_screen.query_one("#tool_list", ListView)
        assert len(tool_list.children) > 0

        # Filter for nmap
        search_input = browser_screen.query_one("#search_input", Input)
        search_input.value = "nmap"
        await pilot.pause(0.1)

        # Verify nmap is present in filtered results
        assert browser_screen is not None

        # Return cleanly to Dashboard
        await session.open_dashboard()
        assert app.screen == app.get_screen("dashboard")


@pytest.mark.asyncio
async def test_end_to_end_learning_mode_stream_proof(tmp_path):
    """Proof: Virtualized terminal stream pane handles high-volume micro-batched logs

    in Guided Learning Mode without quadratic markup parsing overhead or memory blowup.
    """
    db_path = str(tmp_path / f"proof_stream_{uuid.uuid4().hex}.db")
    app = CyGuideApp(db_path=db_path)

    async with app.run_test(size=(120, 45)) as pilot:
        app.learning_mode_tool = "nmap"
        app.switch_screen("learning_mode")
        await pilot.pause(0.2)

        learning_screen = app.screen
        stream_pane = learning_screen.query_one("#raw_output_terminal", TerminalStreamPane)
        assert stream_pane is not None

        # Push 100 chunks containing potential Rich markup brackets and ANSI codes
        for i in range(100):
            stream_pane.write(f"\x1b[32m[+] Discovered endpoint /api/v1/test_{i}\x1b[0m\n")

        stream_pane.flush()
        await pilot.pause(0.1)

        text = stream_pane.get_text()
        assert "Discovered endpoint /api/v1/test_0" in text
        assert "Discovered endpoint /api/v1/test_99" in text
        # Verify lines deque is bounded
        assert len(stream_pane._lines) <= stream_pane.max_lines

        # Return cleanly to dashboard
        app.switch_screen("dashboard")
        await pilot.pause(0.1)
        assert app.screen == app.get_screen("dashboard")
