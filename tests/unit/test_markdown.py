"""Unit tests for CyGuide centralized markdown rendering engine."""

import pytest
from rich.console import Console

from cyguide.ui.widgets.markdown import (
    CYGUIDE_MARKDOWN_THEME,
    CyGuideMarkdown,
    render_markdown,
)

pytestmark = pytest.mark.fast


def test_markdown_theme_hr_color():
    """Verify markdown theme specifies electric blue for horizontal rules."""
    hr_style = CYGUIDE_MARKDOWN_THEME.styles.get("markdown.hr")
    assert hr_style is not None
    assert hr_style.color is not None
    assert hr_style.color.name == "#38bdf8"
    assert hr_style.bold is True


def test_major_break_renders_electric_blue_double_line():
    """Verify major breaks (***) render electric blue double-line (═)."""
    console = Console(width=40, force_terminal=True, color_system="truecolor")
    with console.capture() as capture:
        console.print(render_markdown("Run 1\n\n***\n\nRun 2"))
    rendered = capture.get()

    assert "═" in rendered
    # ANSI 38;2;56;189;248 is #38bdf8 in truecolor RGB
    assert "56;189;248" in rendered


def test_minor_break_renders_dim_single_line():
    """Verify minor breaks (---) render subtle dim single-line (─)."""
    console = Console(width=40, force_terminal=True, color_system="truecolor")
    with console.capture() as capture:
        console.print(render_markdown("Section A\n\n---\n\nSection B"))
    rendered = capture.get()

    assert "─" in rendered
    assert "═" not in rendered
    # ANSI 38;2;51;65;85 is #334155 in truecolor RGB
    assert "51;65;85" in rendered


def test_render_markdown_empty_text():
    """Verify empty text produces a valid empty CyGuideMarkdown renderable."""
    md = render_markdown("")
    assert isinstance(md, CyGuideMarkdown)


def test_render_markdown_bold_heading_cleanup():
    """Verify legacy bolded headings **# Heading** are normalized."""
    md = render_markdown("**## Summary**")
    console = Console(width=40, force_terminal=True)
    with console.capture() as capture:
        console.print(md)
    rendered = capture.get()
    assert "Summary" in rendered
