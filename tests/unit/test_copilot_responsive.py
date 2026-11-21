"""Unit tests for Copilot responsive layout, card table reflow, and resizer messages."""

import pytest
from rich.console import Console
from textual.app import App
from textual.widgets import Button, Input, Label

from cyguide.ui.compat import setup_textual_compat
from cyguide.ui.screens.learning import LearningModeScreen
from cyguide.ui.widgets.markdown import render_markdown

setup_textual_compat()


def test_cyguide_table_card_reflow_narrow():
    """Verify that multi-column markdown tables reflow into readable cards under 52 cols."""
    markdown_table = (
        "| Flag | What it does | Why it matters |\n"
        "| :--- | :--- | :--- |\n"
        "| -sS | TCP SYN scan | Stealthy and fast |\n"
        "| -sV | Version detection | Identifies daemons |\n"
    )

    console_narrow = Console(width=40, height=25, force_terminal=True, color_system=None)
    with console_narrow.capture() as capture_narrow:
        console_narrow.print(render_markdown(markdown_table))
    output_narrow = capture_narrow.get()

    # In narrow mode, it should reflow into bulleted cards with field: value
    assert "• -sS" in output_narrow
    assert "What it does: TCP SYN scan" in output_narrow
    assert "Why it matters: Stealthy and fast" in output_narrow
    assert "• -sV" in output_narrow


def test_cyguide_table_standard_wide():
    """Verify that multi-column tables retain standard grid rendering when width >= 52."""
    markdown_table = (
        "| Flag | What it does | Why it matters |\n"
        "| :--- | :--- | :--- |\n"
        "| -sS | TCP SYN scan | Stealthy and fast |\n"
    )

    console_wide = Console(width=80, height=25, force_terminal=True, color_system=None)
    with console_wide.capture() as capture_wide:
        console_wide.print(render_markdown(markdown_table))
    output_wide = capture_wide.get()

    # In wide mode, it prints standard table borders
    assert "Flag" in output_wide
    assert "What it does" in output_wide
    assert "Why it matters" in output_wide


class CopilotResponsiveTestApp(App):
    def on_mount(self) -> None:
        self.push_screen(LearningModeScreen())


@pytest.mark.asyncio
async def test_copilot_responsive_breakpoints():
    """Verify responsive breakpoints update labels, badges, and placeholders dynamically."""
    app = CopilotResponsiveTestApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, LearningModeScreen)

        # 1. Compact mode (< 36 cols, e.g. 28)
        screen._sync_copilot_responsive_layout(28)
        assert screen.query_one("#copilot_tab_controls") is not None
        assert screen.query_one("#copilot_model_badge", Label).styles.display == "none"
        assert screen.query_one("#toggle_ai_explanation_btn", Button).label == "● ON"
        assert screen.query_one("#copy_explanation_btn", Button).label == "⎘"
        assert screen.query_one("#clear_explanation_btn", Button).label == "⌫"
        assert screen.query_one("#copy_notes_btn", Button).label == "⎘"
        assert screen.query_one("#export_notes_btn", Button).label == "⤓"
        assert screen.query_one("#clear_notes_btn", Button).label == "⌫"
        assert screen.query_one("#ask_btn", Button).label == "▶"
        assert screen.query_one("#chat_input", Input).placeholder == "Ask AI..."

        # 2. Standard mode (36-49 cols, e.g. 44)
        screen._sync_copilot_responsive_layout(44)
        assert screen.query_one("#copilot_model_badge", Label).styles.display == "block"
        assert screen.query_one("#toggle_ai_explanation_btn", Button).label == "● AI: ON"
        assert screen.query_one("#copy_explanation_btn", Button).label == "COPY"
        assert screen.query_one("#clear_explanation_btn", Button).label == "CLEAR"
        assert screen.query_one("#copy_notes_btn", Button).label == "COPY"
        assert screen.query_one("#export_notes_btn", Button).label == "EXPORT"
        assert screen.query_one("#clear_notes_btn", Button).label == "CLEAR"
        assert screen.query_one("#ask_btn", Button).label == "ASK"
        assert "Ask AI tutor or / for help" in screen.query_one("#chat_input", Input).placeholder

        # 3. Wide mode (>= 50 cols, e.g. 60)
        screen._sync_copilot_responsive_layout(60)
        assert screen.query_one("#copilot_model_badge", Label).styles.display == "block"
        assert screen.query_one("#toggle_ai_explanation_btn", Button).label == "● AI: ON"
        assert screen.query_one("#copy_explanation_btn", Button).label == "COPY"
        assert screen.query_one("#clear_explanation_btn", Button).label == "CLEAR"
        assert screen.query_one("#ask_btn", Button).label == "ASK"
        assert "commands" in screen.query_one("#chat_input", Input).placeholder

        # 4. Left sidebar responsive breakpoints (< 26 vs >= 26)
        screen._sync_sidebar_responsive_layout(22)
        assert screen.query_one("#save_checkpoint_btn", Button).label == "⤓"
        assert screen.query_one("#load_checkpoint_btn", Button).label == "⤒"
        assert screen.query_one("#sidebar_ask_btn", Button).label == "✦ ASK"
        assert screen.query_one("#run_btn", Button).label == "▶"

        screen._sync_sidebar_responsive_layout(32)
        assert screen.query_one("#save_checkpoint_btn", Button).label == "⤓ SAVE"
        assert screen.query_one("#load_checkpoint_btn", Button).label == "⤒ LOAD"
        assert screen.query_one("#sidebar_ask_btn", Button).label == "✦ ASK AI"
        assert screen.query_one("#run_btn", Button).label == "▶ RUN"

        # 5. Theory copy action
        screen._raw_theory_content = "RFC 793 SYN Analysis"
        screen.action_copy_theory()
        assert app.clipboard == "RFC 793 SYN Analysis"

        # 6. Notes copy action
        textarea = screen.query_one("#learning_scratchpad_textarea")
        textarea.load_text("# Lab Recon Notes\nDiscovered open port 22 & 80.")

        # Test copy notes
        screen.action_copy_notes()
        assert "Discovered open port 22 & 80." in app.clipboard
