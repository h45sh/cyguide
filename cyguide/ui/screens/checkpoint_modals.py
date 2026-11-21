"""Modal dialogs for saving and loading Learning Mode laboratory checkpoints (.cyglab)."""

from __future__ import annotations

from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView

from cyguide.engine.learning import LearningSession


class SaveCheckpointModal(ModalScreen[Optional[str]]):
    """Modal dialog prompting the student for a checkpoint file name."""

    DEFAULT_CSS = """
    SaveCheckpointModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    """

    BINDINGS = [
        ("escape", "dismiss_modal", "Cancel"),
    ]

    def __init__(
        self,
        default_name: str = "",
        tool_name: str = "",
        target: str = "",
        tools_used: Optional[List[str]] = None,
        findings_count: int = 0,
    ):
        super().__init__()
        self.default_name = default_name
        self.tool_name = tool_name
        self.target = target
        self.tools_used = tools_used or (
            [tool_name] if tool_name and tool_name != "learning" else []
        )
        self.findings_count = findings_count

    def compose(self) -> ComposeResult:
        with Vertical(id="checkpoint_modal_card", classes="checkpoint_save_card"):
            with Horizontal(id="checkpoint_modal_header"):
                yield Label("◆ SAVE LAB CHECKPOINT", id="checkpoint_modal_title")
                yield Label("Esc: Cancel", id="checkpoint_modal_hint")

            target_display = self.target if self.target else "Universal Target"
            badge_text = (
                f"◆ LAB ({len(self.tools_used)} TOOLS)"
                if len(self.tools_used) > 1
                else (f"◆ {self.tools_used[0].upper()}" if self.tools_used else "◆ LAB")
            )
            with Horizontal(id="checkpoint_modal_meta_row"):
                yield Label(
                    badge_text,
                    classes="checkpoint_tool_badge",
                    markup=False,
                )
                yield Label(
                    f"Target: [bold #38bdf8]{target_display}[/bold #38bdf8]",
                    id="checkpoint_modal_meta_target",
                )
                if self.tools_used and len(self.tools_used) > 1:
                    tools_str = ", ".join(self.tools_used)
                    yield Label(
                        f"Tools: [bold #a78bfa]{tools_str}[/bold #a78bfa]",
                        id="checkpoint_modal_meta_tools",
                    )
                if self.findings_count > 0:
                    yield Label(
                        f"Findings: [bold #34d399]{self.findings_count}[/bold #34d399]",
                        id="checkpoint_modal_meta_findings",
                    )
                yield Label("🔒 0o600 Private", classes="checkpoint_sec_badge")

            yield Label(
                "Serializes terminal stdout, multi-tool graph findings, AI tutor dialogue, and lab notes into a universal .cyglab archive.",
                id="checkpoint_modal_desc",
            )

            yield Label("Checkpoint File Name:", classes="checkpoint_input_label")
            yield Input(
                value=self.default_name,
                placeholder="e.g. nmap_lab_portscan",
                id="checkpoint_name_input",
            )

            with Horizontal(classes="dialog_buttons"):
                yield Button("Cancel [Esc]", id="checkpoint_cancel_btn")
                yield Button("💾 Save Checkpoint", variant="primary", id="checkpoint_confirm_btn")

    def on_mount(self) -> None:
        def focus_input():
            try:
                inp = self.query_one("#checkpoint_name_input", Input)
                inp.focus()
            except Exception:
                pass

        self.call_after_refresh(focus_input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "checkpoint_name_input":
            self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "checkpoint_confirm_btn":
            self._submit()
        elif event.button.id == "checkpoint_cancel_btn":
            self.dismiss(None)

    def _submit(self) -> None:
        try:
            val = self.query_one("#checkpoint_name_input", Input).value.strip()
            if not val:
                val = self.default_name
            # sanitize filename
            import re

            clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", val)
            if not clean_name.endswith(".cyglab"):
                clean_name += ".cyglab"
            self.dismiss(clean_name)
        except Exception:
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class LoadCheckpointModal(ModalScreen[Optional[str]]):
    """Modal dialog displaying available .cyglab checkpoints to restore."""

    DEFAULT_CSS = """
    LoadCheckpointModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    """

    BINDINGS = [
        ("escape", "dismiss_modal", "Cancel"),
    ]

    def __init__(self, checkpoints_dir: str):
        super().__init__()
        self.checkpoints_dir = checkpoints_dir
        self.checkpoints: List[dict] = LearningSession.list_checkpoints(self.checkpoints_dir)

    def _build_list_items(self) -> List[ListItem]:
        if not self.checkpoints:
            return [
                ListItem(
                    Vertical(
                        Label("📂 No Saved Checkpoints", classes="checkpoint_empty_title"),
                        Label(
                            f"No .cyglab archives found in {self.checkpoints_dir}\nUse 'Save Lab' (^s) in Learning Mode to snapshot your session.",
                            classes="checkpoint_empty_label",
                        ),
                        classes="checkpoint_empty_container",
                    )
                )
            ]

        items = []
        for item in self.checkpoints:
            size_kb = round(item.get("size_bytes", 0) / 1024, 1)
            size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb / 1024, 2)} MB"
            target = item.get("target") or "No target"
            saved_time = item.get("saved_at", "")[:19].replace("T", " ")
            if not saved_time and item.get("mtime"):
                from datetime import datetime, timezone

                saved_time = datetime.fromtimestamp(item["mtime"], tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            tools_used = item.get("tools_used") or []
            if not tools_used and item.get("tool_name") and item.get("tool_name") != "lab":
                tools_used = [item.get("tool_name")]

            tool_badge_text = (
                "MULTI-TOOL"
                if len(tools_used) > 1
                else (tools_used[0].upper() if tools_used else "LAB")
            )
            nodes_count = item.get("nodes_count", 0)
            log_count = item.get("log_count", 0)
            flags = item.get("flags", "")
            notes_prev = item.get("notes_preview", "")

            meta_items = [f"[dim #64748b]Target:[/] [bold #e2e8f0]{target}[/]"]
            if tools_used:
                tools_str = ", ".join(tools_used)
                meta_items.append(f"[dim #64748b]Tools:[/] [bold #38bdf8]{tools_str}[/]")
            elif flags:
                meta_items.append(f"[dim #64748b]Flags:[/] [#c5a059]{flags}[/]")
            if nodes_count > 0:
                meta_items.append(f"[dim #64748b]Findings:[/] [bold #a78bfa]{nodes_count}[/]")
            if log_count > 0:
                meta_items.append(f"[dim #64748b]Logs:[/] [bold #34d399]{log_count}[/]")
            meta_line = "   ".join(meta_items)

            row_widgets = [
                Horizontal(
                    Label(f"◆ {tool_badge_text}", classes="checkpoint_tool_badge", markup=False),
                    Label(f"{item['filename']}", classes="checkpoint_filename"),
                    Label(size_str, classes="checkpoint_filesize"),
                    Label(saved_time, classes="checkpoint_filedate"),
                    classes="checkpoint_item_row1",
                ),
                Label(meta_line, classes="checkpoint_item_meta"),
            ]
            if notes_prev:
                notes_clean = " ".join(notes_prev.split())
                if len(notes_clean) > 75:
                    notes_clean = notes_clean[:72] + "..."
                row_widgets.append(
                    Label(
                        f"[dim #64748b]Notes:[/] [italic #94a3b8]{notes_clean}[/]",
                        classes="checkpoint_item_notes",
                    )
                )

            list_item = ListItem(Vertical(*row_widgets, classes="checkpoint_item_content"))
            items.append(list_item)
        return items

    def compose(self) -> ComposeResult:
        with Vertical(id="checkpoint_modal_card", classes="checkpoint_load_card"):
            with Horizontal(id="checkpoint_modal_header"):
                yield Label("◆ LOAD LAB CHECKPOINT", id="checkpoint_modal_title")
                yield Label("Esc: Cancel", id="checkpoint_modal_hint")

            yield Label(
                "Select a saved checkpoint to restore terminal stdout, graph findings, AI tutor dialogue, and lab notes.",
                id="checkpoint_modal_desc",
            )

            with Horizontal(id="checkpoint_list_subbar"):
                yield Label(
                    f"Saved Checkpoints ({len(self.checkpoints)})",
                    classes="checkpoint_subheading",
                )
                yield Label(
                    "↑/↓: Navigate • Enter: Load",
                    classes="checkpoint_nav_hint",
                )

            with Vertical(id="checkpoint_list_container"):
                yield ListView(*self._build_list_items(), id="checkpoint_list_view")

            with Horizontal(classes="dialog_buttons"):
                yield Button("Cancel [Esc]", id="checkpoint_load_cancel_btn")
                yield Button(
                    "📂 Load Selected", variant="primary", id="checkpoint_load_confirm_btn"
                )

    def on_mount(self) -> None:
        def focus_list():
            try:
                list_view = self.query_one("#checkpoint_list_view", ListView)
                list_view.focus()
                if list_view.children:
                    list_view.index = 0
            except Exception:
                pass

        self.call_after_refresh(focus_list)

    def refresh_list(self) -> None:
        try:
            list_view = self.query_one("#checkpoint_list_view", ListView)
        except Exception:
            return
        list_view.clear()
        self.checkpoints = LearningSession.list_checkpoints(self.checkpoints_dir)
        for it in self._build_list_items():
            list_view.append(it)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._confirm_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "checkpoint_load_confirm_btn":
            self._confirm_selected()
        elif event.button.id == "checkpoint_load_cancel_btn":
            self.dismiss(None)

    def _confirm_selected(self) -> None:
        try:
            list_view = self.query_one("#checkpoint_list_view", ListView)
            if list_view.index is not None and 0 <= list_view.index < len(self.checkpoints):
                selected = self.checkpoints[list_view.index]
                self.dismiss(selected["path"])
            else:
                self.dismiss(None)
        except Exception:
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
