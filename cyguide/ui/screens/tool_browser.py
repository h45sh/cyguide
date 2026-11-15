import asyncio
import shutil
from typing import Dict, List, Optional

from rich.markdown import Markdown as RichMarkdown
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static

from cyguide.engine.manifest import Manifest

_THEORY_MD_CACHE: Dict[str, RichMarkdown] = {}


def _get_tool_theory_markdown(manifest: Manifest) -> RichMarkdown:
    """Pre-parse and memoize lightweight Rich Markdown for instant sub-millisecond tool switching."""
    cache_key = manifest.meta.name
    if cache_key in _THEORY_MD_CACHE:
        return _THEORY_MD_CACHE[cache_key]

    desc = (manifest.meta.description or manifest.meta.one_line_summary or "").strip()
    theory = (manifest.meta.theory or "").strip()
    if theory:
        full_md = f"**{desc}**\n\n{theory}" if desc else theory
    else:
        full_md = desc or "No theoretical overview available for this tool."

    parsed = RichMarkdown(full_md, justify="left", code_theme="monokai")
    _THEORY_MD_CACHE[cache_key] = parsed
    return parsed

CANONICAL_CATEGORIES = [
    "Network Reconnaissance",
    "Web Enumeration",
    "Vulnerability Assessment",
]

CANONICAL_TOOL_ORDER = {
    "Network Reconnaissance": ["nmap", "whois", "subfinder", "dnspython"],
    "Web Enumeration": ["gobuster", "ffuf"],
    "Vulnerability Assessment": ["nikto", "searchsploit", "nuclei"],
}


def _category_sort_key(category: str) -> tuple[int, str]:
    """Sort canonical categories first in curriculum progression, then alphabetically."""
    try:
        return (0, CANONICAL_CATEGORIES.index(category))
    except ValueError:
        return (1, category.lower())


def _tool_sort_key(category: str, tool_name: str) -> tuple[int, str]:
    """Sort canonical tools in fixed pedagogical order, then alphabetically."""
    cat_order = CANONICAL_TOOL_ORDER.get(category, [])
    try:
        return (0, cat_order.index(tool_name))
    except ValueError:
        return (1, tool_name.lower())


def _match_score(tool_name: str, manifest: Manifest, query: str) -> int:
    """Score matching priority for instant search highlighting."""
    q = query.lower().strip()
    if not q:
        return 999
    name = tool_name.lower()
    if name == q:
        return 0  # Exact tool name match
    if name.startswith(q):
        return 1  # Prefix tool name match
    if q in name:
        return 2  # Substring tool name match
    if q in manifest.meta.one_line_summary.lower():
        return 3  # Summary match
    if q in manifest.meta.category.lower():
        return 4  # Category match
    return 5      # Recipe / flag match


class CategoryHeaderItem(ListItem):
    """Visual category separator item in the tool list."""

    disabled = True

    def __init__(self, category_name: str):
        super().__init__(classes="category_header_item")
        self.category_name = category_name

    def compose(self) -> ComposeResult:
        yield Label(f"◈ {self.category_name.upper()}", classes="category_header_title")


class ToolListItem(ListItem):
    """A clean, single-line item for the tool catalog."""

    def __init__(self, tool_name: str, summary: str, recipes: List[str], manifest: Manifest):
        super().__init__(classes="tool_list_item")
        self.tool_name = tool_name
        self.summary = summary
        self.recipes = recipes
        self.manifest = manifest

    def compose(self) -> ComposeResult:
        with Horizontal(classes="tool_item_row"):
            yield Label(f"◆ {self.tool_name}", classes="tool_name_label")
            count_str = (
                f"{len(self.recipes)} {'recipe' if len(self.recipes) == 1 else 'recipes'}"
            )
            yield Label(f" {count_str} ", classes="tool_recipe_badge")


class ToolInspectorPane(Vertical):
    """Deep module: live inspector rendering tool overview, health, and workflow recipes."""

    def __init__(self, **kwargs):
        super().__init__(id="tool_inspector_pane", **kwargs)
        self.active_tool: Optional[str] = None
        self.active_manifest: Optional[Manifest] = None
        self._show_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        with Vertical(id="inspector_header_card"):
            with Horizontal(id="inspector_title_row"):
                yield Label("◆ SELECT A TOOL", id="inspector_title")
                yield Label("", id="inspector_category_badge")
            yield Horizontal(id="inspector_meta_bar")

        with Horizontal(id="inspector_split_body"):
            with Vertical(id="inspector_desc_card", classes="inspector_card"):
                yield Label("TOOL CAPABILITIES & OVERVIEW", classes="inspector_card_title")
                with VerticalScroll(id="inspector_desc_scroll"):
                    yield Static(
                        "Select a security tool or curriculum module from the catalog to view details.",
                        id="inspector_desc_text",
                    )

            with Vertical(id="inspector_recipes_card", classes="inspector_card"):
                yield Label(
                    "CURRICULUM RECIPES",
                    id="inspector_recipes_card_title",
                    classes="inspector_card_title",
                )
                with VerticalScroll(id="inspector_recipes_scroll"):
                    yield Vertical(id="inspector_recipes_container")

        with Horizontal(id="inspector_action_bar"):
            yield Button("▶ START GUIDED LESSON (↵)", id="start_lesson_btn", variant="primary")

    async def show_tool(self, name: str, manifest: Manifest) -> None:
        """Render security tool briefing and curriculum recipe outline."""
        async with self._show_lock:
            self.active_tool = name
            self.active_manifest = manifest

            bin_ready = shutil.which(manifest.meta.binary) is not None
            status_text = "● Ready" if bin_ready else "○ Not in PATH"
            status_cls = "status_ready" if bin_ready else "status_missing"

            # Update Header
            self.query_one("#inspector_title", Label).update(f"◆ {manifest.meta.name.upper()}")
            self.query_one("#inspector_category_badge", Label).update(
                f" {manifest.meta.category.upper()} "
            )

            meta_bar = self.query_one("#inspector_meta_bar", Horizontal)
            await meta_bar.remove_children()
            meta_badges = [
                Label(status_text, classes=f"meta_badge {status_cls}"),
                Label(f"CLI: {manifest.meta.binary}", classes="meta_badge"),
            ]
            if manifest.output.get("produces"):
                produces_str = ", ".join(manifest.output["produces"][:2])
                meta_badges.append(Label(f"Produces: {produces_str}", classes="meta_badge"))
            await meta_bar.mount(*meta_badges)

            # Update Description Card with ultra-fast textbook Markdown
            theory_renderable = _get_tool_theory_markdown(manifest)
            self.query_one("#inspector_desc_text", Static).update(theory_renderable)
            self.query_one("#inspector_desc_card").display = True
            try:
                self.query_one("#inspector_desc_scroll", VerticalScroll).scroll_home(animate=False)
            except Exception:
                pass

            # Update Recipes Card
            recipes = manifest.learning.recipes if manifest.learning else []
            self.query_one("#inspector_recipes_card_title", Label).update(
                f"CURRICULUM RECIPES ({len(recipes)})"
            )
            recipes_container = self.query_one("#inspector_recipes_container", Vertical)
            await recipes_container.remove_children()

            recipe_widgets = []
            for r in recipes:
                raw_flags = " ".join(r.flags) if getattr(r, "flags", None) else "(standard)"
                flags_display = raw_flags if len(raw_flags) <= 30 else raw_flags[:27] + "..."
                recipe_widgets.append(
                    Horizontal(
                        Label(f"• {r.name}", classes="inspector_recipe_row_name"),
                        Label(f"{flags_display}", classes="inspector_recipe_row_flags"),
                        classes="inspector_recipe_row",
                    )
                )
            if recipe_widgets:
                await recipes_container.mount(*recipe_widgets)
                self.query_one("#inspector_recipes_card").display = True
                try:
                    self.query_one("#inspector_recipes_scroll", VerticalScroll).scroll_home(animate=False)
                except Exception:
                    pass
            else:
                self.query_one("#inspector_recipes_card").display = False

            self.query_one("#inspector_action_bar").display = True

    async def show_empty(self, message: str) -> None:
        """Render an empty/hint state when search yields no matches."""
        async with self._show_lock:
            self.active_tool = None
            self.active_manifest = None

            self.query_one("#inspector_title", Label).update("◆ NO TOOLS FOUND")
            self.query_one("#inspector_category_badge", Label).update("")
            await self.query_one("#inspector_meta_bar", Horizontal).remove_children()

            self.query_one("#inspector_desc_text", Static).update(message)
            self.query_one("#inspector_recipes_card").display = False
            self.query_one("#inspector_action_bar").display = False


class ToolBrowserScreen(Screen):
    """Tool Selection Home Screen for Learning Mode."""

    BINDINGS = [
        ("f1", "show_shortcuts", "Help"),
        ("escape", "nav_dashboard", "Dashboard"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_lock = asyncio.Lock()
        self.last_selected_tool: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="browser_container"):
            with Horizontal(id="browser_header_bar"):
                with Vertical(id="browser_titles"):
                    yield Label("LEARNING MODE", id="browser_title")
                    yield Label(
                        "Select a security tool or curriculum module to begin your guided investigation session.",
                        id="browser_subtitle",
                    )
                yield Label("0 Tools Available", id="browser_stats_badge")

            yield Input(
                placeholder="Search tools, recipes, or flags... (e.g. nmap, syn, cve, -sV)",
                id="search_input",
                select_on_focus=False,
            )

            with Horizontal(id="browser_workspace"):
                with Vertical(id="tool_catalog_pane"):
                    with Horizontal(id="catalog_header_row"):
                        yield Label("SECURITY TOOLS CATALOG", classes="pane_section_title")
                    yield ListView(id="tool_list")

                yield ToolInspectorPane()
        yield Footer()

    async def on_mount(self) -> None:
        await self.reset_fresh_state()

    async def on_screen_resume(self) -> None:
        """Ensure a fresh search state while keeping the highlighter on the active tool."""
        await self.reset_fresh_state()

    async def reset_fresh_state(self) -> None:
        """Reset search query to clean state, reload full catalog, and preserve active tool highlighter."""
        try:
            search_input = self.query_one("#search_input", Input)
            if search_input.value != "":
                search_input.value = ""
            else:
                await self.refresh_tools("")
            tool_list = self.query_one("#tool_list", ListView)
            tool_list.focus()
        except Exception:
            pass

    @property
    def inspector(self) -> ToolInspectorPane:
        return self.query_one(ToolInspectorPane)

    async def refresh_tools(self, filter_text: str = "", preferred_tool: Optional[str] = None) -> None:
        async with self._refresh_lock:
            registry = self.app.registry
            tool_list = self.query_one("#tool_list", ListView)

            target_tool = (
                preferred_tool
                or self.last_selected_tool
                or getattr(self.app, "learning_mode_tool", None)
            )

            # Group tools by category
            categories: Dict[str, List[Dict]] = {}
            total_count = 0

            for name in registry.list_tools():
                tool_data = registry.get_tool(name)
                manifest = tool_data["manifest"]

                if not manifest.modes.get("learning"):
                    continue

                # Search filtering
                match = (
                    filter_text.lower() in name.lower()
                    or filter_text.lower() in manifest.meta.one_line_summary.lower()
                    or filter_text.lower() in manifest.meta.category.lower()
                )

                # Also check recipes and flags
                if not match and manifest.learning:
                    for r in manifest.learning.recipes:
                        flags_joined = (
                            " ".join(r.flags).lower() if getattr(r, "flags", None) else ""
                        )
                        if (
                            filter_text.lower() in r.name.lower()
                            or filter_text.lower() in (r.description or "").lower()
                            or filter_text.lower() in flags_joined
                        ):
                            match = True
                            break
                    if not match:
                        for f in manifest.learning.flags:
                            if (
                                filter_text.lower() in f.get("flag", "").lower()
                                or filter_text.lower() in f.get("explanation", "").lower()
                            ):
                                match = True
                                break

                if match:
                    cat = manifest.meta.category
                    categories.setdefault(cat, []).append({"name": name, "manifest": manifest})
                    total_count += 1

            self.query_one("#browser_stats_badge", Label).update(
                f"{total_count} {'Tool' if total_count == 1 else 'Tools'} Available"
            )

            best_tool_item: Optional[ToolListItem] = None
            best_tool_index: Optional[int] = None
            best_score = 9999

            sorted_cats = sorted(categories.keys(), key=_category_sort_key)
            items_to_add: List[ListItem] = []
            item_index = 0

            for cat in sorted_cats:
                items_to_add.append(CategoryHeaderItem(cat))
                item_index += 1
                sorted_tools = sorted(categories[cat], key=lambda t: _tool_sort_key(cat, t["name"]))
                for t in sorted_tools:
                    recipes_list = (
                        [r.name for r in t["manifest"].learning.recipes]
                        if t["manifest"].learning
                        else []
                    )
                    item = ToolListItem(
                        t["name"],
                        t["manifest"].meta.one_line_summary,
                        recipes_list,
                        t["manifest"],
                    )
                    if filter_text:
                        score = _match_score(t["name"], t["manifest"], filter_text)
                        if score < best_score:
                            best_score = score
                            best_tool_item = item
                            best_tool_index = item_index
                    else:
                        if target_tool and t["name"] == target_tool:
                            best_tool_item = item
                            best_tool_index = item_index
                        elif best_tool_item is None:
                            best_tool_item = item
                            best_tool_index = item_index

                    items_to_add.append(item)
                    item_index += 1

            await tool_list.clear()
            if items_to_add:
                await tool_list.extend(items_to_add)

            if best_tool_item is not None and best_tool_index is not None:
                tool_list.index = best_tool_index
                self.last_selected_tool = best_tool_item.tool_name
                await self.inspector.show_tool(best_tool_item.tool_name, best_tool_item.manifest)
            else:
                await tool_list.append(
                    ListItem(
                        Label(f"No tools match '{filter_text}'", classes="no_tools_found"),
                        disabled=True,
                    )
                )
                await self.inspector.show_empty(
                    f"No security tools or recipes match '{filter_text}'.\n\n"
                    "Try searching by tool name (e.g. nmap), category (e.g. web), or flag keyword (e.g. cve, -sV)."
                )

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            await self.refresh_tools(event.value)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search_input":
            if self.inspector.active_tool:
                self._launch_tool(self.inspector.active_tool)

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, ToolListItem):
            self.last_selected_tool = event.item.tool_name
            await self.inspector.show_tool(event.item.tool_name, event.item.manifest)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ToolListItem):
            self.last_selected_tool = event.item.tool_name
            self._launch_tool(event.item.tool_name)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start_lesson_btn" and self.inspector.active_tool:
            self._launch_tool(self.inspector.active_tool)

    def on_key(self, event: events.Key) -> None:
        search_input = self.query_one("#search_input", Input)

        # 1. Down arrow from search input moves focus down to tool list
        if event.key == "down" and search_input.has_focus:
            tool_list = self.query_one("#tool_list", ListView)
            tool_list.focus()
            event.prevent_default()
            event.stop()
            return

        # 2. Up arrow from top of tool list moves focus back up to search input
        if event.key == "up" and not search_input.has_focus:
            tool_list = self.query_one("#tool_list", ListView)
            if tool_list.index in (None, 0, 1):
                search_input.focus()
                event.prevent_default()
                event.stop()
                return

        # 3. Enter key or Right arrow key: open currently highlighted tool directly
        is_right_nav = event.key == "right" and (not search_input.has_focus or search_input.value == "")
        if (event.key == "enter" or is_right_nav) and self.inspector.active_tool:
            self._launch_tool(self.inspector.active_tool)
            event.prevent_default()
            event.stop()
            return

        # 4. Type-to-search: alphanumeric character pressed while search_input is not focused
        if (
            not search_input.has_focus
            and event.is_printable
            and len(event.character or "") == 1
            and not event.key.startswith("ctrl+")
            and not event.key.startswith("alt+")
        ):
            search_input.focus()
            search_input.value += event.character
            search_input.cursor_position = len(search_input.value)
            event.prevent_default()
            event.stop()
            return

        # 5. Backspace while search_input is not focused: delete last char and focus
        if not search_input.has_focus and event.key == "backspace":
            search_input.focus()
            if search_input.value:
                search_input.value = search_input.value[:-1]
                search_input.cursor_position = len(search_input.value)
            event.prevent_default()
            event.stop()
            return

    def _launch_tool(self, tool_name: str) -> None:
        """Launch selected tool into Learning Mode screen."""
        self.last_selected_tool = tool_name
        self.app.learning_mode_tool = tool_name
        self.app.switch_screen("learning_mode")

    def action_show_shortcuts(self) -> None:
        from cyguide.ui.dialogs import ShortcutsDialog

        self.app.push_screen(ShortcutsDialog())

    def action_nav_dashboard(self) -> None:
        """Single escape directly to the dashboard."""
        self.app.switch_screen("dashboard")
