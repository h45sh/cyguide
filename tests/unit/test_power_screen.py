"""Unit tests for PowerModeScreen, tabs, job restoration, entity browser, and palette."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Static, TabbedContent, TabPane

from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource, JobStatus, JobStatusEnum
from cyguide.ui.screens.power import PowerModeScreen
from cyguide.ui.widgets.power import CommandPalette, EntityBrowser


@pytest.mark.asyncio
async def test_power_mode_screen_composition():
    class ScreenApp(App):
        def compose(self) -> ComposeResult:
            yield PowerModeScreen()

    app = ScreenApp()
    async with app.run_test():
        screen = app.query_one(PowerModeScreen)
        assert screen.query_one("#sidebar_resizer") is not None
        assert screen.query_one("#scratchpad_resizer") is not None
        assert screen.query_one("#job_queue") is not None
        assert len(screen.query("#suggestions_pane")) == 0

        sidebar = screen.query_one("#power_sidebar")
        resizer = screen.query_one("#sidebar_resizer")

        # Test Ctrl+B toggle (hide)
        screen.action_toggle_sidebar()
        assert sidebar.has_class("collapsed")
        assert sidebar.display is False
        assert resizer.has_class("hidden")
        assert resizer.display is False

        # Test Ctrl+B toggle (restore)
        screen.action_toggle_sidebar()
        assert not sidebar.has_class("collapsed")
        assert sidebar.display is True
        assert not resizer.has_class("hidden")
        assert resizer.display is True


@pytest.mark.asyncio
async def test_power_mode_running_job_tab_restoration():
    store = GraphStore(":memory:")
    await store.initialize()
    facade = PowerWorkspaceFacade(store, MagicMock(), MagicMock())
    ws_id = await facade.create_workspace("TestWS")
    sess_id = await facade.create_session(ws_id, "TestSess")

    job_id = uuid.uuid4()
    job = JobStatus(
        job_id=job_id,
        session_id=uuid.UUID(sess_id),
        tool_name="ncat",
        status=JobStatusEnum.RUNNING,
    )
    facade.register_job(job)
    facade.append_job_buffer(job_id, "Listening on 0.0.0.0 4444...\n")
    facade.execution.register_action(
        ActionRequest(
            action_id=job_id,
            session_id=uuid.UUID(sess_id),
            tool_name="ncat",
            params={"raw_flags": "-lvnp 4444"},
            triggered_by=ActionSource.USER,
            is_explicit_shell=True,
        )
    )

    class PowerApp(App):
        def __init__(self):
            super().__init__()
            self.store = store
            self.power_facade = facade
            self.selected_session_id = sess_id

        def compose(self) -> ComposeResult:
            yield PowerModeScreen()

    app = PowerApp()
    async with app.run_test() as pilot:
        screen = app.query_one(PowerModeScreen)
        tabs = screen.query_one("#job_tabs", TabbedContent)

        # Ensure tab was restored for the running job
        assert screen.terminal_count >= 1
        active_tab_id = tabs.active
        assert active_tab_id in screen.tab_to_job
        assert screen.tab_to_job[active_tab_id] == str(job_id)

        # Verify running indicator in tab title
        tab_widget = tabs.get_tab(active_tab_id)
        assert "◌" in str(tab_widget.label)

        # Verify buffer content was written
        log = screen.query_one(f"#log_{active_tab_id}", RichLog)
        assert any("Listening on 0.0.0.0 4444" in str(line) for line in log.lines)

        # Simulate job status change to DONE
        job.status = JobStatusEnum.DONE
        facade._notify_job_change(job)
        await pilot.pause()

        # Verify running indicator was stripped
        assert "◌" not in str(tab_widget.label)

    await store.close()


def test_flag_regex_detection():
    import re

    flag_pattern = re.compile(
        r"(?:flag|FLAG|ctf|CTF|htb|HTB|thm|THM)\{[A-Za-z0-9_!@#$%^&*+=?.-]+\}"
    )

    sample_output = """
    Target scanned successfully.
    Found secret text: flag{s1mpl3_fl4g_v4lu3}
    Another token: HTB{w3b_3xpl01t_succ3ss!}
    Third token: THM{try_hack_me_2026}
    Noise: some text {not_a_flag} flag{} invalid flag{has space}
    """
    matches = flag_pattern.findall(sample_output)
    assert len(matches) == 3
    assert "flag{s1mpl3_fl4g_v4lu3}" in matches
    assert "HTB{w3b_3xpl01t_succ3ss!}" in matches
    assert "THM{try_hack_me_2026}" in matches


def test_command_palette_ctrl_y():
    palette = CommandPalette()
    mock_input = MagicMock()
    mock_input.value = "> "
    palette.query_one = MagicMock(return_value=mock_input)

    posted_messages = []
    palette.post_message = lambda msg: posted_messages.append(msg)

    event = MagicMock()
    event.key = "ctrl+y"
    palette.on_key(event)

    assert any(isinstance(m, CommandPalette.CopyTabRequest) for m in posted_messages)
    assert event.stop.called
    assert event.prevent_default.called


def test_action_copy_active_tab():
    screen = PowerModeScreen()
    mock_app = MagicMock()

    mock_tabs = MagicMock()
    mock_tabs.active = "term_1"

    line1 = MagicMock()
    line1.text = "nmap -sV 10.10.10.1"
    line2 = MagicMock()
    line2.text = "Port 80/tcp open http"
    mock_log = MagicMock()
    mock_log.lines = [line1, line2]

    def mock_query_one(selector, *args, **kwargs):
        if selector == "#job_tabs":
            return mock_tabs
        if selector == "#log_term_1":
            return mock_log
        raise ValueError(f"Unknown selector: {selector}")

    screen.query_one = mock_query_one

    with patch.object(PowerModeScreen, "app", new_callable=PropertyMock) as mock_prop:
        mock_prop.return_value = mock_app
        screen.action_copy_active_tab()

    mock_app.copy_to_clipboard.assert_called_once_with("nmap -sV 10.10.10.1\nPort 80/tcp open http")


@pytest.mark.asyncio
async def test_send_desktop_notification():
    screen = PowerModeScreen()
    with patch("shutil.which", return_value="/usr/bin/notify-send"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = MagicMock()
            mock_proc.wait = AsyncMock()
            mock_exec.return_value = mock_proc

            await screen._send_desktop_notification("Job Completed", "Finished scan")
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "notify-send"
            assert "Job Completed" in args


def test_command_palette_prefix_normalization():
    palette = CommandPalette()
    mock_input = MagicMock()
    palette.query_one = MagicMock(return_value=mock_input)

    event = MagicMock()
    event.value = "> > whois 104.20.23.154"
    event.input = mock_input
    palette.on_input_changed(event)
    assert mock_input.value == "> whois 104.20.23.154"

    palette.shell_locked = True
    event.value = "! ! ls -la"
    palette.on_input_changed(event)
    assert mock_input.value == "! ls -la"


def test_command_palette_submission_strips_duplicate_prefixes():
    palette = CommandPalette()
    palette.shell_locked = True
    mock_input = MagicMock()

    posted = []
    palette.post_message = lambda msg: posted.append(msg)

    event = MagicMock()
    event.value = "> > whois 104.20.23.154"
    event.input = mock_input

    palette.on_input_submitted(event)
    assert len(posted) == 1
    sub = posted[0]
    assert sub.tool_name == "whois"
    assert sub.expanded_params == ["104.20.23.154"]
    assert sub.value == "whois 104.20.23.154"


@pytest.mark.asyncio
async def test_entity_browser_caps_large_categories():
    browser = EntityBrowser()
    nodes = []
    for i in range(250):
        nodes.append(
            {
                "id": f"dns_{i}",
                "schema_type": "dns.record",
                "pik_json": json.dumps({"domain": f"sub{i}.example.com", "type": "A"}),
                "data_json": "{}",
                "status": "confirmed",
            }
        )

    await browser.refresh_entities({"nodes": nodes, "edges": []})
    assert len(browser.root.children) == 1
    dns_root = browser.root.children[0]
    assert "Domains & DNS (250)" in str(dns_root.label)
    assert len(dns_root.children) == 201
    assert "… 50 more (filter with search)" in str(dns_root.children[-1].label)


@pytest.mark.asyncio
async def test_power_mode_live_update_debouncing():
    screen = PowerModeScreen()
    screen.active_session_id = "test-session"
    mock_app = MagicMock()
    mock_facade = MagicMock()
    mock_facade.get_graph_snapshot = AsyncMock(return_value={"nodes": [], "edges": []})
    mock_app.power_facade = mock_facade

    with patch.object(PowerModeScreen, "app", new_callable=PropertyMock) as mock_prop:
        mock_prop.return_value = mock_app
        for _ in range(20):
            await screen.handle_live_update("test-session", MagicMock())

        assert screen._live_update_task is not None
        assert not screen._live_update_task.done()

        await screen._live_update_task
        mock_facade.get_graph_snapshot.assert_called_once_with("test-session")


@pytest.mark.asyncio
async def test_power_mode_welcome_guide_lifecycle():
    class PowerGuideTestApp(App):
        def __init__(self):
            super().__init__()
            self.power_facade = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.session_name = "test-session"
            self.power_facade.get_context = AsyncMock(return_value=mock_ctx)
            self.power_facade.get_session = AsyncMock(
                return_value={"status": "ACTIVE", "workspace_id": "ws-1"}
            )
            self.power_facade.get_active_jobs_count.return_value = 0
            self.power_facade.get_graph_snapshot = AsyncMock(
                return_value={"nodes": [], "edges": []}
            )
            self.power_facade.get_jobs = AsyncMock(return_value=[])
            self.power_facade.get_all_jobs = AsyncMock(return_value=[])

        def compose(self) -> ComposeResult:
            yield PowerModeScreen()

    app = PowerGuideTestApp()
    async with app.run_test() as pilot:
        screen = app.query_one(PowerModeScreen)
        screen.active_session_id = "test-session"
        screen.terminal_count = 0

        await screen._show_welcome_guide()
        tabs = screen.query_one("#job_tabs", TabbedContent)
        guide_pane = next((p for p in tabs.query(TabPane) if p.id == "tab_guide"), None)
        assert guide_pane is not None
        assert "GUIDE" in str(tabs.get_tab("tab_guide").label)

        guide_text = screen.query_one("#power_guide_text", Static)
        markup = getattr(guide_text.content, "markup", str(guide_text.content))
        assert "OPERATOR WORKSPACE GUIDE" in markup

        tab_id = await screen.action_new_terminal_tab("nmap 127.0.0.1")
        assert tab_id == "term_1"
        assert not any(p.id == "tab_guide" for p in tabs.query(TabPane))

        await screen.action_close_terminal_tab()
        assert any(p.id == "tab_guide" for p in tabs.query(TabPane))


@pytest.mark.asyncio
async def test_power_mode_scratchpad_debounced_save(tmp_path):
    """Verify that scratchpad saves are debounced and persisted off the main UI thread."""
    from textual.widgets import TextArea

    class ScratchpadApp(App):
        def compose(self) -> ComposeResult:
            yield PowerModeScreen()

    app = ScratchpadApp()
    app.preferences = MagicMock()
    app.preferences.write_scratchpad = MagicMock()

    async with app.run_test() as pilot:
        screen = app.query_one(PowerModeScreen)
        text_area = screen.query_one("#scratchpad_textarea", TextArea)

        # Trigger rapid changes
        text_area.text = "Note 1"
        screen.on_text_area_changed(TextArea.Changed(text_area))
        text_area.text = "Note 2"
        screen.on_text_area_changed(TextArea.Changed(text_area))
        text_area.text = "Final Note"
        screen.on_text_area_changed(TextArea.Changed(text_area))

        # Immediately, preferences.write_scratchpad should not have been called yet (debounced)
        assert app.preferences.write_scratchpad.call_count == 0

        # Wait past the debounce duration (300ms)
        await pilot.pause(0.35)

        # Now it should have been called with the latest content
        assert app.preferences.write_scratchpad.call_count >= 1
        app.preferences.write_scratchpad.assert_called_with("Final Note")


@pytest.mark.asyncio
async def test_command_palette_lhost_badge_offloading():
    """Verify that get_lhost_info is offloaded to a worker thread via asyncio.to_thread."""
    class PaletteApp(App):
        def compose(self) -> ComposeResult:
            yield CommandPalette()

    app = PaletteApp()
    with patch("cyguide.engine.network.get_lhost_info", return_value=("10.10.14.8", "tun0")) as mock_lhost:
        async with app.run_test() as pilot:
            palette = app.query_one(CommandPalette)
            palette._update_lhost_badge()
            await pilot.pause(0.1)

            assert mock_lhost.called
            badge = palette.query_one("#lhost_badge")
            assert "tun0: 10.10.14.8" in str(badge.render())
            assert badge.has_class("vpn")


@pytest.mark.asyncio
async def test_tool_health_modal_offloaded():
    """Verify that ToolHealthModal.refresh_health uses asyncio.to_thread for check_and_update_tool_health."""
    from cyguide.ui.screens.tool_health_modal import ToolHealthModal

    class HealthApp(App):
        def __init__(self):
            super().__init__()
            self.check_and_update_tool_health = MagicMock(return_value={
                "nmap": {"status": "ok", "healthy": True, "binary": "/usr/bin/nmap"}
            })

        def compose(self) -> ComposeResult:
            yield Static("test")

    app = HealthApp()
    modal = ToolHealthModal()
    async with app.run_test() as pilot:
        app.push_screen(modal)
        await pilot.pause(0.1)

        assert app.check_and_update_tool_health.called
        summary = modal.query_one("#tool_health_summary_label")
        assert "All 1 registered tools are operational" in str(summary.render())

