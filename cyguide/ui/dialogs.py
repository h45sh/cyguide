"""Reusable modal dialogs for CyGuide screens."""

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown

SHORTCUTS_MD = """
# CyGuide Keyboard Shortcuts & Hotkeys

## Global & Help
* **`F1` / `Ctrl+/`**: Show this Keyboard Shortcuts & Hotkeys Help dialog
* **`Ctrl+P`**: Open Command Palette (e.g. Toggle Animations)
* **`Q` / `Ctrl+Q`**: Quit Application

## Dashboard (Engagement Management)
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+N`**: New Workspace
* **`Ctrl+S`**: New Session
* **`Ctrl+H`**: Toggle Session History (Active vs. Archived)
* **`Ctrl+A` / `c`**: Archive / Reopen Engagement
* **`F2`**: Rename highlighted Workspace or Session inline
* **`Ctrl+D`**: Toggle Delete Mode / Confirm Deletion
* **`Ctrl+M`**: Toggle Organize (Move) Mode / Confirm Move
* **`Space`**: Select/check item (in Delete/Organize modes)
* **`Ctrl+B`**: Toggle Workspace Sidebar
* **`Ctrl+L`**: Switch to Learning Mode
* **`Esc`**: Cancel Action / Mode
* **`Q`**: Quit Application

## Power Mode (Advanced Operator Workspace)
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+T`**: Open New Terminal Tab
* **`Ctrl+W`**: Close Active Terminal Tab
* **`Ctrl+Y`**: Copy Active Terminal Tab Log to Clipboard
* **`Ctrl+K`**: Kill / Terminate Running Job (`SIGTERM`)
* **`Ctrl+R`**: Reopen Archived Session (Restores Write Mode)
* **`Ctrl+PageUp / PageDown`**: Switch Terminal Tabs
* **`Shift+Enter` / `Alt+Enter` / `Ctrl+J`**: Run Command in New Tab
* **`Ctrl+Tab / Ctrl+Shift+Tab`**: Switch Sessions
* **`Ctrl+Right / Ctrl+Left`**: Switch Sessions (Alt)
* **`Ctrl+B`**: Toggle Sidebar (Hide Browser & Job Queue)
* **`Alt+[` / `Alt+]`**: Shrink / Expand Sidebar Width (or Scratchpad when focused)
* **`Ctrl+F`**: Focus Target Filter (`Filter targets...`)
* **`Ctrl+N`**: Toggle Note Taking Scratchpad
* **`Ctrl+G`**: Toggle Global Entity Graph (Workspace-wide view)
* **`Ctrl+E`**: Export Session Report & Database Archive
* **`Ctrl+L`**: Toggle Raw Shell Lock
* **`!` prefix**: One-time Raw Shell Command
* **`Tab`**: Auto-complete Filenames (in Shell-Locked mode)
* **`Up / Down`**: Command History
* **`?` or `help`**: Show this shortcuts menu
* **`Esc`**: Return to Dashboard

## Entity Browser
* **`Enter` / Click**: Select Entity Node (sets context variables)
* **`F2`**: Rename / Set Custom Alias for Selected Entity
* **`Type in Search Box (`Ctrl+F`)`**: Real-time filtering of hosts, ports, services, domains, and aliases

## Learning Mode
* **`F1`**: Show Shortcuts / Help dialog
* **`Ctrl+Left` / `Ctrl+Right`**: Prev Tab / Next Tab (Explanation vs. Raw Output)
* **`Ctrl+B`**: Toggle Lesson Sidebar
* **`Alt+[` / `Alt+]` (or `Alt+{` / `Alt+}`)**: Shrink / Expand Sidebar Width
* **`Esc`**: Return to Tool Browser / Dashboard
* **`Q`**: Quit Application
"""


class RenameDialog(ModalScreen[str]):
    """A modal dialog to rename a workspace, session, or entity."""

    def __init__(self, prompt: str, initial_value: str):
        super().__init__()
        self.prompt = prompt
        self.initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Vertical(id="rename_dialog"):
            yield Label(self.prompt, id="rename_prompt")
            yield Input(value=self.initial_value, id="rename_input")
            with Horizontal(classes="dialog_buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        def focus_input():
            try:
                inp = self.query_one("#rename_input", Input)
                inp.focus()
                inp.action_select_all()
            except Exception:
                pass

        self.call_after_refresh(focus_input)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
            return

        try:
            inp = self.query_one("#rename_input", Input)
            btn_save = self.query_one("#save", Button)
            btn_cancel = self.query_one("#cancel", Button)
        except Exception:
            return

        if inp.has_focus:
            if event.key == "down":
                event.stop()
                btn_save.focus()
        else:
            if event.key == "up":
                event.stop()
                inp.focus()
            elif event.key in ("left", "right"):
                event.stop()
                if btn_save.has_focus:
                    btn_cancel.focus()
                else:
                    btn_save.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            self.dismiss(val)
        else:
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            val = self.query_one("#rename_input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)


class ShortcutsDialog(ModalScreen):
    """Modal displaying keyboard shortcuts and help."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Close"),
        ("f1", "app.pop_screen", "Close"),
        ("q", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="shortcuts_dialog"):
            yield Markdown(SHORTCUTS_MD)
            with Horizontal(classes="dialog_buttons"):
                yield Button("Close", variant="primary", id="close_shortcuts")

    def on_mount(self) -> None:
        def focus_close():
            try:
                self.query_one("#close_shortcuts", Button).focus()
            except Exception:
                pass

        self.call_after_refresh(focus_close)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_shortcuts":
            self.dismiss()
