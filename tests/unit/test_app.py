import pytest
from cyguide.app import CyGuideApp

def test_app_structure():
    """Verify the app has the expected screens and title."""
    app = CyGuideApp()
    assert app.TITLE == "CyGuide"
    assert "dashboard" in app.SCREENS
    assert "learning_mode" in app.SCREENS
    assert "power_mode" in app.SCREENS
    assert "tool_browser" in app.SCREENS

@pytest.mark.asyncio
async def test_app_component_init(tmp_path):
    """Smoke test for app component setup without running the full TUI."""
    app = CyGuideApp()
    # We can't easily call on_mount because it's managed by Textual's loop,
    # but we can verify the class structure.
    assert hasattr(app, "SCREENS")

def test_format_activity():
    """Verify that format_activity formats different schemas and event types correctly."""
    from cyguide.ui.screens.home import format_activity
    import json

    # 1. System event (Ran nmap)
    line = format_activity("Session 22:40:20", "system.event", "Ran nmap")
    assert line == "[22:40:20] Run: nmap"

    # 2. network.host
    host_json = json.dumps({"pik": {"ip": "192.168.1.1"}, "data": {}})
    line = format_activity("Session 22:40:20", "network.host", "Discovered network.host", finding_json=host_json)
    assert line == "[22:40:20] Host: 192.168.1.1"

    # 3. network.service
    service_json = json.dumps({"pik": {"port": 80}, "data": {"service_name": "http"}})
    line = format_activity("Session 22:40:20", "network.service", "Discovered network.service", finding_json=service_json)
    assert line == "[22:40:20] Port: 80 (http)"

    # 4. dns.record
    dns_json = json.dumps({"pik": {"domain": "api.example.com"}})
    line = format_activity("Session 22:40:20", "dns.record", "Discovered dns.record", finding_json=dns_json)
    assert line == "[22:40:20] Domain: api.example.com"

    # 5. web.endpoint
    web_json = json.dumps({"pik": {"url": "https://example.com/admin"}})
    line = format_activity("Session 22:40:20", "web.endpoint", "Discovered web.endpoint", finding_json=web_json)
    assert line == "[22:40:20] URL: example.com/admin"

    # 6. network.netblock
    net_json = json.dumps({"pik": {"cidr": "10.0.0.0/24"}})
    line = format_activity("MyLongSessionName", "network.netblock", "Discovered network.netblock", finding_json=net_json)
    assert line == "[MyLongSe..] Netblock: 10.0.0.0/24"

@pytest.mark.asyncio
async def test_learning_screen_resume_preserves_buffer():
    """Verify that returning from expanded output view does not erase learning mode output."""
    from cyguide.ui.screens.learning import LearningModeScreen
    from textual._context import active_app
    from unittest.mock import MagicMock

    mock_app = MagicMock()
    mock_app.learning_mode_tool = "nmap"
    token = active_app.set(mock_app)

    try:
        screen = LearningModeScreen()
        screen.active_tool = "nmap"
        screen.log_buffer = ["Line 1\n", "Line 2\n"]
        screen.explanation_buffer = "Explanation content"

        # When screen resumes with same tool, update_tool_context(force=False) must not wipe buffers
        await screen.update_tool_context(force=False)
        assert screen.log_buffer == ["Line 1\n", "Line 2\n"]
        assert screen.explanation_buffer == "Explanation content"
    finally:
        active_app.reset(token)

@pytest.mark.asyncio
async def test_learning_screen_clear_buttons(tmp_path):
    """Verify that clicking clear buttons in explanation and raw output tabs clears their respective content."""
    db_file = str(tmp_path / "test_app_clear.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        app.learning_mode_tool = "nmap"
        app.switch_screen("learning_mode")
        await pilot.pause()

        screen = app.screen
        assert screen.query_one("#clear_explanation_btn") is not None
        assert screen.query_one("#clear_output_btn") is not None

        # Populate buffers
        screen.explanation_buffer = "Some explanation text"
        screen.log_buffer = ["Log entry 1\n", "Log entry 2\n"]

        # Click clear explanation button
        await pilot.click("#clear_explanation_btn")
        await pilot.pause()
        assert screen.explanation_buffer == ""

        # Switch to raw output tab and click clear output button
        screen.query_one("#learning_tabs").active = "tab_output"
        await pilot.pause()
        await pilot.click("#clear_output_btn")
        await pilot.pause()
        assert screen.log_buffer == []

def test_css_stylesheet_syntax():
    """Verify that the Textual CSS stylesheet contains zero parsing or property errors."""
    from textual.css.stylesheet import Stylesheet
    ss = Stylesheet()
    ss.read("cyguide/ui/style.css")
    ss.parse()
    assert len(ss.rules) > 0

@pytest.mark.asyncio
async def test_app_headless_mount_and_screens(tmp_path):
    """Verify that the app mounts and compiles CSS across all screens without crashing."""
    db_file = str(tmp_path / "test_app.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        for screen_name in ["dashboard", "power_mode", "tool_browser"]:
            app.switch_screen(screen_name)
            await pilot.pause()
            assert app.screen is not None

@pytest.mark.asyncio
async def test_confirmation_dialog_keyboard_navigation():
    """Verify that left/right/up/down keys switch button focus and Escape cancels."""
    from cyguide.ui.screens.home import ConfirmationDialog
    from textual.app import App
    from textual.widgets import Label

    class DummyApp(App):
        def compose(self):
            yield Label("Root")

    app = DummyApp()
    async with app.run_test() as pilot:
        dialog = ConfirmationDialog("Test Confirmation?", confirm_label="Delete", cancel_label="Cancel", is_destructive=True)
        app.push_screen(dialog)
        await pilot.pause(0.2)

        # Initial focus should be on cancel button for destructive dialogs
        assert app.focused.id == "cancel"

        # Left arrow moves to confirm
        await pilot.press("left")
        await pilot.pause(0.1)
        assert app.focused.id == "confirm"

        # Right arrow moves back to cancel
        await pilot.press("right")
        await pilot.pause(0.1)
        assert app.focused.id == "cancel"

        # Escape dismisses dialog
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app.screen != dialog

@pytest.mark.asyncio
async def test_rename_dialog_keyboard_navigation():
    """Verify that down/up/left/right navigate and Escape cancels in RenameDialog."""
    from cyguide.ui.screens.home import RenameDialog
    from textual.app import App
    from textual.widgets import Label

    class DummyApp(App):
        def compose(self):
            yield Label("Root")

    app = DummyApp()
    async with app.run_test() as pilot:
        dialog = RenameDialog("Rename Item", "Original")
        app.push_screen(dialog)
        await pilot.pause(0.2)

        # Initial focus on input
        assert app.focused.id == "rename_input"

        # Down moves to save button
        await pilot.press("down")
        await pilot.pause(0.1)
        assert app.focused.id == "save"

        # Right moves to cancel button
        await pilot.press("right")
        await pilot.pause(0.1)
        assert app.focused.id == "cancel"

        # Up moves back to input
        await pilot.press("up")
        await pilot.pause(0.1)
        assert app.focused.id == "rename_input"

        # Escape dismisses dialog
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert app.screen != dialog

@pytest.mark.asyncio
async def test_system_commands_show_setting_state():
    """Verify get_system_commands displays setting status with visual indicator without long descriptions."""
    from cyguide.app import CyGuideApp
    app = CyGuideApp()
    async with app.run_test() as pilot:
        commands = list(app.get_system_commands(app.screen))
        anim_cmd = next(c for c in commands if "Toggle Animations" in c.title)
        assert "● ON" in anim_cmd.title or "○ OFF" in anim_cmd.title
        assert anim_cmd.help == ""

        # Verify Toggle Sidebar has been removed from palette
        assert not any("Toggle Sidebar" in c.title for c in commands)


@pytest.mark.asyncio
async def test_tool_health_in_command_palette():
    """Verify tool health has one consolidated option in command palette, with tools under it."""
    from cyguide.app import CyGuideApp
    from cyguide.ui.screens.tool_health_modal import ToolHealthModal
    app = CyGuideApp()
    async with app.run_test() as pilot:
        commands = list(app.get_system_commands(app.screen))
        health_cmd = next(c for c in commands if "Tool Health" in c.title)
        assert health_cmd.help == ""
        assert "Healthy" in health_cmd.title or "Issue" in health_cmd.title

        # Verify individual tools are NOT polluting root command palette options
        assert not any(c.title.startswith("Tool: ") for c in commands)

        # Trigger tool health action to verify all tools are listed under it in the modal
        app.action_show_tool_health()
        await pilot.pause(0.1)
        assert isinstance(app.screen, ToolHealthModal)
        modal_items = list(app.screen.query_one("#tool_health_items").children)
        assert len(modal_items) >= 5  # gobuster, nikto, nmap, subfinder, whois
        assert any("nmap" in str(item.children[0].render()) for item in modal_items)


@pytest.mark.asyncio
async def test_tool_health_arrow_navigation():
    """Verify right arrow navigates into Tool Health list and left arrow navigates back out."""
    from cyguide.app import CyGuideApp
    from cyguide.ui.screens.tool_health_modal import ToolHealthModal
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "CyGuideCommandPalette"

        cl = app.screen.query_one("CommandList")
        tool_health_idx = next(i for i, opt in enumerate(cl.options) if "Tool Health" in str(opt.prompt))
        cl.highlighted = tool_health_idx
        await pilot.pause(0.1)

        # Right arrow moves IN to ToolHealthModal
        await pilot.press("right")
        await pilot.pause(0.2)
        assert isinstance(app.screen, ToolHealthModal)

        # Left arrow moves OUT back to CyGuideCommandPalette
        await pilot.press("left")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "CyGuideCommandPalette"


@pytest.mark.asyncio
async def test_dashboard_tool_health_conditional_visibility():
    """Verify tool health is hidden on dashboard when healthy, but appears when there are errors."""
    from cyguide.app import CyGuideApp
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        dashboard = app.screen
        assert dashboard.__class__.__name__ == "DashboardScreen"

        container = dashboard.query_one("#tool_health_container")
        # In a healthy environment (all 5 tools installed), tool health is hidden
        assert "hidden" in container.classes

        # Simulate a negative tool health status (load error)
        app.registry.load_errors["faulty_tool"] = "Crash during initialization"
        await dashboard.refresh_diagnostics()
        await pilot.pause(0.1)

        # Should now appear on dashboard!
        assert "hidden" not in container.classes
        diag_list = dashboard.query_one("#diagnostics_list")
        items = list(diag_list.children)
        assert len(items) > 0
        assert any("faulty_tool" in str(item.children[0].render()) for item in items)


@pytest.mark.asyncio
async def test_palette_right_arrow_executes_leaf_and_preserves_memory():
    """Verify right arrow executes leaf command in palette and restores highlight on left arrow."""
    from cyguide.app import CyGuideApp
    from cyguide.ui.screens.tool_health_modal import ToolHealthModal
    from textual.command import CommandList

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        # 1. Right arrow on leaf command (Toggle Animations) executes it
        assert app.animations_enabled is True
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        cl = app.screen.query_one(CommandList)
        anim_idx = next(i for i, opt in enumerate(cl.options) if "Toggle Animations" in str(opt.prompt))
        cl.highlighted = anim_idx
        await pilot.pause(0.1)
        await pilot.press("right")
        await pilot.pause(0.2)
        assert app.animations_enabled is False

        # 2. Right arrow on Tool Health moves into sub-dialog, left arrow moves back with highlight preserved
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        cl = app.screen.query_one(CommandList)
        th_idx = next(i for i, opt in enumerate(cl.options) if "Tool Health" in str(opt.prompt))
        cl.highlighted = th_idx
        await pilot.pause(0.1)
        await pilot.press("right")
        await pilot.pause(0.2)
        assert isinstance(app.screen, ToolHealthModal)

        await pilot.press("left")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "CyGuideCommandPalette"
        new_cl = app.screen.query_one(CommandList)
        assert "Tool Health" in str(new_cl.get_option_at_index(new_cl.highlighted).prompt)


@pytest.mark.asyncio
async def test_dashboard_workspace_session_arrow_navigation():
    """Verify left/right arrow navigation between workspaces and sessions on Dashboard."""
    from cyguide.app import CyGuideApp

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        d = app.screen
        ws_list = d.query_one("#workspace_list")
        sess_list = d.query_one("#session_list")

        ws_id = await app.power_facade.create_workspace("TestWS")
        sess_id = await app.power_facade.create_session(ws_id, "TestSession")
        await d.refresh_workspaces()
        await d.show_workspace_details(ws_id)
        await pilot.pause(0.2)

        ws_list.focus()
        ws_idx = ws_list.index
        assert ws_list.has_focus

        # 1. Right arrow moves IN from workspace_list to session_list
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus

        # 2. Left arrow moves OUT back to workspace_list, keeping workspace highlighted
        await pilot.press("left")
        await pilot.pause(0.1)
        assert ws_list.has_focus
        assert ws_list.index == ws_idx

        # 3. Right arrow moves to session_list, and another Right arrow enters the session
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus
        await pilot.press("right")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "PowerModeScreen"

        # 4. In PowerModeScreen, left arrow does NOT exit to dashboard
        await pilot.press("left")
        await pilot.pause(0.1)
        assert app.screen.__class__.__name__ == "PowerModeScreen"

        # 5. Esc returns to dashboard
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "DashboardScreen"


@pytest.mark.asyncio
async def test_dashboard_arrow_navigation_in_delete_and_organize_modes():
    """Verify left/right arrow keys navigate between workspace and session in DELETE and ORGANIZE modes."""
    from cyguide.app import CyGuideApp

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        d = app.screen
        ws_list = d.query_one("#workspace_list")
        sess_list = d.query_one("#session_list")

        ws_id = await app.power_facade.create_workspace("TestWS")
        sess_id = await app.power_facade.create_session(ws_id, "TestSession")
        await d.refresh_workspaces()
        await d.show_workspace_details(ws_id)
        await pilot.pause(0.2)

        # 1. DELETE Mode
        await pilot.press("ctrl+d")
        await pilot.pause(0.2)
        assert d.mode == "DELETE"
        ws_list.focus()
        await pilot.pause(0.1)
        assert ws_list.has_focus

        # Right arrow moves IN to session list
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus

        # Left arrow moves OUT to workspace list
        await pilot.press("left")
        await pilot.pause(0.1)
        assert ws_list.has_focus

        # Right arrow on session_list in DELETE mode does not enter power_mode
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus
        await pilot.press("right")
        await pilot.pause(0.1)
        assert app.screen.__class__.__name__ == "DashboardScreen"

        # Cancel DELETE mode
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert d.mode == "NORMAL"

        # 2. ORGANIZE Mode (Step 1)
        await pilot.press("ctrl+m")
        await pilot.pause(0.2)
        assert d.mode == "ORGANIZE" and d.organize_step == 1
        ws_list.focus()
        await pilot.pause(0.1)
        assert ws_list.has_focus

        # Right arrow moves IN to session list
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus

        # Left arrow moves OUT to workspace list
        await pilot.press("left")
        await pilot.pause(0.1)
        assert ws_list.has_focus

        # Select a session with Space
        sess_list.focus()
        await pilot.press("space")
        await pilot.pause(0.1)
        assert len(d.selected_sessions) == 1

        # 3. ORGANIZE Mode (Step 2: Choose destination)
        await pilot.press("ctrl+m")
        await pilot.pause(0.2)
        assert d.organize_step == 2
        assert ws_list.has_focus

        # Right arrow moves IN to session list
        await pilot.press("right")
        await pilot.pause(0.1)
        assert sess_list.has_focus

        # Left arrow moves OUT to workspace list
        await pilot.press("left")
        await pilot.pause(0.1)
        assert ws_list.has_focus

        # Cancel ORGANIZE mode
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert d.mode == "NORMAL"


@pytest.mark.asyncio
async def test_settings_persistence(tmp_path):
    """Verify animations setting persists across app restarts."""
    import json
    db_file = str(tmp_path / "cyguide.db")
    settings_file = tmp_path / "settings.json"

    # 1. Initial app defaults animations to True
    app1 = CyGuideApp(db_path=db_file)
    assert app1.animations_enabled is True
    assert not settings_file.exists()

    # 2. Toggle animations to False
    app1.action_toggle_animations()
    assert app1.animations_enabled is False
    assert settings_file.exists()

    with open(settings_file, "r") as f:
        data = json.load(f)
    assert data.get("animations_enabled") is False

    # 3. New app instance with the same db_path loads animations_enabled as False
    app2 = CyGuideApp(db_path=db_file)
    assert app2.animations_enabled is False

    async with app2.run_test() as pilot:
        await pilot.pause(0.1)
        assert "no-animations" in app2.classes


@pytest.mark.asyncio
async def test_palette_theme_in_and_out_navigation():
    """Verify right arrow steps into Theme sub-palette and left arrow steps back with Theme highlighted."""
    from cyguide.app import CyGuideApp
    from textual.command import CommandList

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        # Open command palette
        await pilot.press("ctrl+p")
        await pilot.pause(0.2)
        cl = app.screen.query_one(CommandList)
        theme_idx = next(i for i, opt in enumerate(cl.options) if "Theme" in str(opt.prompt))
        cl.highlighted = theme_idx
        await pilot.pause(0.1)

        # Right arrow steps into Theme sub-palette
        await pilot.press("right")
        await pilot.pause(0.2)
        theme_palette = app.screen
        assert theme_palette.__class__.__name__ == "CyGuideCommandPalette"
        assert getattr(theme_palette, "is_sub_palette", False) is True

        # Left arrow in Theme sub-palette steps back to root palette
        await pilot.press("left")
        await pilot.pause(0.2)
        root_palette = app.screen
        assert root_palette.__class__.__name__ == "CyGuideCommandPalette"
        assert getattr(root_palette, "is_sub_palette", False) is False

        # Theme option should be preserved as highlighted
        root_cl = root_palette.query_one(CommandList)
        assert "Theme" in str(root_cl.get_option_at_index(root_cl.highlighted).prompt)

        # Left arrow in root palette closes it back to dashboard
        await pilot.press("left")
        await pilot.pause(0.2)
        assert app.screen.__class__.__name__ == "DashboardScreen"


@pytest.mark.asyncio
async def test_new_workspace_session_rename_dialog():
    """Verify creating a new workspace or session triggers RenameDialog with current time as default name."""
    import re
    from cyguide.ui.screens.home import RenameDialog

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        d = app.screen
        await pilot.pause(0.2)

        # 1. Trigger New Workspace (Ctrl+N) -> opens RenameDialog with default time
        await pilot.press("ctrl+n")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RenameDialog)
        ws_inp = app.screen.query_one("#rename_input")
        ws_default_time = ws_inp.value
        assert re.match(r"^\d{2}:\d{2}:\d{2}$", ws_default_time)

        # Accept default time
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, RenameDialog)
        workspaces = await app.store.list_workspaces()
        ws_names = [w["name"] for w in workspaces]
        assert ws_default_time in ws_names

        # 2. Trigger New Session (Ctrl+S) -> opens RenameDialog with default time
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RenameDialog)
        sess_inp = app.screen.query_one("#rename_input")
        sess_default_time = sess_inp.value
        assert re.match(r"^\d{2}:\d{2}:\d{2}$", sess_default_time)

        # Accept default time
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, RenameDialog)
        sessions = await app.store.list_sessions(d.selected_ws_id)
        sess_names = [s["name"] for s in sessions]
        assert sess_default_time in sess_names

        # 3. Custom name input
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RenameDialog)
        app.screen.query_one("#rename_input").value = "Custom Session Name"
        await pilot.press("enter")
        await pilot.pause(0.2)
        sessions2 = await app.store.list_sessions(d.selected_ws_id)
        sess2_names = [s["name"] for s in sessions2]
        assert "Custom Session Name" in sess2_names

        # 4. Cancel creation with Escape
        await pilot.press("ctrl+s")
        await pilot.pause(0.2)
        assert isinstance(app.screen, RenameDialog)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, RenameDialog)
        sessions3 = await app.store.list_sessions(d.selected_ws_id)
        assert len(sessions3) == len(sessions2)


@pytest.mark.asyncio
async def test_learning_sidebar_layout_and_wrapping():
    """Verify Learning Mode Plan A sidebar: unclipped run button, launchpad container, and wrapping preview."""
    from cyguide.app import CyGuideApp
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(120, 45)) as pilot:
        await app.push_screen("learning_mode")
        await pilot.pause()

        screen = app.screen
        pane = screen.query_one("#lesson_config_pane")
        rl = screen.query_one("#recipe_list")
        lp = screen.query_one("#launchpad_container")
        run_btn = screen.query_one("#run_btn")
        preview = screen.query_one("#command_preview")

        # 1. Verify layout hierarchy
        assert lp is not None
        assert run_btn is not None
        assert rl is not None

        # 2. Verify run button is unclipped (within the pane boundary)
        pane_bottom = pane.region.y + pane.region.height
        btn_bottom = run_btn.region.y + run_btn.region.height
        assert btn_bottom <= pane_bottom, f"Button bottom {btn_bottom} exceeds pane bottom {pane_bottom}"
        assert run_btn.region.height == 3

        # 3. Test recipe selection updates preview
        rl.index = 1
        await pilot.press("enter")
        await pilot.pause()
        assert "-Pn" in screen.query_one("#flags_input").value
        assert "-Pn" in str(preview.render())

        # 4. Test long command wrapping expands preview height
        initial_height = preview.size.height
        screen.query_one("#flags_input").value = "-sV -sC -A -T4 -p 1-65535 -oN scan.txt --script=vuln,default"
        await pilot.pause()
        assert preview.size.height >= initial_height
        assert "vuln" in str(preview.render())


@pytest.mark.asyncio
async def test_session_overview_hierarchy_and_formatting(tmp_path):
    """Verify session overview card hierarchy, schema formatting, and power mode launch."""
    import uuid
    from cyguide.schemas.network import NetworkHost, NetworkService
    from cyguide.schemas.netblock import NetworkNetblock

    db_path = str(tmp_path / f"test_overview_{uuid.uuid4().hex}.db")
    app = CyGuideApp(db_path=db_path)
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        dashboard = app.get_screen("dashboard")
        ws_id = await app.power_facade.create_workspace("OverviewWS")
        sess_id = await app.power_facade.create_session(ws_id, "ReconSession")

        # 1. Test empty state initially
        await dashboard.refresh_workspaces()
        await pilot.pause()
        await dashboard.show_session_details(sess_id, force=True)
        await pilot.pause()

        assert dashboard.query_one(".session_id_card") is not None
        assert dashboard.query_one(".session_metrics_grid") is not None
        assert dashboard.query_one(".session_graph_card") is not None
        assert dashboard.query_one(".entity_empty_notice") is not None

        # 2. Add findings and verify formatted entity rows without truncation
        await app.store.upsert_finding(sess_id, NetworkHost.create(ip="192.168.1.50"))
        await app.store.upsert_finding(sess_id, NetworkService.create(host_ip="192.168.1.50", port=80, protocol="tcp", service_name="http"))
        await app.store.upsert_finding(sess_id, NetworkNetblock.create(cidr="192.168.1.0/24"))

        await dashboard.show_session_details(sess_id, force=True)
        await pilot.pause()

        labels = [str(l.render()) for l in dashboard.query(".entity_stat_label")]
        assert any("Hosts" in l for l in labels)
        assert any("Services" in l for l in labels)
        assert any("Netblocks" in l for l in labels)
        # Verify canonical ordering: Hosts (device) -> Netblocks (ip range) -> Services
        hosts_idx = next(i for i, l in enumerate(labels) if "Hosts" in l)
        netblock_idx = next(i for i, l in enumerate(labels) if "Netblocks" in l)
        services_idx = next(i for i, l in enumerate(labels) if "Services" in l)
        assert hosts_idx < netblock_idx < services_idx

        # 3. Verify enter session button switches to power mode
        enter_btn = dashboard.query_one(".enter_session_btn")
        assert enter_btn is not None
        await pilot.click(".enter_session_btn")
        await pilot.pause()
        assert type(app.screen).__name__ == "PowerModeScreen"
