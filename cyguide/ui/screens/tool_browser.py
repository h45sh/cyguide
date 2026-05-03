"""Tool Selection screen for Learning Mode."""

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Label, ListItem, ListView, Input
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from typing import List, Dict

class ToolListItem(ListItem):
    """A custom list item for the tool browser."""
    def __init__(self, tool_name: str, summary: str, recipes: List[str]):
        super().__init__()
        self.tool_name = tool_name
        self.summary = summary
        self.recipes = recipes

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"{self.tool_name.ljust(12)}", classes="tool_name_label")
            yield Label(self.summary, classes="tool_summary_label")

class ToolBrowserScreen(Screen):
    """Phase 1: Tool Selection Home Screen."""
    
    BINDINGS = [
        ("escape", "nav_dashboard", "Dashboard"),
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="browser_container"):
            yield Label("LEARNING MODE", id="browser_title")
            yield Label("What do you want to learn today?", id="browser_subtitle")
            
            yield Input(placeholder="Search tools, recipes, or flags...", id="search_input")
            
            with Vertical(id="tool_list_area"):
                yield ListView(id="tool_list")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_tools()
        self.query_one("#search_input").focus()

    async def refresh_tools(self, filter_text: str = "") -> None:
        registry = self.app.registry
        tool_list = self.query_one("#tool_list", ListView)
        await tool_list.clear()
        
        # Group tools by category
        categories: Dict[str, List[Dict]] = {}
        for name in registry.list_tools():
            tool_data = registry.get_tool(name)
            manifest = tool_data["manifest"]
            
            if not manifest.modes.get("learning"):
                continue
                
            # Search filtering
            match = filter_text.lower() in name.lower() or \
                    filter_text.lower() in manifest.meta.one_line_summary.lower()
            
            # Also check recipes and flags
            if not match and manifest.learning:
                for r in manifest.learning.recipes:
                    if filter_text.lower() in r.name.lower():
                        match = True; break
                for f in manifest.learning.flags:
                    if filter_text.lower() in f["flag"].lower() or filter_text.lower() in f["explanation"].lower():
                        match = True; break
            
            if match:
                cat = manifest.meta.category
                if cat not in categories: categories[cat] = []
                categories[cat].append({"name": name, "manifest": manifest})

        for cat, tools in categories.items():
            await tool_list.append(ListItem(Label(f"── {cat.upper()} ──────────────────────────────"), disabled=True, classes="category_header_item"))
            for t in tools:
                await tool_list.append(ToolListItem(t["name"], t["manifest"].meta.one_line_summary, [r.name for r in t["manifest"].learning.recipes]))

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search_input":
            await self.refresh_tools(event.value)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ToolListItem):
            # Navigate to Lesson Screen
            self.app.learning_mode_tool = event.item.tool_name
            self.app.switch_screen("learning_mode")

    def action_nav_dashboard(self) -> None:
        self.app.switch_screen("dashboard")
