"""Unit tests for Phase 3.5 Learning Mode hardening and Entity Browser filtering."""

import json

import pytest

from cyguide.engine.explainer import ExplainerBackend
from cyguide.engine.gateway import ActionGateway, ActionValidationError
from cyguide.engine.manifest import Manifest
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.ui.screens.learning import LearningModeScreen
from cyguide.ui.widgets.power import EntityBrowser


class MockExplainerBackend(ExplainerBackend):
    async def explain(self, prompt: str):
        yield "Response to: "
        yield prompt


@pytest.mark.asyncio
async def test_explainer_ask_and_explain_backward_compat():
    backend = MockExplainerBackend()
    
    # Test ExplainerBackend.ask() alias
    chunks = []
    async for chunk in backend.ask("test query"):
        chunks.append(chunk)
    assert "".join(chunks) == "Response to: test query"

    # Test ExplainerBackend.explain() directly
    chunks_expl = []
    async for chunk in backend.explain("backend test 2"):
        chunks_expl.append(chunk)
    assert "".join(chunks_expl) == "Response to: backend test 2"



def test_strip_scanner_noise():
    screen = LearningModeScreen()
    raw_output = (
        "===============================================================\n"
        "Gobuster v3.5\n"
        "by OJ Reeves (@TheColonial) & Christian Mehlmauer (@firefart)\n"
        "===============================================================\n"
        "[-] Target: http://127.0.0.1\n"
        "[-] Method: GET\n"
        "Progress: 24% [====>              ] 240/1000\n"
        "/admin (Status: 200) [Size: 1234]\n"
        "/login (Status: 302) [Size: 456]\n"
        "===============================================================\n"
    )
    cleaned = screen._strip_scanner_noise(raw_output)
    assert "Gobuster v3.5" not in cleaned
    assert "by OJ Reeves" not in cleaned
    assert "Progress: 24%" not in cleaned
    assert "/admin (Status: 200)" in cleaned
    assert "/login (Status: 302)" in cleaned


@pytest.mark.asyncio
async def test_extract_structured_findings():
    store = GraphStore(":memory:")
    await store.initialize()
    _, session_id = await store.get_or_create_learning_sandbox()

    # Upsert sample finding
    from cyguide.schemas.network import NetworkService
    svc = NetworkService.create(host_ip="127.0.0.1", port=80, protocol="tcp", service_name="http")
    await store.upsert_finding(session_id, svc)

    screen = LearningModeScreen()
    ui_text, llm_text = await screen._extract_structured_findings(store, session_id)
    assert "80/tcp" in ui_text
    assert "http" in ui_text
    assert "80/tcp" in llm_text
    assert "http" in llm_text

    await store.close()


@pytest.mark.asyncio
async def test_entity_browser_search_filter():
    browser = EntityBrowser()
    graph_data = {
        "nodes": [
            {
                "id": "host_1",
                "schema_type": "network.host",
                "pik_json": json.dumps({"ip": "192.168.1.10"}),
                "data_json": json.dumps({"state": "up", "alias": "primary-dc"}),
                "status": "confirmed",
            },
            {
                "id": "svc_1",
                "schema_type": "network.service",
                "pik_json": json.dumps({"ip": "192.168.1.10", "port": 22, "protocol": "tcp"}),
                "data_json": json.dumps({"service_name": "ssh"}),
                "status": "confirmed",
            },
            {
                "id": "host_2",
                "schema_type": "network.host",
                "pik_json": json.dumps({"ip": "10.0.0.5"}),
                "data_json": json.dumps({"state": "up"}),
                "status": "confirmed",
            },
            {
                "id": "host_loopback",
                "schema_type": "network.host",
                "pik_json": json.dumps({"ip": "127.0.0.1"}),
                "data_json": json.dumps({"state": "up"}),
                "status": "confirmed",
            },
            {
                "id": "dns_1",
                "schema_type": "dns.record",
                "pik_json": json.dumps({"domain": "internal.corp", "type": "A", "value": "10.0.0.5"}),
                "data_json": json.dumps({}),
                "status": "confirmed",
            },
        ],
        "edges": [
            {"source_id": "host_1", "target_id": "svc_1", "rel": "hosts"}
        ]
    }

    # 1. Unfiltered refresh - verify automatic naming (localhost, DNS domain, alias)
    browser.set_filter("")
    await browser.refresh_entities(graph_data)
    targets_node = next(n for n in browser.root.children if "Targets" in str(n.label))
    host_labels = [str(child.label) for child in targets_node.children]
    assert any("192.168.1.10 (primary-dc)" in l for l in host_labels)
    assert any("10.0.0.5 (internal.corp)" in l for l in host_labels)
    assert any("127.0.0.1 (localhost)" in l for l in host_labels)

    # 2. Filter for ssh/22 (should keep host_1 and svc_1)
    browser.set_filter("22")
    await browser.refresh_entities(graph_data)
    labels_filtered = [str(node.label) for node in browser.root.children]
    assert any("Targets (1)" in l for l in labels_filtered)

    # 3. Filter for hostname/alias "primary-dc" or "internal.corp"
    browser.set_filter("primary-dc")
    await browser.refresh_entities(graph_data)
    labels_alias = [str(node.label) for node in browser.root.children]
    assert any("Targets (1)" in l for l in labels_alias)

    browser.set_filter("internal.corp")
    await browser.refresh_entities(graph_data)
    labels_domain = [str(node.label) for node in browser.root.children]
    assert any("Targets (1)" in l for l in labels_domain)

    # 4. Filter with no matches
    browser.set_filter("nonexistent_pattern")
    await browser.refresh_entities(graph_data)
    labels_empty = [str(node.label) for node in browser.root.children]
    assert any("No matches for 'nonexistent_pattern'" in l for l in labels_empty)


@pytest.mark.asyncio
async def test_store_and_facade_set_entity_alias():
    store = GraphStore(":memory:")
    await store.initialize()
    _, session_id = await store.get_or_create_learning_sandbox()

    from cyguide.schemas.network import NetworkHost
    host = NetworkHost.create(ip="192.168.1.50")
    await store.upsert_finding(session_id, host)

    # Fetch node
    nodes = await store.get_all_nodes(session_id)
    assert len(nodes) == 1
    node_id = nodes[0]["id"]

    from unittest.mock import MagicMock

    from cyguide.engine.power_facade import PowerWorkspaceFacade
    facade = PowerWorkspaceFacade(store, MagicMock(), MagicMock())
    await facade.set_entity_alias(session_id, node_id, "DMZ-Web-Gateway")

    updated_node = await store.get_node(session_id, node_id)
    assert updated_node is not None
    updated_data = json.loads(updated_node["data_json"])
    assert updated_data.get("alias") == "DMZ-Web-Gateway"

    await store.close()


@pytest.mark.asyncio
async def test_learning_action_ssrf_rejection():
    store = GraphStore(":memory:")
    await store.initialize()
    _, session_id = await store.get_or_create_learning_sandbox()

    registry = ToolRegistry()
    manifest_data = {
        "meta": {"name": "nmap", "description": "Nmap scanner", "version": "1.0", "categories": ["Scanning"], "binary": "nmap"},
        "modes": {"learning": True, "power": True},
        "input": {"accepts": ["network.host"]},
        "output": {"produces": ["network.service"]},
    }
    registry.tools["nmap"] = {"manifest": Manifest(**manifest_data), "adapter": None}

    gateway = ActionGateway(registry, store)
    
    # Attempting to scan cloud metadata link-local endpoint
    import uuid
    malicious_action = ActionRequest(
        session_id=uuid.UUID(session_id),
        tool_name="nmap",
        params={"raw_flags": "-sV 169.254.169.254"},
        triggered_by=ActionSource.USER,
    )

    with pytest.raises(ActionValidationError) as exc_info:
        await gateway.validate_action(malicious_action)

    assert "cloud metadata" in str(exc_info.value).lower()
    await store.close()


@pytest.mark.asyncio
async def test_chat_prompt_allows_greetings():
    screen = LearningModeScreen()
    screen.active_tool = "nmap"
    screen.log_buffer = ["PORT 80/tcp open http\n"]

    # Test prompt generation for greetings
    question = "hello"
    context_block = ""
    tool_tag = screen.active_tool or "tool"
    if screen.log_buffer:
        cleaned_context = screen._strip_scanner_noise("".join(screen.log_buffer[-50:]))
        safe_context = cleaned_context.replace("</untrusted_scan_output>", "<\\/untrusted_scan_output>")
        context_block = (
            f'<untrusted_scan_output tool="{tool_tag}">\n{safe_context}\n</untrusted_scan_output>\n\n'
        )

    system_prompt = (
        f"You are CyGuide AI Tutor, an interactive cybersecurity instructor assisting a student in a learning lab.\n"
        f"Active tool in session: {tool_tag}.\n\n"
        f"{context_block}"
        "CORE BEHAVIOR & INTERACTION RULES:\n"
        "- If the student greets you (e.g., 'hello', 'hi', 'hey'), greet them back warmly and concisely.\n"
    )
    assert "greet them back warmly" in system_prompt
    assert question == "hello"


@pytest.mark.asyncio
async def test_learning_slash_commands_and_copy():
    """Verify that Ollama-style slash commands and copy actions execute correctly in Learning Mode."""
    from cyguide.app import CyGuideApp

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        app.learning_mode_tool = "nmap"
        app.switch_screen("learning_mode")
        await pilot.pause()

        screen = app.screen
        chat_input = screen.query_one("#chat_input")

        # 1. Test /help command
        chat_input.value = "/help"
        await screen.submit_chat_question().wait()
        assert "CyGuide Learning Mode Commands" in screen.explanation_buffer
        assert "/summary" in screen.explanation_buffer

        # 2. Test /model command
        chat_input.value = "/model"
        await screen.submit_chat_question().wait()
        assert "AI Tutor Status" in screen.explanation_buffer
        assert "nmap" in screen.explanation_buffer

        # 3. Test /recipes command
        chat_input.value = "/recipes"
        await screen.submit_chat_question().wait()
        assert "Available Recipes" in screen.explanation_buffer

        # 4. Test unknown slash command
        chat_input.value = "/unknown_foo"
        await screen.submit_chat_question().wait()
        assert "Unknown command: `/unknown_foo`" in screen.explanation_buffer

        # 5. Test /clear command
        chat_input.value = "/clear"
        await screen.submit_chat_question().wait()
        assert screen.explanation_buffer == ""

        # 6. Test copy actions
        screen.explanation_buffer = "Sample AI Explanation"
        screen.log_buffer = ["Raw log 1\n", "Raw log 2\n"]

        # action_copy_explanation
        screen.action_copy_explanation()
        # action_copy_output
        screen.action_copy_output()
        # action_copy_selection
        screen.action_copy_selection()


@pytest.mark.asyncio
async def test_learning_recipes_tab_and_circular_navigation():
    """Verify single-line recipe items, dedicated Recipes tab, recipe cards, and 3-tab navigation."""
    from cyguide.app import CyGuideApp
    from textual.widgets import TabbedContent, Button

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(120, 45)) as pilot:
        app.learning_mode_tool = "nmap"
        await app.push_screen("learning_mode")
        await pilot.pause()

        screen = app.screen
        tabs = screen.query_one("#learning_tabs", TabbedContent)

        # 1. Verify 3 tabs exist and initial active tab
        pane_ids = [pane.id for pane in tabs.query("TabPane")]
        assert "tab_explanation" in pane_ids
        assert "tab_output" in pane_ids
        assert "tab_recipes" in pane_ids
        assert tabs.active == "tab_explanation"

        # 2. Test 3-tab circular navigation
        screen.action_next_tab()
        await pilot.pause()
        assert tabs.active == "tab_output"

        screen.action_next_tab()
        await pilot.pause()
        assert tabs.active == "tab_recipes"

        screen.action_next_tab()
        await pilot.pause()
        assert tabs.active == "tab_explanation"

        screen.action_prev_tab()
        await pilot.pause()
        assert tabs.active == "tab_recipes"

        screen.action_prev_tab()
        await pilot.pause()
        assert tabs.active == "tab_output"

        screen.action_prev_tab()
        await pilot.pause()
        assert tabs.active == "tab_explanation"

        # 3. Verify sidebar recipe list items are clean and single-line
        recipe_list = screen.query_one("#recipe_list")
        assert len(recipe_list.children) > 0
        first_item = recipe_list.children[0]
        assert len(first_item.query(".recipe_name")) == 1
        assert len(first_item.query(".recipe_desc")) == 0

        # 4. Verify recipe cards inside #recipes_scroll in tab_recipes
        recipes_scroll = screen.query_one("#recipes_scroll")
        recipe_cards = recipes_scroll.query(".recipe_card")
        assert len(recipe_cards) == len(recipe_list.children)

        # 5. Test loading recipe via button in tab_recipes
        tabs.active = "tab_recipes"
        await pilot.pause()
        load_btn = screen.query_one("#load_recipe_0", Button)
        load_btn.press()
        await pilot.pause()
        assert screen.query_one("#flags_input").value == "-sV"
        assert tabs.active == "tab_recipes"

        # 6. Test /recipes slash command switches to tab_recipes
        chat_input = screen.query_one("#chat_input")
        chat_input.value = "/recipes"
        await screen.submit_chat_question().wait()
        await pilot.pause()
        assert tabs.active == "tab_recipes"


@pytest.mark.asyncio
async def test_learning_ask_ai_and_run_buttons():
    """Verify sidebar Ask AI button, recipe card Ask AI & Run buttons, and run/stop button toggling."""
    from cyguide.app import CyGuideApp
    from textual.widgets import Button, TabbedContent

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test(size=(120, 45)) as pilot:
        app.learning_mode_tool = "nmap"
        await app.push_screen("learning_mode")
        await pilot.pause()

        screen = app.screen
        tabs = screen.query_one("#learning_tabs", TabbedContent)

        # 1. Sidebar Ask AI button verification
        sidebar_ask = screen.query_one("#sidebar_ask_btn", Button)
        run_btn = screen.query_one("#run_btn", Button)
        stop_btn = screen.query_one("#stop_btn", Button)

        assert sidebar_ask is not None
        assert "ASK AI" in str(sidebar_ask.label)
        assert run_btn.display is True
        assert sidebar_ask.display is True
        assert stop_btn.display is False

        # 2. Test clicking sidebar Ask AI button switches to tab_explanation and calls query_ai_tutor
        tabs.active = "tab_output"
        await pilot.pause()
        sidebar_ask.press()
        await pilot.pause()
        assert tabs.active == "tab_explanation"
        assert "Explain command:" in screen.explanation_buffer

        # 3. Recipe cards have both [✦ ASK AI] and [▶ RUN] buttons
        tabs.active = "tab_recipes"
        await pilot.pause()

        ask_recipe_0 = screen.query_one("#ask_recipe_0", Button)
        load_recipe_0 = screen.query_one("#load_recipe_0", Button)

        assert ask_recipe_0 is not None
        assert "ASK AI" in str(ask_recipe_0.label)
        assert load_recipe_0 is not None
        assert "RUN" in str(load_recipe_0.label)
        assert "recipe_ask_btn" in ask_recipe_0.classes
        assert "recipe_run_btn" in load_recipe_0.classes

        # 4. Test clicking recipe card [✦ ASK AI] button
        ask_recipe_0.press()
        await pilot.pause()
        assert tabs.active == "tab_explanation"
        assert "Explain recipe:" in screen.explanation_buffer

        # 5. Test button state toggling during scan and after reset
        screen.reset_ui_after_run()
        assert run_btn.display is True
        assert sidebar_ask.display is True
        assert stop_btn.display is False

        # Trigger simulated scan UI state
        screen.scan_in_progress = True
        run_btn.display = False
        sidebar_ask.display = False
        stop_btn.display = True
        assert run_btn.display is False
        assert sidebar_ask.display is False
        assert stop_btn.display is True

        screen.reset_ui_after_run()
        assert run_btn.display is True
        assert sidebar_ask.display is True
        assert stop_btn.display is False

        # 6. Verify tool_summary_header is hidden in sidebar (as description lives in explanation pane)
        tool_summary = screen.query_one("#tool_summary_header")
        assert tool_summary.display is False

        # 7. Test shrunk sidebar (width 20) keeps BOTH buttons visible and within bounds
        pane = screen.query_one("#lesson_config_pane")
        pane.styles.width = 20
        screen.refresh(layout=True)
        await pilot.pause()

        pane_right = pane.region.x + pane.region.width
        pane_bottom = pane.region.y + pane.region.height

        assert sidebar_ask.region.x + sidebar_ask.region.width <= pane_right
        assert run_btn.region.x + run_btn.region.width <= pane_right
        assert run_btn.region.y + run_btn.region.height <= pane_bottom
        assert sidebar_ask.region.width > 0
        assert run_btn.region.width > 0

        # 8. Test clicking ask_recipe_0 while on tab_recipes cleanly stays on tab_explanation (no snap-back)
        tabs.active = "tab_recipes"
        await pilot.pause()
        assert tabs.active == "tab_recipes"

        tab_changes = []
        tabs.watch(tabs, "active", lambda old, new: tab_changes.append((old, new)))

        await pilot.click("#ask_recipe_0")
        await pilot.pause()
        await pilot.pause()

        assert tabs.active == "tab_explanation"
        assert ("tab_explanation", "tab_recipes") not in tab_changes

        # 9. Test recipe card button updates to STOP on run and toggles STOP/RUN correctly
        tabs.active = "tab_recipes"
        await pilot.pause()
        recipe_btn_0 = screen.query_one("#load_recipe_0", Button)
        recipe_btn_1 = screen.query_one("#load_recipe_1", Button)
        ask_recipe_0 = screen.query_one("#ask_recipe_0", Button)

        assert "RUN" in str(recipe_btn_0.label)
        assert recipe_btn_0.has_class("recipe_run_btn")
        assert not recipe_btn_0.has_class("recipe_stop_btn")

        # Simulate scan start with recipe 0 active
        screen.active_recipe_idx = 0
        screen.scan_in_progress = True
        # Apply run_scan UI setup
        for btn in screen.query(".recipe_run_btn, .recipe_stop_btn"):
            if btn.id and btn.id.startswith("load_recipe_"):
                idx_str = btn.id.replace("load_recipe_", "")
                if idx_str.isdigit() and int(idx_str) == 0:
                    btn.label = "■ STOP"
                    btn.remove_class("recipe_run_btn")
                    btn.add_class("recipe_stop_btn")
                    btn.disabled = False
                else:
                    btn.disabled = True
        for ab in screen.query(".recipe_ask_btn"):
            ab.disabled = True

        assert "STOP" in str(recipe_btn_0.label)
        assert recipe_btn_0.has_class("recipe_stop_btn")
        assert not recipe_btn_0.has_class("recipe_run_btn")
        assert recipe_btn_0.disabled is False
        assert recipe_btn_1.disabled is True
        assert ask_recipe_0.disabled is True

        # When stopped or completed, reset_ui_after_run restores buttons
        screen.reset_ui_after_run()
        assert "RUN" in str(recipe_btn_0.label)
        assert recipe_btn_0.has_class("recipe_run_btn")
        assert not recipe_btn_0.has_class("recipe_stop_btn")
        assert recipe_btn_0.disabled is False
        assert recipe_btn_1.disabled is False
        assert ask_recipe_0.disabled is False
        assert screen.active_recipe_idx is None

        # 10. Test AI explanation toggle button in tab_explanation
        tabs.active = "tab_explanation"
        await pilot.pause()
        toggle_btn = screen.query_one("#toggle_ai_explanation_btn", Button)
        assert toggle_btn.has_class("ai_toggle_on")
        assert "ON" in str(toggle_btn.label)
        assert screen.ai_explanations_enabled is True

        # Click toggle button to turn off
        await pilot.click("#toggle_ai_explanation_btn")
        await pilot.pause()
        assert screen.ai_explanations_enabled is False
        assert toggle_btn.has_class("ai_toggle_off")
        assert "OFF" in str(toggle_btn.label)

        # Test querying AI when disabled skips LLM, preserves buffer intact, and updates status label
        prev_buffer = screen.explanation_buffer
        await screen.query_ai_tutor("What is nmap?").wait()
        await pilot.pause()
        assert screen.explanation_buffer == prev_buffer, "Must not wipe or alter explanation buffer when AI is disabled"
        status_lbl = screen.query_one("#explanation_status_label")
        assert "OFF" in str(status_lbl.render())

        # Click toggle button to turn back on
        toggle_btn.press()
        await pilot.pause()
        assert screen.ai_explanations_enabled is True
        assert toggle_btn.has_class("ai_toggle_on")
        assert "ON" in str(toggle_btn.label)

        # 11. Test that running a scan while AI is OFF preserves previous explanation and shows warning banner
        screen.explanation_buffer = "### Important Previous Explanation"
        toggle_btn.press()
        await pilot.pause()
        assert screen.ai_explanations_enabled is False

        await screen.run_scan().wait()
        await pilot.pause(0.2)
        assert screen.explanation_buffer == "### Important Previous Explanation", "Previous explanation must NOT be wiped!"
        status_lbl = screen.query_one("#explanation_status_label")
        assert "OFF" in str(status_lbl.render())

        # 12. Test that running a scan while AI is ON ALSO preserves previous explanation
        toggle_btn.press()
        await pilot.pause()
        assert screen.ai_explanations_enabled is True
        screen.explanation_buffer = "### Retained History From Previous Activity"
        await screen.run_scan().wait()
        await pilot.pause(0.2)
        assert "### Retained History From Previous Activity" in screen.explanation_buffer, (
            "Previous explanation must NOT be wiped when AI is ON!"
        )
        assert f"Run #{screen.run_count}" in screen.explanation_buffer

