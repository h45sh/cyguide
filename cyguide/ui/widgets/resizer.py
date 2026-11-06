"""Interactive edge resizer widget for split panes."""

from typing import Optional
from rich.text import Text
from textual import events
from textual.widget import Widget


class ResizeHandle(Widget):
    """A vertical edge handle that can be clicked or dragged to resize an adjacent pane."""

    DEFAULT_CSS = """
    ResizeHandle {
        width: 1;
        height: 100%;
        background: transparent;
        color: #334155;
        content-align: center middle;
        pointer: ew-resize;
    }
    ResizeHandle:hover {
        background: #181b22;
        color: #38bdf8;
    }
    ResizeHandle.-dragging {
        background: #0284c7;
        color: #ffffff;
    }
    """

    def __init__(
        self,
        target_id: str,
        side: str = "left",
        min_size: int = 16,
        max_size: int = 70,
        setting_key: Optional[str] = None,
        char: str = "│",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.target_id = target_id
        self.side = side  # 'left' (target is left of handle) or 'right' (target is right of handle)
        self.min_size = min_size
        self.max_size = max_size
        self.setting_key = setting_key
        self.char = char
        self._dragging: bool = False
        self._start_x: int = 0
        self._start_width: int = 0

    def render(self) -> Text:
        return Text(self.char, style="bold")

    def _get_target_widget(self) -> Optional[Widget]:
        try:
            return self.screen.query_one(f"#{self.target_id}")
        except Exception:
            return None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        target = self._get_target_widget()
        if not target:
            return

        self._dragging = True
        self.capture_mouse()
        self.add_class("-dragging")
        target.add_class("-resizing")

        self._start_x = event.screen_x
        try:
            if target.styles.width and target.styles.width.value is not None:
                self._start_width = int(target.styles.width.value)
            elif target.region.width > 0:
                self._start_width = int(target.region.width)
            else:
                self._start_width = self.min_size
        except Exception:
            self._start_width = self.min_size

        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        target = self._get_target_widget()
        if not target:
            return

        delta_x = event.screen_x - self._start_x
        if self.side == "left":
            new_width = self._start_width + delta_x
        else:  # right
            new_width = self._start_width - delta_x

        try:
            screen_width = self.screen.size.width
            max_limit = min(self.max_size, max(self.min_size + 10, screen_width - 35))
        except Exception:
            max_limit = self.max_size

        new_width = max(self.min_size, min(new_width, max_limit))
        target.styles.width = new_width
        self.screen.refresh(layout=True)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.release_mouse()
        self.remove_class("-dragging")

        target = self._get_target_widget()
        if target:
            target.remove_class("-resizing")
            try:
                final_width = int(target.styles.width.value)
            except Exception:
                final_width = int(target.region.width) if target.region.width > 0 else self.min_size

            if self.setting_key and hasattr(self.app, "_save_settings"):
                self.app._save_settings({self.setting_key: final_width})
        event.stop()
