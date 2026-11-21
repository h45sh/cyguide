"""CyGuide Centralized Markdown Rendering Engine.

Provides unified, low-glare, eye-friendly typography across all screens (Learning, Power,
Tool Browser, dialogs, modals). Combines CyGuide's signature electric blue accents
for dividers and interactive focus with warm amber headings and a calm slate palette.
"""

from __future__ import annotations

import re
from typing import ClassVar, Dict, Type

from rich import box
from rich.markdown import (
    BlockQuote as RichBlockQuote,
)
from rich.markdown import (
    Heading as RichHeading,
)
from rich.markdown import (
    HorizontalRule as RichHorizontalRule,
)
from rich.markdown import (
    Markdown as RichMarkdown,
)
from rich.markdown import (
    MarkdownElement,
)
from rich.markdown import (
    TableElement as RichTableElement,
)
from rich.rule import Rule as RichRule
from rich.segment import Segment as RichSegment
from rich.style import Style as RichStyle
from rich.table import Table as RichTable
from rich.text import Text as RichText
from rich.theme import Theme

# Eye-Comfort Soft Cyan, Sky Blue & Slate Palette for CyGuide Markdown
CYGUIDE_MARKDOWN_THEME = Theme(
    {
        "markdown.h1": "bold #38bdf8",
        "markdown.h2": "bold #7dd3fc",
        "markdown.h3": "bold #cbd5e1",
        "markdown.h4": "bold #94a3b8",
        "markdown.h5": "bold #94a3b8",
        "markdown.h6": "dim #64748b",
        "markdown.paragraph": "#cbd5e1",
        "markdown.text": "#cbd5e1",
        "markdown.em": "italic #94a3b8",
        "markdown.strong": "bold #e2e8f0",
        "markdown.code": "#86efac on #181c24",
        "markdown.code_block": "#cbd5e1 on #12151b",
        "markdown.block_quote": "#94a3b8",
        "markdown.list": "#38bdf8",
        "markdown.item": "#cbd5e1",
        "markdown.item.bullet": "#38bdf8",
        "markdown.item.number": "#38bdf8",
        "markdown.hr": "bold #38bdf8",
        "markdown.link": "underline #38bdf8",
        "markdown.link_url": "underline #0284c7",
        "markdown.table.header": "bold #7dd3fc",
        "markdown.table.border": "#28303f",
    }
)


class CyGuideHorizontalRule(RichHorizontalRule):
    """Adaptive horizontal separator:
    - Electric blue double-line (═) between distinct runs/questions (***)
    - Subtle dim single-line (─) for internal markdown section breaks (---)
    """

    def __init__(self, is_major_break: bool = False):
        super().__init__()
        self.is_major_break = is_major_break

    @classmethod
    def create(cls, markdown: RichMarkdown, token) -> CyGuideHorizontalRule:
        is_major = getattr(token, "markup", "").startswith("*")
        return cls(is_major_break=is_major)

    def __rich_console__(self, console, options):
        if self.is_major_break:
            yield RichRule(style="bold #38bdf8", characters="═")
        else:
            yield RichRule(style="dim #334155", characters="─")
        yield RichText()


class CyGuideHeading(RichHeading):
    """Clean heading hierarchy without eye-straining ad-hoc highlights."""

    def __rich_console__(self, console, options):
        text = self.text.copy()
        heading_justify = self.LEVEL_ALIGN.get(self.tag, "left")
        text.justify = heading_justify
        yield text


class CyGuideBlockQuote(RichBlockQuote):
    """Uniform blockquote with subtle slate accent bar and comfortable reading text."""

    def __rich_console__(self, console, options):
        render_options = options.update(width=options.max_width - 4)
        border_style = RichStyle.parse("#475569")
        text_style = "#cbd5e1"

        for elem in self.elements:
            if hasattr(elem, "text"):
                elem.text.stylize(text_style)

        lines = console.render_lines(self.elements, render_options, style=border_style)
        new_line = RichSegment("\n")
        padding = RichSegment("▌ ", border_style)
        for line in lines:
            yield padding
            yield from line
            yield new_line


class CyGuideTable(RichTableElement):
    """Adaptive markdown table that reflows into clean card lists in narrow viewports."""

    def __rich_console__(self, console, options):
        headers = []
        if self.header is not None and self.header.row is not None:
            headers = [c.content.plain.strip() for c in self.header.row.cells]

        # In narrow viewports (< 52 cols), wide multi-column tables crush to unreadable widths.
        # Reflow rows into clean, readable key-value cards instead.
        if options.max_width < 52 and len(headers) >= 2:
            if self.body is not None:
                for idx, row in enumerate(self.body.rows):
                    cells = [c.content for c in row.cells]
                    card_text = RichText()
                    primary_title = cells[0].plain.strip() if cells else f"Item {idx + 1}"
                    card_text.append(f"• {primary_title}\n", style="bold #7dd3fc")
                    for h_idx in range(1, len(cells)):
                        h_title = headers[h_idx] if h_idx < len(headers) else f"Field {h_idx + 1}"
                        val = cells[h_idx].plain.strip()
                        card_text.append(f"  {h_title}: ", style="bold #94a3b8")
                        card_text.append(f"{val}\n", style="#cbd5e1")
                    card_text.append("\n")
                    yield card_text
            return

        table = RichTable(
            box=box.SIMPLE,
            pad_edge=False,
            style="markdown.table.border",
            show_edge=True,
            collapse_padding=True,
        )
        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                table.add_column(heading)
        if self.body is not None:
            for row in self.body.rows:
                row_content = [element.content for element in row.cells]
                table.add_row(*row_content)
        yield table


class CyGuideMarkdown(RichMarkdown):
    """Markdown renderer with customized CyGuide visual elements."""

    elements: ClassVar[Dict[str, Type[MarkdownElement]]] = dict(RichMarkdown.elements)
    elements["hr"] = CyGuideHorizontalRule
    elements["heading_open"] = CyGuideHeading
    elements["blockquote_open"] = CyGuideBlockQuote
    elements["table_open"] = CyGuideTable


def render_markdown(text: str, code_theme: str = "nord-darker") -> CyGuideMarkdown:
    """Render markdown using CyGuide unified low-glare styling."""
    if not text:
        return CyGuideMarkdown("", justify="left", code_theme=code_theme)
    if "**#" in text:
        text = re.sub(r"^\s*\*\*(#{1,6}\s+.*?)\*\*\s*$", r"\1", text, flags=re.MULTILINE)
    return CyGuideMarkdown(text, justify="left", code_theme=code_theme)
