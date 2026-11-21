# codeguard: disable-file[UNTRACKED_SCHEMA_MUTATION]
"""Unit and integration tests for Learning Mode .cyglab checkpoints."""

import os
import stat

import aiosqlite
import pytest

from cyguide.engine.learning import LearningSession
from cyguide.engine.store import GraphStore
from cyguide.ui.screens.checkpoint_modals import LoadCheckpointModal, SaveCheckpointModal


@pytest.mark.asyncio
async def test_learning_session_save_and_load_checkpoint(tmp_path):
    """Verify that save_checkpoint creates a valid 0o600 .cyglab SQLite archive and load_checkpoint restores it."""
    db_file = str(tmp_path / "main.db")
    store = GraphStore(db_file)
    await store.initialize()

    # Create workspace and session
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Lab")

    # Insert a test node and event
    from cyguide.schemas.network import NetworkHost

    host = NetworkHost.create(ip="10.0.0.1")
    await store.upsert_finding(sess_id, host)
    await store.log_audit_event(sess_id, "scan", "Port scan executed", status="SUCCESS")

    session = LearningSession(
        store=store,
        registry=None,
        execution=None,
        session_id=sess_id,
        workspace_id=ws_id,
    )
    session.active_tool = "nmap"
    session.active_recipe_idx = 1
    session.log_buffer = ["Nmap starting...\n", "Discovered 80/tcp open\n"]
    session.explanation_buffer = "### Nmap Service Scan Analysis\nPort 80 is open."
    session.notes = "Found port 80. Need to check HTTP server."

    chk_file = str(tmp_path / "nmap_checkpoint.cyglab")
    saved_path = await session.save_checkpoint(
        checkpoint_path=chk_file,
        target="10.0.0.1",
        flags="-sV -p 80",
        model_name="gemini-2.0-flash",
    )

    assert saved_path == chk_file
    assert os.path.exists(chk_file)

    # 1. Verify strict 0o600 file permissions
    st = os.stat(chk_file)
    mode = stat.S_IMODE(st.st_mode)
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    # 2. Verify list_checkpoints discovers the archive
    checkpoints = LearningSession.list_checkpoints(str(tmp_path))
    assert len(checkpoints) == 1
    item = checkpoints[0]
    assert item["tool_name"] == "nmap"
    assert item["target"] == "10.0.0.1"
    assert item["recipe_idx"] == 1
    assert "Found port 80" in item["notes_preview"]
    assert item["filename"] == "nmap_checkpoint.cyglab"

    # 3. Create fresh session and restore from checkpoint
    restore_store_file = str(tmp_path / "restored.db")
    restore_store = GraphStore(restore_store_file)
    await restore_store.initialize()

    restore_session = LearningSession(
        store=restore_store,
        registry=None,
        execution=None,
    )

    data = await restore_session.load_checkpoint(chk_file)

    assert data["tool_name"] == "nmap"
    assert data["recipe_idx"] == 1
    assert data["target"] == "10.0.0.1"
    assert data["flags"] == "-sV -p 80"
    assert data["model_name"] == "gemini-2.0-flash"
    assert data["notes"] == "Found port 80. Need to check HTTP server."
    assert "Port 80 is open." in data["explanation_buffer"]
    assert len(data["log_buffer"]) == 2

    # Verify internal session properties were restored
    assert restore_session.active_tool == "nmap"
    assert restore_session.active_recipe_idx == 1
    assert restore_session.notes == "Found port 80. Need to check HTTP server."
    assert restore_session.log_buffer == ["Nmap starting...\n", "Discovered 80/tcp open\n"]

    # Verify graph findings were imported into restore_store
    nodes = await restore_store.get_all_nodes(sess_id)
    assert len(nodes) == 1
    assert nodes[0]["schema_type"] == "network.host"

    await store.close()
    await restore_store.close()


@pytest.mark.asyncio
async def test_learning_session_multi_tool_checkpoint(tmp_path):
    """Verify universal multi-tool session persistence across nmap and gobuster."""
    from cyguide.schemas.network import NetworkHost
    from cyguide.schemas.web import WebEndpoint

    db_file = str(tmp_path / "multi_tool_main.db")
    store = GraphStore(db_file)
    await store.initialize()

    ws_id = await store.create_workspace("Universal WS")
    sess_id = await store.create_session(ws_id, "Universal Lab")

    session = LearningSession(
        store=store,
        registry=None,
        execution=None,
        session_id=sess_id,
        workspace_id=ws_id,
    )

    # 1. First tool: nmap
    session.active_tool = "nmap"
    session.tools_used.add("nmap")
    session.tool_configs["nmap"] = {
        "target": "10.0.0.5",
        "flags": "-sV -p 80,443",
        "recipe_idx": 0,
    }
    host = NetworkHost.create(ip="10.0.0.5")
    await store.upsert_finding(sess_id, host)
    session.log_buffer = ["[nmap] Discovered 80/tcp and 443/tcp open\n"]
    session.explanation_buffer = "Nmap discovered web services on 80 and 443."

    # 2. Second tool: gobuster
    session.active_tool = "gobuster"
    session.tools_used.add("gobuster")
    session.tool_configs["gobuster"] = {
        "target": "http://10.0.0.5",
        "flags": "dir -u http://10.0.0.5 -w common.txt",
        "recipe_idx": 1,
    }
    endpoint = WebEndpoint.create(
        url="http://10.0.0.5/admin",
        host_ip="10.0.0.5",
        port=80,
        status_code=200,
    )
    await store.upsert_finding(sess_id, endpoint)
    session.log_buffer.append("[gobuster] Found /admin (Status: 200)\n")
    session.explanation_buffer += "\nGobuster discovered /admin endpoint."
    session.notes = "10.0.0.5 has port 80 open. Discovered /admin portal."

    # 3. Save universal checkpoint
    chk_file = str(tmp_path / "lab_multi_tool.cyglab")
    await session.save_checkpoint(
        checkpoint_path=chk_file,
        target="http://10.0.0.5",
        flags="dir -u http://10.0.0.5 -w common.txt",
        model_name="claude-3.5-sonnet",
    )

    # 4. Verify discovery via list_checkpoints
    checkpoints = LearningSession.list_checkpoints(str(tmp_path))
    assert len(checkpoints) >= 1
    chk_entry = next(c for c in checkpoints if c["filename"] == "lab_multi_tool.cyglab")
    assert sorted(chk_entry["tools_used"]) == ["gobuster", "nmap"]
    assert chk_entry["active_tool"] == "gobuster"
    assert chk_entry["nodes_count"] >= 2
    assert "Discovered /admin" in chk_entry["notes_preview"]

    # 5. Restore into completely fresh store and session
    restore_store_file = str(tmp_path / "multi_restored.db")
    restore_store = GraphStore(restore_store_file)
    await restore_store.initialize()

    restore_session = LearningSession(
        store=restore_store,
        registry=None,
        execution=None,
    )
    loaded_data = await restore_session.load_checkpoint(chk_file)

    assert sorted(loaded_data["tools_used"]) == ["gobuster", "nmap"]
    assert restore_session.tools_used == {"gobuster", "nmap"}
    assert "nmap" in restore_session.tool_configs
    assert restore_session.tool_configs["nmap"]["target"] == "10.0.0.5"
    assert "gobuster" in restore_session.tool_configs
    assert restore_session.tool_configs["gobuster"]["target"] == "http://10.0.0.5"
    assert restore_session.active_tool == "gobuster"
    assert len(restore_session.log_buffer) == 2
    assert "Discovered /admin portal" in restore_session.notes

    # Verify both findings restored into new store
    restored_nodes = await restore_store.get_all_nodes(sess_id)
    assert len(restored_nodes) >= 2
    node_types = {n["schema_type"] for n in restored_nodes}
    assert "network.host" in node_types
    assert "web.endpoint" in node_types

    await store.close()
    await restore_store.close()


@pytest.mark.asyncio
async def test_learning_checkpoint_error_handling(tmp_path):
    """Verify appropriate error handling for missing and corrupt checkpoint files."""
    session = LearningSession(store=None, registry=None, execution=None)

    with pytest.raises(FileNotFoundError):
        await session.load_checkpoint(str(tmp_path / "non_existent.cyglab"))

    # Corrupt archive (not SQLite)
    corrupt_file = str(tmp_path / "corrupt.cyglab")
    with open(corrupt_file, "w") as f:
        f.write("corrupted content")

    with pytest.raises((ValueError, aiosqlite.DatabaseError)):
        await session.load_checkpoint(corrupt_file)


@pytest.mark.asyncio
async def test_learning_ui_checkpoint_flow(tmp_path):
    """Verify Learning Mode UI save/load checkpoint buttons, modals, and hotkeys."""
    from textual.widgets import Button, Input, TextArea

    from cyguide.app import CyGuideApp

    checkpoints_dir = str(tmp_path / "checkpoints")
    os.makedirs(checkpoints_dir, mode=0o700, exist_ok=True)

    app = CyGuideApp(db_path=":memory:")
    app.checkpoints_dir = checkpoints_dir

    async with app.run_test(size=(120, 45)) as pilot:
        app.learning_mode_tool = "nmap"
        await app.push_screen("learning_mode")
        await pilot.pause()

        screen = app.screen

        # 1. Verify Save and Load buttons exist in UI, have clean icons/tooltips, and adapt responsively
        save_btn = screen.query_one("#save_checkpoint_btn", Button)
        load_btn = screen.query_one("#load_checkpoint_btn", Button)
        reset_btn = screen.query_one("#reset_session_btn", Button)
        assert save_btn is not None
        assert load_btn is not None
        assert reset_btn is not None
        assert str(save_btn.label) in ("⤓", "⤓ SAVE")
        assert str(load_btn.label) in ("⤒", "⤒ LOAD")
        assert str(reset_btn.label) in ("↻", "↻ RESET")
        assert save_btn.tooltip is None
        assert load_btn.tooltip is None
        assert reset_btn.tooltip is None

        # Verify responsive behavior: wide pane expands labels, standard pane shows SAVE/LOAD, narrow pane keeps icons
        screen._sync_sidebar_responsive_layout(50)
        assert "SAVE" in str(save_btn.label)
        assert "LOAD" in str(load_btn.label)
        assert "RESET" in str(reset_btn.label)

        screen._sync_sidebar_responsive_layout(32)
        assert "SAVE" in str(save_btn.label)
        assert "LOAD" in str(load_btn.label)
        assert str(reset_btn.label) == "↻"

        screen._sync_sidebar_responsive_layout(22)
        assert str(save_btn.label) == "⤓"
        assert str(load_btn.label) == "⤒"
        assert str(reset_btn.label) == "↻"

        # 1b. Verify welcome text is in raw output terminal, and explanation_text has tutor prompt
        from cyguide.ui.widgets import TerminalStreamPane

        terminal = screen.query_one("#raw_output_terminal", TerminalStreamPane)
        assert "NMAP" in terminal.get_text()
        assert "Quick Start Guide" in terminal.get_text()

        # 1c. Test Ctrl+B toggles sidebar
        sidebar = screen.query_one("#lesson_config_pane")
        assert not sidebar.has_class("collapsed")
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert sidebar.has_class("collapsed")
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert not sidebar.has_class("collapsed")

        # 1d. Test Ctrl+Alt+B toggles Copilot
        copilot = screen.query_one("#learning_copilot_pane")
        assert not copilot.has_class("hidden_sidebar")
        await pilot.press("ctrl+alt+b")
        await pilot.pause()
        assert copilot.has_class("hidden_sidebar")
        await pilot.press("ctrl+alt+b")
        await pilot.pause()
        assert not copilot.has_class("hidden_sidebar")

        # 2. Populate target, flags, and notes
        screen.query_one("#target_input", Input).value = "192.168.1.50"
        screen.query_one("#flags_input", Input).value = "-sS -T4"
        notes_area = screen.query_one("#learning_scratchpad_textarea", TextArea)
        notes_area.load_text("Student Lab 1: Found open ports.")
        screen.explanation_buffer = "### AI Analysis: SYN Stealth Scan\nFast scan."
        screen.log_buffer = ["Nmap 7.94 scan initiated...\n", "Host is up (0.001s latency).\n"]

        # 3. Click Save Checkpoint button -> Opens SaveCheckpointModal
        save_btn.press()
        await pilot.pause(0.2)

        save_modal = app.screen
        assert isinstance(save_modal, SaveCheckpointModal)
        assert "nmap" in save_modal.tool_name
        assert save_modal.styles.align == ("center", "middle")
        save_card = save_modal.query_one("#checkpoint_modal_card")
        assert save_card.region.width >= 70
        assert save_modal.query_one("#checkpoint_confirm_btn").visible is True
        assert save_modal.query_one("#checkpoint_cancel_btn").visible is True

        # Confirm save with custom name
        name_input = save_modal.query_one("#checkpoint_name_input", Input)
        name_input.value = "my_custom_lab.cyglab"
        save_modal.query_one("#checkpoint_confirm_btn", Button).press()
        await pilot.pause(0.5)

        # Verify file was created in checkpoints directory
        expected_file = os.path.join(checkpoints_dir, "my_custom_lab.cyglab")
        assert os.path.exists(expected_file)
        assert stat.S_IMODE(os.stat(expected_file).st_mode) == 0o600

        # 4. Clear state in UI to simulate starting fresh session
        screen.query_one("#target_input", Input).value = "127.0.0.1"
        screen.query_one("#flags_input", Input).value = ""
        notes_area.load_text("")
        screen.clear_output()
        screen.clear_explanation()

        # 5. Click Load Checkpoint button -> Opens LoadCheckpointModal
        load_btn.press()
        await pilot.pause(0.5)

        load_modal = app.screen
        assert isinstance(load_modal, LoadCheckpointModal)
        assert load_modal.styles.align == ("center", "middle")
        load_card = load_modal.query_one("#checkpoint_modal_card")
        assert load_card.region.x > 0
        assert load_card.region.y > 0
        assert load_card.region.width >= 80
        assert load_modal.query_one("#checkpoint_load_confirm_btn").visible is True
        assert load_modal.query_one("#checkpoint_load_cancel_btn").visible is True
        assert len(load_modal.checkpoints) >= 1
        assert load_modal.checkpoints[0]["filename"] == "my_custom_lab.cyglab"

        # Select and load
        load_modal.query_one("#checkpoint_load_confirm_btn", Button).press()
        await pilot.pause(0.5)

        # 6. Verify restored state in UI
        assert screen.query_one("#target_input", Input).value == "192.168.1.50"
        assert screen.query_one("#flags_input", Input).value == "-sS -T4"
        assert "Student Lab 1" in notes_area.text
        assert "SYN Stealth Scan" in screen.explanation_buffer
        assert len(screen.log_buffer) == 2


def test_terminal_stream_pane_write_lines():
    """Verify TerminalStreamPane write_line and write_lines methods."""
    from cyguide.ui.widgets import TerminalStreamPane

    pane = TerminalStreamPane()
    pane.write_line("Line 1")
    pane.write_line("Line 2\n")
    pane.write_lines(["Line 3", "Line 4\n"])
    text = pane.get_text()
    assert text == "Line 1\nLine 2\nLine 3\nLine 4"


@pytest.mark.asyncio
async def test_learning_screen_sidebar_graph_toggle():
    """Verify toggling between recipes list and entity knowledge graph in learning mode."""
    from cyguide.app import CyGuideApp
    from cyguide.ui.screens.learning import LearningModeScreen

    app = CyGuideApp()
    async with app.run_test(size=(140, 40)) as pilot:
        screen = LearningModeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        recipes_btn = screen.query_one("#toggle_recipes_btn")
        graph_btn = screen.query_one("#toggle_graph_btn")
        recipe_list = screen.query_one("#recipe_list")
        browser = screen.query_one("#learning_entity_browser")

        assert "active_view" in recipes_btn.classes
        assert "hidden" in browser.classes
        assert "hidden" not in recipe_list.classes

        # Toggle via button press
        graph_btn.press()
        await pilot.pause()

        assert "active_view" in graph_btn.classes
        assert "hidden" not in browser.classes
        assert "hidden" in recipe_list.classes

        # Toggle back via shortcut
        await pilot.press("ctrl+g")
        await pilot.pause()

        assert "active_view" in recipes_btn.classes
        assert "hidden" in browser.classes
        assert "hidden" not in recipe_list.classes


@pytest.mark.asyncio
async def test_learning_screen_reset_session_shortcut():
    """Verify reset session via ctrl+alt+r shortcut and confirmation dialog."""
    from cyguide.app import CyGuideApp
    from cyguide.ui.dialogs import ConfirmationDialog
    from cyguide.ui.screens.learning import LearningModeScreen

    app = CyGuideApp()
    async with app.run_test(size=(140, 40)) as pilot:
        screen = LearningModeScreen()
        await app.push_screen(screen)
        await pilot.pause()

        # Seed state
        screen.session.log_buffer = ["Line 1\n", "Line 2\n"]
        screen.session.explanation_buffer = "Scan explanation text"
        screen.session.notes = "Initial notes"
        screen.query_one("#learning_scratchpad_textarea").load_text("Initial notes")

        # Press ctrl+alt+r shortcut
        await pilot.press("ctrl+alt+r")
        await pilot.pause()

        # Modal confirmation dialog should be displayed
        dialog = app.screen
        assert isinstance(dialog, ConfirmationDialog)
        assert "Reset lab session" in dialog.message

        # Cancel first to test cancellation
        dialog.query_one("#cancel").press()
        await pilot.pause()

        # State should be unchanged
        assert len(screen.session.log_buffer) == 2
        assert screen.session.explanation_buffer == "Scan explanation text"

        # Now trigger and confirm reset
        await pilot.press("ctrl+alt+r")
        await pilot.pause()
        dialog = app.screen
        assert isinstance(dialog, ConfirmationDialog)
        dialog.query_one("#confirm").press()
        await pilot.pause(0.5)

        # State must be completely reset
        assert screen.session.log_buffer == []
        assert screen.session.explanation_buffer == ""
        assert screen.session.notes == ""
        assert screen.query_one("#learning_scratchpad_textarea").text == ""
        r = screen.query_one("#explanation_text").render()
        assert "AI Copilot Tutor Ready" in r._renderable.markup


@pytest.mark.asyncio
async def test_learning_session_legacy_checkpoint_compatibility(tmp_path):
    """Verify that older checkpoints without primary_target column load cleanly and upgrade gracefully."""
    import sqlite3

    legacy_chk = str(tmp_path / "legacy_lab.cyglab")
    conn = sqlite3.connect(legacy_chk)
    conn.execute(
        """
        CREATE TABLE learning_state (
            session_id TEXT PRIMARY KEY,
            tool_name TEXT,
            recipe_idx INTEGER,
            target TEXT,
            flags TEXT,
            stdout_log TEXT,
            explanation_buffer TEXT,
            notes TEXT,
            model_name TEXT,
            saved_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO learning_state (
            session_id, tool_name, recipe_idx, target, flags, stdout_log, explanation_buffer, notes, model_name, saved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "11111111-2222-3333-4444-555555555555",
            "ffuf",
            2,
            "http://example.com/api",
            "-w /usr/share/wordlists/dirb/common.txt",
            '["Scanning http://example.com/api...\\n"]',
            "### Ffuf Analysis\\nFuzzing API endpoint",
            "Legacy lab notes",
            "ollama:mistral",
            "2026-11-20T10:00:00Z",
        ),
    )
    conn.commit()
    conn.close()

    # 1. list_checkpoints should handle legacy column names
    cps = LearningSession.list_checkpoints(str(tmp_path))
    assert len(cps) == 1
    assert cps[0]["target"] == "http://example.com/api"
    assert cps[0]["active_tool"] == "ffuf"

    # 2. load_checkpoint should load cleanly without 'no such column' errors
    session = LearningSession(store=None, registry=None, execution=None)
    data = await session.load_checkpoint(legacy_chk)
    assert data["target"] == "http://example.com/api"
    assert data["primary_target"] == "http://example.com/api"
    assert data["active_tool"] == "ffuf"
    assert data["notes"] == "Legacy lab notes"

    # 3. re-saving into the same checkpoint upgrades the table schema without error
    await session.save_checkpoint(
        legacy_chk, target="http://example.com/api", flags="-w wordlist.txt"
    )
    reloaded = await session.load_checkpoint(legacy_chk)
    assert reloaded["primary_target"] == "http://example.com/api"
