"""Tests for ResizeHandle and Power mode UI enhancements."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Static

from cyguide.schemas.power import JobStatus, JobStatusEnum
from cyguide.ui.screens.power import PowerModeScreen
from cyguide.ui.widgets.power import JobQueue
from cyguide.ui.widgets.resizer import ResizeHandle


class ResizerTestApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = {}

    def save_settings(self, updates):
        self.settings.update(updates)

    def compose(self) -> ComposeResult:
        with Horizontal(id="container"):
            with Vertical(id="left_pane"):
                pass
            yield ResizeHandle(
                target_id="left_pane",
                side="left",
                min_size=16,
                max_size=60,
                setting_key="left_width",
                id="left_resizer",
            )
            with Vertical(id="center_pane"):
                pass
            yield ResizeHandle(
                target_id="right_pane",
                side="right",
                min_size=20,
                max_size=50,
                setting_key="right_width",
                id="right_resizer",
            )
            with Vertical(id="right_pane"):
                pass


@pytest.mark.asyncio
async def test_resizer_handle_mouse_drag():
    app = ResizerTestApp()
    async with app.run_test():
        left_pane = app.query_one("#left_pane")
        left_pane.styles.width = 25
        left_resizer = app.query_one("#left_resizer", ResizeHandle)

        # Simulate MouseDown
        down_event = MouseDown(
            left_resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=25,
            screen_y=5,
        )
        left_resizer.on_mouse_down(down_event)
        assert left_resizer._dragging is True
        assert left_resizer.has_class("-dragging")
        assert left_pane.has_class("-resizing")

        # Simulate MouseMove (drag right by 10 columns)
        move_event = MouseMove(
            left_resizer,
            x=10,
            y=0,
            delta_x=10,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=35,
            screen_y=5,
        )
        left_resizer.on_mouse_move(move_event)
        assert int(left_pane.styles.width.value) == 35

        # Simulate MouseUp
        up_event = MouseUp(
            left_resizer,
            x=10,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=35,
            screen_y=5,
        )
        left_resizer.on_mouse_up(up_event)
        assert left_resizer._dragging is False
        assert not left_resizer.has_class("-dragging")
        assert not left_pane.has_class("-resizing")
        assert app.settings.get("left_width") == 35


@pytest.mark.asyncio
async def test_job_queue_renders_without_headers():
    class JobQueueApp(App):
        def compose(self) -> ComposeResult:
            yield JobQueue(id="test_job_queue")

    app = JobQueueApp()
    async with app.run_test() as pilot:
        jq = app.query_one("#test_job_queue", JobQueue)

        # Verify no "JOB QUEUE" Label widget is in JobQueue children
        labels = list(jq.query("Label"))
        assert len(labels) == 0

        # Feed some jobs
        s_id = uuid4()
        job1 = JobStatus(
            job_id=uuid4(),
            session_id=s_id,
            tool_name="nmap",
            status=JobStatusEnum.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        job2 = JobStatus(
            job_id=uuid4(),
            session_id=s_id,
            tool_name="gobuster",
            status=JobStatusEnum.DONE,
            started_at=datetime.now(timezone.utc),
        )

        await jq.update_jobs([job1, job2])
        await pilot.pause()

        job_list = jq.query_one("#power_job_list")
        # Ensure items exist and no Session header item was inserted
        assert len(job_list.children) == 2
        static0 = job_list.children[0].query_one(Static)
        assert "nmap" in str(static0.content)
        assert "◌" in str(static0.content)
        static1 = job_list.children[1].query_one(Static)
        assert "gobuster" in str(static1.content)
        assert "●" in str(static1.content)


def test_style_css_input_scrollbar_removal():
    import os

    css_path = os.path.join(os.path.dirname(__file__), "../../cyguide/ui/style.css")
    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify global Input scrollbar-size: 0 0
    assert "Input, CommandInput, .input" in content
    assert "scrollbar-size: 0 0;" in content
    # Verify ResizeHandle styling
    assert "ResizeHandle" in content
    assert "pointer: ew-resize;" in content


@pytest.mark.asyncio
async def test_power_mode_screen_composition():
    from cyguide.ui.screens.power import PowerModeScreen

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
    import uuid
    from unittest.mock import MagicMock

    from textual.widgets import RichLog, TabbedContent

    from cyguide.engine.power_facade import PowerWorkspaceFacade
    from cyguide.engine.store import GraphStore
    from cyguide.schemas.power import ActionRequest, ActionSource
    from cyguide.ui.screens.power import PowerModeScreen

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
    facade._active_jobs[job_id] = job
    facade._job_buffers[job_id] = ["Listening on 0.0.0.0 4444...\n"]
    facade._job_actions[job_id] = ActionRequest(
        action_id=job_id,
        session_id=uuid.UUID(sess_id),
        tool_name="ncat",
        params={"raw_flags": "-lvnp 4444"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True,
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


@pytest.mark.asyncio
async def test_job_queue_concurrent_updates_no_duplicate_ids():
    class JobQueueApp(App):
        def compose(self) -> ComposeResult:
            yield JobQueue(id="test_job_queue")

    app = JobQueueApp()
    async with app.run_test() as pilot:
        jq = app.query_one("#test_job_queue", JobQueue)
        s_id = uuid4()
        j1 = uuid4()
        j2 = uuid4()
        job1 = JobStatus(
            job_id=j1,
            session_id=s_id,
            tool_name="nmap",
            status=JobStatusEnum.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        job2 = JobStatus(
            job_id=j2,
            session_id=s_id,
            tool_name="whois",
            status=JobStatusEnum.DONE,
            started_at=datetime.now(timezone.utc),
        )

        # Initial populate
        await jq.update_jobs([job1])
        await pilot.pause()

        # Fire concurrent update_jobs calls with differing order to simulate rapid state transitions
        await asyncio.gather(
            jq.update_jobs([job1, job2]),
            jq.update_jobs([job2, job1]),
            jq.update_jobs([job1]),
        )
        await pilot.pause()

        job_list = jq.query_one("#power_job_list")
        assert len(job_list.children) >= 1


@pytest.mark.asyncio
async def test_job_queue_handles_duplicate_job_ids_in_input():
    class JobQueueApp(App):
        def compose(self) -> ComposeResult:
            yield JobQueue(id="test_job_queue")

    app = JobQueueApp()
    async with app.run_test() as pilot:
        jq = app.query_one("#test_job_queue", JobQueue)
        s_id = uuid4()
        j1 = uuid4()
        job1 = JobStatus(
            job_id=j1,
            session_id=s_id,
            tool_name="nmap",
            status=JobStatusEnum.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        # Duplicate job in single input list must not raise DuplicateIds
        await jq.update_jobs([job1, job1])
        await pilot.pause()

        job_list = jq.query_one("#power_job_list")
        assert len(job_list.children) == 1


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
    from cyguide.ui.widgets.power import CommandPalette

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
    from unittest.mock import PropertyMock

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
    from unittest.mock import AsyncMock

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
    from cyguide.ui.widgets.power import CommandPalette

    palette = CommandPalette()
    mock_input = MagicMock()
    palette.query_one = MagicMock(return_value=mock_input)

    # 1. Multiple redundant prefixes like "> > whois ..." collapsed
    event = MagicMock()
    event.value = "> > whois 104.20.23.154"
    event.input = mock_input
    palette.on_input_changed(event)
    assert mock_input.value == "> whois 104.20.23.154"

    # 2. In shell locked mode, redundant collapsed to "! "
    palette.shell_locked = True
    event.value = "! ! ls -la"
    palette.on_input_changed(event)
    assert mock_input.value == "! ls -la"


def test_command_palette_submission_strips_duplicate_prefixes():
    from cyguide.ui.widgets.power import CommandPalette

    palette = CommandPalette()
    palette.shell_locked = True
    mock_input = MagicMock()

    posted = []
    palette.post_message = lambda msg: posted.append(msg)

    # User submitted "> > whois 104.20.23.154"
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
    import json
    from cyguide.ui.widgets.power import EntityBrowser

    browser = EntityBrowser()
    nodes = []
    for i in range(250):
        nodes.append({
            "id": f"dns_{i}",
            "schema_type": "dns.record",
            "pik_json": json.dumps({"domain": f"sub{i}.example.com", "type": "A"}),
            "data_json": "{}",
            "status": "confirmed",
        })

    await browser.refresh_entities({"nodes": nodes, "edges": []})
    assert len(browser.root.children) == 1
    dns_root = browser.root.children[0]
    assert "Domains & DNS (250)" in str(dns_root.label)
    # Capped at 200 visible children + 1 informative leaf note
    assert len(dns_root.children) == 201
    assert "… 50 more (filter with search)" in str(dns_root.children[-1].label)


@pytest.mark.asyncio
async def test_power_mode_live_update_debouncing():
    from unittest.mock import AsyncMock, PropertyMock

    screen = PowerModeScreen()
    screen.active_session_id = "test-session"
    mock_app = MagicMock()
    mock_facade = MagicMock()
    mock_facade.get_graph_snapshot = AsyncMock(return_value={"nodes": [], "edges": []})
    mock_app.power_facade = mock_facade

    with patch.object(PowerModeScreen, "app", new_callable=PropertyMock) as mock_prop:
        mock_prop.return_value = mock_app
        # Rapidly fire 20 live update events
        for _ in range(20):
            await screen.handle_live_update("test-session", MagicMock())

        # Only one debounced task was created
        assert screen._live_update_task is not None
        assert not screen._live_update_task.done()

        # Let debounced task execute
        await screen._live_update_task
        mock_facade.get_graph_snapshot.assert_called_once_with("test-session")
