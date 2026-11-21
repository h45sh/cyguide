"""Preflight dependency, wordlist, and parameter verification modal screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from cyguide.engine.preflight import PreflightIssue, PreflightReport, PreflightVerifier


@dataclass
class PreflightModalResult:
    """Result returned when dismissing PreflightModal."""

    confirmed: bool
    target: str
    flags: str


class PreflightModal(ModalScreen[Optional[PreflightModalResult]]):
    """Modal dialog displaying preflight checks, missing binaries, and one-click remedies."""

    DEFAULT_CSS = """
    PreflightModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #preflight_modal_card {
        width: 78;
        max-width: 90%;
        max-height: 85%;
        background: #121316;
        border: heavy #ef4444;
        padding: 1 2;
    }

    #preflight_modal_card.is_ready {
        border: heavy #10b981;
    }

    #preflight_modal_card.is_warning_only {
        border: heavy #f59e0b;
    }

    #preflight_header {
        height: auto;
        margin-bottom: 1;
    }

    #preflight_title {
        text-style: bold;
        color: #fca5a5;
        width: 1fr;
    }

    #preflight_meta_row {
        height: auto;
        margin-bottom: 1;
    }

    .preflight_tool_badge {
        background: #27272a;
        color: #38bdf8;
        text-style: bold;
        padding: 0 1;
        margin-right: 1;
    }

    .preflight_status_badge {
        padding: 0 1;
        text-style: bold;
        margin-right: 1;
    }

    .badge_error {
        background: #450a0a;
        color: #ef4444;
    }

    .badge_warning {
        background: #451a03;
        color: #f59e0b;
    }

    .badge_ok {
        background: #064e3b;
        color: #10b981;
    }

    #preflight_desc {
        color: #71717a;
        margin-bottom: 1;
    }

    #preflight_issues_scroll {
        max-height: 18;
        background: #09090b;
        border: solid #27272a;
        padding: 1;
        margin-bottom: 1;
    }

    .preflight_issue_card {
        height: auto;
        background: #18181b;
        border-left: wide #ef4444;
        padding: 1;
        margin-bottom: 1;
    }

    .preflight_issue_card.issue_warning {
        border-left: wide #f59e0b;
    }

    .issue_header {
        height: auto;
        margin-bottom: 0;
    }

    .issue_tag {
        text-style: bold;
        margin-right: 1;
    }

    .issue_title {
        color: #ffffff;
        text-style: bold;
    }

    .issue_desc {
        color: #a1a1aa;
        margin-top: 0;
        margin-bottom: 0;
    }

    .issue_hint {
        color: #38bdf8;
        text-style: italic;
        margin-top: 0;
        margin-bottom: 1;
    }

    .remedy_btn {
        width: auto;
        margin-top: 0;
    }

    #preflight_actions_row {
        height: auto;
        align: right middle;
    }

    #preflight_proceed_btn {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        report: PreflightReport,
        verifier: PreflightVerifier,
        active_tool: str = "",
        initial_target: str = "",
        initial_flags: str = "",
        recipe_idx: Optional[int] = None,
    ):
        super().__init__()
        self.report = report
        self.verifier = verifier
        self.active_tool = active_tool
        self.current_target = initial_target
        self.current_flags = initial_flags
        self.recipe_idx = recipe_idx

    def compose(self) -> ComposeResult:
        card_class = "checkpoint_card"
        if self.report.is_valid:
            card_class = "is_ready" if not self.report.has_warnings else "is_warning_only"

        with Vertical(id="preflight_modal_card", classes=card_class):
            with Horizontal(id="preflight_header"):
                yield Label("◆ PRE-FLIGHT VERIFICATION", id="preflight_title")
                yield Label("Esc: Cancel", id="preflight_modal_esc")

            with Horizontal(id="preflight_meta_row"):
                yield Label(
                    f"TOOL: {self.active_tool.upper()}",
                    classes="preflight_tool_badge",
                    markup=False,
                )
                yield Label(
                    f"Target: [bold #38bdf8]{self.current_target or 'None'}[/bold #38bdf8]",
                    id="preflight_meta_target",
                )
                status_text, status_class = self._get_status_badge_meta()
                yield Label(
                    status_text,
                    classes=f"preflight_status_badge {status_class}",
                    id="preflight_status_label",
                )

            yield Label(
                "Potential execution issues or missing dependencies were detected before launching the scan.",
                id="preflight_desc",
            )

            with VerticalScroll(id="preflight_issues_scroll"):
                for idx, issue in enumerate(self.report.issues):
                    yield from self._render_issue_card(idx, issue)

            with Horizontal(id="preflight_actions_row"):
                yield Button("Cancel", variant="default", id="preflight_cancel_btn")
                yield Button(
                    "▶ Proceed with Scan",
                    variant="success",
                    id="preflight_proceed_btn",
                    disabled=not self.report.is_valid,
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "preflight_cancel_btn":
            self.action_cancel()
        elif bid == "preflight_proceed_btn":
            self.action_proceed()
        elif bid.startswith("remedy_btn_"):
            try:
                idx = int(bid.replace("remedy_btn_", ""))
                self._handle_remedy(idx)
            except Exception as e:
                self.notify(f"Remediation error: {e}", severity="error")

    def action_cancel(self) -> None:
        """Dismiss without executing."""
        self.dismiss(None)

    def action_proceed(self) -> None:
        """Proceed with execution if valid."""
        if not self.report.is_valid:
            self.notify("Cannot proceed: blocking errors must be remediated.", severity="warning")
            return
        self.dismiss(
            PreflightModalResult(
                confirmed=True,
                target=self.current_target,
                flags=self.current_flags,
            )
        )

    def _handle_remedy(self, idx: int) -> None:
        """Execute a one-click automated remedy and refresh the modal report."""
        if idx < 0 or idx >= len(self.report.issues):
            return

        issue = self.report.issues[idx]
        if issue.remedy_action == "copy_install_command":
            cmd = issue.remedy_payload or issue.remediation_hint
            try:
                if hasattr(self.app, "copy_to_clipboard"):
                    self.app.copy_to_clipboard(cmd)
                self.notify(f"Copied to clipboard: {cmd}", title="Install Command")
            except Exception:
                pass
            return

        # Apply target/flags/wordlist remedies
        updated_target, updated_flags, feedback = self.verifier.apply_remedy(
            issue=issue,
            target=self.current_target,
            flags=self.current_flags,
        )
        self.current_target = updated_target
        self.current_flags = updated_flags

        if feedback:
            try:
                self.notify(feedback, title="Remedy Applied", severity="information")
            except Exception:
                pass

        # Re-verify and rebuild UI
        self.report = self.verifier.verify(
            tool_name=self.active_tool,
            target=self.current_target,
            flags=self.current_flags,
            recipe_idx=self.recipe_idx,
        )
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Re-render issue list and update status badges."""
        try:
            scroll = self.query_one("#preflight_issues_scroll", VerticalScroll)
            scroll.remove_children()

            if not self.report.issues:
                scroll.mount(
                    Static(
                        "[bold #10b981]✔ All preflight checks passed! The command is ready to execute.[/]",
                        classes="preflight_success_notice",
                    )
                )
            else:
                for idx, issue in enumerate(self.report.issues):
                    for w in self._render_issue_card(idx, issue):
                        scroll.mount(w)

            # Update status badge & card styling
            status_text, status_class = self._get_status_badge_meta()
            label = self.query_one("#preflight_status_label", Label)
            label.update(status_text)
            label.classes = f"preflight_status_badge {status_class}"

            target_label = self.query_one("#preflight_meta_target", Label)
            target_label.update(
                f"Target: [bold #38bdf8]{self.current_target or 'None'}[/bold #38bdf8]"
            )

            card = self.query_one("#preflight_modal_card", Vertical)
            card.remove_class("is_ready")
            card.remove_class("is_warning_only")
            if self.report.is_valid:
                card.add_class("is_ready" if not self.report.has_warnings else "is_warning_only")

            # Update proceed button state
            btn = self.query_one("#preflight_proceed_btn", Button)
            btn.disabled = not self.report.is_valid
            if self.report.is_valid:
                btn.focus()
        except Exception:
            pass

    def _get_status_badge_meta(self) -> tuple[str, str]:
        """Return formatted badge text and CSS class based on report status."""
        errors_cnt = len(self.report.errors)
        warnings_cnt = len(self.report.warnings)

        if errors_cnt > 0:
            return (
                f"✕ {errors_cnt} ERROR{'S' if errors_cnt > 1 else ''}",
                "badge_error",
            )
        elif warnings_cnt > 0:
            return (
                f"⚠ {warnings_cnt} WARNING{'S' if warnings_cnt > 1 else ''}",
                "badge_warning",
            )
        return "✔ READY", "badge_ok"

    def _render_issue_card(self, idx: int, issue: PreflightIssue) -> List[Any]:
        """Produce UI widgets for an individual issue card."""
        is_warn = issue.severity == "warning"
        card_class = "preflight_issue_card issue_warning" if is_warn else "preflight_issue_card"
        tag_color = "#f59e0b" if is_warn else "#ef4444"
        tag_text = f"[{tag_color} bold][{issue.category.upper()}][/]"

        widgets = []
        with Vertical(classes=card_class):
            with Horizontal(classes="issue_header"):
                widgets.append(Label(tag_text, classes="issue_tag"))
                widgets.append(Label(issue.title, classes="issue_title"))
            widgets.append(Label(issue.description, classes="issue_desc"))
            widgets.append(Label(f"💡 {issue.remediation_hint}", classes="issue_hint"))

            if issue.can_auto_remedy and issue.remedy_label:
                widgets.append(
                    Button(
                        issue.remedy_label,
                        id=f"remedy_btn_{idx}",
                        variant="primary",
                        classes="remedy_btn",
                    )
                )

        return [Vertical(*widgets, classes=card_class)]
