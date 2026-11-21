"""Unit tests for ResizeHandle widget and split layout drag behavior."""

import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, MouseMove, MouseUp

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

        # Simulate duplicate MouseMove at same coordinate (deadband filtering)
        left_resizer.on_mouse_move(move_event)
        assert left_resizer._current_width == 35
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
