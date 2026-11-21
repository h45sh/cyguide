"""RecipeDeck: Deep widget encapsulating workflow recipe card rendering and state."""

from __future__ import annotations

from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Label, ListItem, Static

from cyguide.engine.learning import ToolLearningContext


class RecipeActionButton(Button):
    """Button inside recipe cards that does not capture focus to prevent TabPane focus snapping."""

    can_focus = False


class RecipeListItem(ListItem):
    """List item for workflow recipes in sidebar."""

    def __init__(self, recipe: Any, tool_name: str):
        super().__init__()
        self.recipe = recipe
        self.tool_name = tool_name

    def compose(self) -> ComposeResult:
        name = getattr(self.recipe, "name", "Recipe")
        yield Label(f"▸ {name}", classes="recipe_name")


class RecipeDeck(VerticalScroll):
    """Deep widget presenting structured workflow recipes and tool reference cards."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.current_context: Optional[ToolLearningContext] = None

    async def load_tool_context(self, context: ToolLearningContext) -> None:
        """Clear and mount tool metadata card and workflow recipe cards."""
        self.current_context = context
        await self.remove_children()

        if not context.recipes:
            await self.mount(
                Static(
                    "No workflow recipes configured for this tool.",
                    id="recipes_empty_state",
                    classes="recipes_header_intro",
                )
            )
            return

        status_text = "● Ready" if context.is_installed else "○ Not in PATH"
        status_cls = "status_ready" if context.is_installed else "status_missing"

        ref_badges = [
            Label(status_text, classes=f"meta_badge {status_cls}"),
            Label(f"CLI: {context.binary}", classes="meta_badge"),
        ]
        if context.produces:
            produces_str = ", ".join(context.produces[:2])
            ref_badges.append(Label(f"Produces: {produces_str}", classes="meta_badge"))

        tool_ref_card = Vertical(
            Horizontal(
                Label(f"◆ {context.tool_name.upper()}", classes="tool_ref_title"),
                Label(
                    f" {context.category.upper()} ",
                    classes="tool_ref_category_badge",
                ),
                classes="tool_ref_header",
            ),
            Horizontal(*ref_badges, classes="tool_ref_meta_bar"),
            Static(context.description, classes="tool_ref_desc"),
            classes="tool_ref_card",
        )
        await self.mount(tool_ref_card)

        intro = Static(
            f"[bold #94a3b8]WORKFLOW RECIPES ({len(context.recipes)})[/]",
            classes="recipes_header_intro",
        )
        await self.mount(intro)

        for idx, r in enumerate(context.recipes):
            has_flags = bool(getattr(r, "flags", None))
            flags_str = " ".join(r.flags) if has_flags else ""
            header_children = [
                Label(f"◆ {r.name}", classes="recipe_card_title"),
            ]
            if has_flags:
                header_children.append(Label(f" {flags_str} ", classes="recipe_card_flags_badge"))
            header_children.append(
                Horizontal(
                    RecipeActionButton(
                        "✦ ASK AI",
                        id=f"ask_recipe_{idx}",
                        classes="recipe_card_btn recipe_ask_btn",
                    ),
                    RecipeActionButton(
                        "▶ RUN",
                        id=f"load_recipe_{idx}",
                        classes="recipe_card_btn recipe_run_btn",
                    ),
                    classes="recipe_card_actions",
                )
            )
            card = Vertical(
                Horizontal(
                    *header_children,
                    classes="recipe_card_header",
                ),
                Label(
                    getattr(r, "description", "") or "No description provided.",
                    classes="recipe_card_desc",
                ),
                classes="recipe_card",
                id=f"recipe_card_{idx}",
            )
            await self.mount(card)

        academic_card = Vertical(
            Label("✦ ACADEMIC & CURRICULUM CO-DESIGN", classes="academic_card_title"),
            Static(
                "CyGuide's learning tracks, wire analyses, and deep-dive labs are built for verifiable classroom instruction. "
                "We welcome collaboration with universities, professors, and open cybersecurity training programs.\n"
                "[dim #94a3b8]Have a lab module or CTF syllabus to integrate into verifiable [bold #38bdf8].cyglab[/] checkpoints? "
                "See [bold #38bdf8]docs/user/ACADEMIC_LAB_GUIDE.md[/] or submit a recipe pull request.[/]",
                classes="academic_card_desc",
            ),
            classes="academic_card",
            id="academic_codesign_card",
        )
        await self.mount(academic_card)

    def set_active_recipe_state(self, active_recipe_idx: Optional[int], is_running: bool) -> None:
        """Update recipe card button labels and disabled states."""
        try:
            for btn in self.query(".recipe_run_btn, .recipe_stop_btn"):
                if btn.id and btn.id.startswith("load_recipe_"):
                    idx_str = btn.id.replace("load_recipe_", "")
                    if idx_str.isdigit():
                        btn_idx = int(idx_str)
                        if is_running:
                            if active_recipe_idx is not None and btn_idx == active_recipe_idx:
                                btn.label = "■ STOP"
                                btn.remove_class("recipe_run_btn")
                                btn.add_class("recipe_stop_btn")
                                btn.disabled = False
                            else:
                                btn.disabled = True
                        else:
                            btn.label = "▶ RUN"
                            btn.remove_class("recipe_stop_btn")
                            btn.add_class("recipe_run_btn")
                            btn.disabled = False

            for ask_btn in self.query(".recipe_ask_btn"):
                ask_btn.disabled = is_running
        except Exception:
            pass

    def reset_buttons(self) -> None:
        """Restore all buttons to idle state."""
        self.set_active_recipe_state(active_recipe_idx=None, is_running=False)
