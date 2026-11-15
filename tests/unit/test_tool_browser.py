"""Unit tests for the Tool Browser screen (Option A Split Master-Detail Layout)."""

import pytest
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, ListView, Static

from cyguide.app import CyGuideApp
from cyguide.ui.screens.tool_browser import (
    CANONICAL_CATEGORIES,
    CANONICAL_TOOL_ORDER,
    CategoryHeaderItem,
    ToolBrowserScreen,
    ToolInspectorPane,
    ToolListItem,
)


@pytest.mark.asyncio
async def test_tool_browser_deterministic_ordering():
    """Verify categories and tools follow canonical curriculum ordering deterministically."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ToolBrowserScreen)

        tool_list = screen.query_one("#tool_list", ListView)
        assert len(tool_list.children) > 0

        # Collect category headers and tool items in order
        categories_found = []
        tools_by_category = {}
        current_cat = None

        for item in tool_list.children:
            if isinstance(item, CategoryHeaderItem):
                current_cat = item.category_name
                categories_found.append(current_cat)
                tools_by_category[current_cat] = []
            elif isinstance(item, ToolListItem):
                assert current_cat is not None
                tools_by_category[current_cat].append(item.tool_name)

        # 1. Verify exact category order matches canonical curriculum
        assert categories_found == CANONICAL_CATEGORIES

        # 2. Verify exact tool order within each category matches dev specification
        for cat, expected_tools in CANONICAL_TOOL_ORDER.items():
            assert tools_by_category[cat] == expected_tools


@pytest.mark.asyncio
async def test_tool_browser_split_layout_and_inspector_live_update():
    """Verify Master-Detail layout panes and live inspector updates on navigation."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ToolBrowserScreen)

        # Verify layout components exist
        catalog_pane = screen.query_one("#tool_catalog_pane")
        inspector_pane = screen.query_one(ToolInspectorPane)
        search_input = screen.query_one("#search_input", Input)

        tool_list = screen.query_one("#tool_list", ListView)
        assert catalog_pane is not None
        assert inspector_pane is not None
        # Focus is directly on the tool list pane for instant keyboard sliding
        assert tool_list.has_focus
        assert not search_input.has_focus

        # Verify side-by-side horizontal split and independent vertical scroll areas
        split_body = inspector_pane.query_one("#inspector_split_body", Horizontal)
        assert split_body is not None
        desc_card = inspector_pane.query_one("#inspector_desc_card")
        recipes_card = inspector_pane.query_one("#inspector_recipes_card")
        assert desc_card is not None
        assert recipes_card is not None
        assert inspector_pane.query_one("#inspector_desc_scroll", VerticalScroll) is not None
        assert inspector_pane.query_one("#inspector_recipes_scroll", VerticalScroll) is not None

        # Initially, first tool (nmap) is active in inspector
        assert inspector_pane.active_tool == "nmap"
        assert len(inspector_pane.query(".inspector_recipe_row")) == 7
        desc_text = inspector_pane.query_one("#inspector_desc_text", Static)
        assert "RFC 793" in getattr(desc_text.content, "markup", "")

        # Arrow down in list to next tool (whois)
        await pilot.press("down")
        await pilot.pause()
        assert tool_list.has_focus
        assert inspector_pane.active_tool == "whois"
        assert len(inspector_pane.query(".inspector_recipe_row")) == 3
        assert "RFC 3912" in getattr(desc_text.content, "markup", "")

        # Press right arrow to launch the highlighted tool (whois) directly into learning mode
        await pilot.press("right")
        await pilot.pause()
        assert app.learning_mode_tool == "whois"
        assert app.screen.__class__.__name__ in ("LearningModeScreen", "LearningScreen")


@pytest.mark.asyncio
async def test_tool_browser_search_filter_and_empty_state():
    """Verify search filtering across tool names, categories, recipes, and flags."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        search_input = screen.query_one("#search_input", Input)
        inspector_pane = screen.query_one(ToolInspectorPane)

        # 1. Filter by tool name
        search_input.value = "gobuster"
        await pilot.pause()
        assert inspector_pane.active_tool == "gobuster"
        tool_items = screen.query(ToolListItem)
        assert len(tool_items) == 1
        assert tool_items[0].tool_name == "gobuster"

        # 2. Filter by flag (e.g. -sV)
        search_input.value = "-sV"
        await pilot.pause()
        assert inspector_pane.active_tool == "nmap"

        # 3. Filter with no matches
        search_input.value = "nonexistent_query_xyz"
        await pilot.pause()
        assert inspector_pane.active_tool is None
        empty_label = screen.query_one(".no_tools_found")
        assert "nonexistent_query_xyz" in str(empty_label.render())
        assert len(screen.query(ToolListItem)) == 0


@pytest.mark.asyncio
async def test_tool_browser_launch_actions():
    """Verify tool selection via Enter, click, and Start Lesson button."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        inspector_pane = screen.query_one(ToolInspectorPane)
        assert inspector_pane.active_tool == "nmap"

        # 1. Click Start Lesson button
        start_btn = inspector_pane.query_one("#start_lesson_btn", Button)
        start_btn.press()
        await pilot.pause()

        assert app.learning_mode_tool == "nmap"
        assert app.screen.name == "learning_mode" or app.screen.__class__.__name__ == "LearningModeScreen"


@pytest.mark.asyncio
async def test_tool_browser_type_to_search_and_enter_launch():
    """Verify auto-typing into search from list and pressing Enter launches closest match."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        search_input = screen.query_one("#search_input", Input)
        tool_list = screen.query_one("#tool_list", ListView)
        inspector_pane = screen.query_one(ToolInspectorPane)

        # 1. Move focus down to tool list
        await pilot.press("down")
        await pilot.pause()
        assert tool_list.has_focus

        # 2. Type characters "w", "h", "o" while list is focused
        await pilot.press("w")
        await pilot.press("h")
        await pilot.press("o")
        await pilot.pause()

        # Search bar should receive the typed characters automatically
        assert search_input.value == "who"
        assert inspector_pane.active_tool == "whois"

        # 3. Pressing Enter should immediately launch the highlighted tool (whois)
        await pilot.press("enter")
        await pilot.pause()

        assert app.learning_mode_tool == "whois"
        assert app.screen.name == "learning_mode" or app.screen.__class__.__name__ == "LearningModeScreen"


@pytest.mark.asyncio
async def test_tool_browser_single_escape_and_fresh_resume():
    """Verify single escape exits directly to dashboard and fresh resume with no duplication."""
    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(140, 35)) as pilot:
        await app.push_screen("tool_browser")
        await pilot.pause()

        screen = app.screen
        search_input = screen.query_one("#search_input", Input)
        inspector_pane = screen.query_one(ToolInspectorPane)

        # 1. Type filter
        search_input.value = "nuclei"
        await pilot.pause()
        assert inspector_pane.active_tool == "nuclei"

        # 2. Single escape immediately exits to dashboard
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ in ("DashboardScreen", "HomeScreen")

        # 3. Resuming tool_browser returns to fresh search bar but preserves active tool highlighter
        await app.switch_screen("tool_browser")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ToolBrowserScreen)
        # Search input is completely fresh and clean
        assert screen.query_one("#search_input", Input).value == ""
        # Highlighter stays on the same tool option as before entering (nuclei)
        assert screen.query_one(ToolInspectorPane).active_tool == "nuclei"
        assert len(screen.query_one(ToolInspectorPane).query(".inspector_recipe_row")) == 5

        # Verify no duplicated items in tool list or recipes in inspector
        tool_items = [item.tool_name for item in screen.query(ToolListItem)]
        assert len(tool_items) == len(set(tool_items))

        # 4. Enter learning mode for nuclei, press Esc to return, verify nuclei highlight is kept with fresh search
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ in ("LearningModeScreen", "LearningScreen")

        await pilot.press("escape")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ToolBrowserScreen)
        assert screen.query_one("#search_input", Input).value == ""
        assert screen.query_one(ToolInspectorPane).active_tool == "nuclei"

