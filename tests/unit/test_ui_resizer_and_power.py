"""Tests for ResizeHandle and Power mode UI enhancements."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Static

from cyguide.ui.widgets.resizer import ResizeHandle
from cyguide.ui.widgets.power import JobQueue
from cyguide.schemas.power import JobStatus, JobStatusEnum


class ResizerTestApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = {}

    def _save_settings(self, updates):
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
        assert "◯" in str(static0.content)
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
