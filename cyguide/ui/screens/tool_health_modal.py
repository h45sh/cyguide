"""Modal dialog for viewing system and security tool health status."""

from typing import Any

from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static


class ToolHealthModal(ModalScreen[None]):
    """Modal dialog displaying comprehensive tool health and diagnostics."""

    BINDINGS = [
        ("escape", "dismiss_modal", "Close"),
        ("q", "dismiss_modal", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="tool_health_card"):
            with Horizontal(id="tool_health_header_row"):
                yield Label("◆ TOOL HEALTH", id="tool_health_header_title")
                yield Label("← Left: Back", id="tool_health_nav_hint")

            yield Label("", id="tool_health_summary_label")

            with Vertical(id="tool_health_list_container"):
                yield ListView(id="tool_health_items")

            with Horizontal(classes="dialog_buttons"):
                yield Button("Close [Esc]", variant="primary", id="close_btn")

    def on_mount(self) -> None:
        self.refresh_health()

        def focus_items():
            try:
                items = self.query_one("#tool_health_items", ListView)
                items.focus()
                if items.children:
                    items.index = 0
            except Exception:
                pass

        self.call_after_refresh(focus_items)

    def on_key(self, event: events.Key) -> None:
        if event.key == "left":
            event.stop()
            self.dismiss()
            self.app.last_palette_highlight = "Tool Health"
            self.app.action_command_palette(preserve_highlight=True)
        elif event.key == "right":
            event.stop()
            try:
                items = self.query_one("#tool_health_items", ListView)
                close_btn = self.query_one("#close_btn", Button)
                if items.has_focus:
                    close_btn.focus()
                else:
                    items.focus()
            except Exception:
                pass
        elif event.key == "escape":
            event.stop()
            self.dismiss()

    async def on_tool_health_changed(self, event: Any) -> None:
        """Handle real-time tool health changes broadcast while modal is open."""
        await self.apply_health(event.health)

    async def on_cy_guide_app_tool_health_changed(self, event: Any) -> None:
        """Fallback handler for nested event class names."""
        await self.apply_health(event.health)

    @work(exclusive=True, group="tool_health_modal")
    async def refresh_health(self) -> None:
        health = self.app.check_and_update_tool_health()
        await self.apply_health(health)

    async def apply_health(self, health: dict) -> None:
        try:
            summary_label = self.query_one("#tool_health_summary_label", Label)
            item_list = self.query_one("#tool_health_items", ListView)
        except Exception:
            return

        total = len(health)
        issues = [info for info in health.values() if not info.get("healthy", False)]

        if not issues:
            summary_label.update(f"● All {total} registered tools are operational and available.")
            summary_label.set_class(True, "summary_green")
            summary_label.set_class(False, "summary_red")
        else:
            summary_label.update(
                f"▲ {len(issues)} issue(s) detected across {total} registered tools."
            )
            summary_label.set_class(True, "summary_red")
            summary_label.set_class(False, "summary_green")

        await item_list.clear()

        for name, info in sorted(health.items()):
            if info.get("status") == "ok":
                status_glyph = "● Ready"
                desc = info.get("binary") or "PATH"
                classes = "tool_status_row status_ok"
            elif info.get("status") == "missing":
                status_glyph = "× Missing"
                desc = info.get("hint") or "Not installed"
                classes = "tool_status_row status_missing"
            else:
                status_glyph = "▲ Error"
                desc = info.get("message", "Error")
                classes = "tool_status_row status_error"

            content = f"{name:<12} {status_glyph:<12} {desc}"
            item_list.append(ListItem(Static(content, classes=classes)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss()

    def action_dismiss_modal(self) -> None:
        self.dismiss()
