"""CommandPreviewEditor widget: Deep UI adapter delegating command construction to RecipeBinding."""

from __future__ import annotations

import re
import shlex
from typing import Any, Dict, List, Optional, Tuple, Union

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label, Static

from cyguide.engine.learning import RecipeBinding, ResolvedInvocation
from cyguide.engine.preflight import PreflightVerifier


def _contains_sudo(flags: str, target: str) -> bool:
    """Check if command parameters contain privileged sudo invocation without false-positives on domains."""
    for text in (flags, target):
        if not text:
            continue
        try:
            tokens = shlex.split(text)
            if any(t.lower() == "sudo" for t in tokens):
                return True
        except Exception:
            if re.search(r"(?:^|\s)sudo(?:\s|$)", text, re.IGNORECASE):
                return True
    return False


class FlagEditor(Vertical):
    """Deep widget managing target and flag input with live command previews."""

    def __init__(self, tool_name: str, manifest: Optional[Any] = None):
        super().__init__()
        self.tool_name = tool_name
        self.manifest = manifest

    def compose(self) -> ComposeResult:
        yield Label("TARGET", classes="input_label")
        yield Input(value="127.0.0.1", id="target_input", placeholder="Target IP or hostname")

        yield Label("ADDITIONAL FLAGS", classes="input_label")
        yield Input(placeholder="e.g. -sV -Pn", id="flags_input")

        yield Label("COMMAND PREVIEW", classes="input_label")
        yield Static(f"{self.tool_name} 127.0.0.1", id="command_preview", classes="selectable")
        yield Label("", id="sudo_warning")

    def on_click(self, event: events.Click) -> None:
        if event.widget and getattr(event.widget, "id", None) == "command_preview":
            selected = getattr(self.screen, "get_selected_text", lambda: "")()
            if not selected:
                try:
                    cmd_widget = self.query_one("#command_preview", Static)
                    text = str(cmd_widget.renderable).strip()
                    if text and hasattr(self.app, "copy_to_clipboard"):
                        self.app.copy_to_clipboard(text)
                        self.notify("Command copied to clipboard!", title="Clipboard")
                except Exception:
                    pass

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_preview()

    def update_preview(self) -> None:
        try:
            target = self.query_one("#target_input", Input).value.strip() or "127.0.0.1"
            flags = self.query_one("#flags_input", Input).value
        except Exception:
            return

        try:
            warning = self.query_one("#sudo_warning", Label)
            quick_warn = PreflightVerifier.quick_check(self.tool_name, target, flags)
            if quick_warn:
                warning.update(quick_warn)
                warning.styles.color = (
                    "red" if "[!] Sudo" in quick_warn or "blocked" in quick_warn else "yellow"
                )
            else:
                warning.update("")
        except Exception:
            pass

        try:
            inv = RecipeBinding.resolve(
                manifest=self.manifest,
                target=target,
                flags_used=flags,
            )
            self.query_one("#command_preview", Static).update(inv.cmd_str)
        except Exception:
            self.query_one("#command_preview", Static).update(
                f"{self.tool_name} {flags} {target}".strip()
            )

    def set_flags(self, flags_val: Union[List[str], str]) -> None:
        """Set flags from a recipe or string and update preview."""
        try:
            input_widget = self.query_one("#flags_input", Input)
            if isinstance(flags_val, (list, tuple)):
                input_widget.value = " ".join(flags_val)
            else:
                input_widget.value = str(flags_val)
            self.update_preview()
        except Exception:
            pass

    def set_target(self, target: str) -> None:
        """Set target host or IP and update preview."""
        try:
            input_widget = self.query_one("#target_input", Input)
            input_widget.value = target
            self.update_preview()
        except Exception:
            pass

    def get_command_params(self) -> Tuple[Dict[str, str], str]:
        """Validate security constraints and return command parameters."""
        flags = self.query_one("#flags_input", Input).value
        target = self.query_one("#target_input", Input).value
        if _contains_sudo(flags, target):
            raise ValueError("Sudo is not allowed in Learning Mode.")
        return {"raw_flags": flags}, target

    def get_invocation(self) -> ResolvedInvocation:
        """Resolve full invocation through RecipeBinding."""
        params, target = self.get_command_params()
        return RecipeBinding.resolve(
            manifest=self.manifest,
            target=target,
            flags_used=params.get("raw_flags", ""),
        )
