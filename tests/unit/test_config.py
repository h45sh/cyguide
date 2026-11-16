"""Unit tests for CyGuide configuration options and Command Palette integration."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Button, Input, Label, Switch

from cyguide.app import CyGuideApp, CyGuideCommandPalette
from cyguide.engine.explainer import ExplanationTutor
from cyguide.ui.screens.config_modal import (
    CloudAPIConfigProvider,
    ConfigModal,
    ConfigProvider,
    DatabaseConfigProvider,
    OllamaConfigProvider,
    ToolsConfigProvider,
)


def test_system_commands_single_config_entry(tmp_path):
    """Verify that get_system_commands has only ONE consolidated Config entry, NO Toggle Sidebar, and NO duplicate config options."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)
    mock_screen = MagicMock()

    commands = list(app.get_system_commands(mock_screen))
    titles = [cmd.title for cmd in commands]

    # Verify single consolidated Config option
    config_commands = [t for t in titles if "Config" in t]
    assert len(config_commands) == 1
    assert config_commands[0] == "Config"

    # Verify Toggle Sidebar has been completely removed
    assert not any("Toggle Sidebar" in t for t in titles)

    # Verify duplicate entries have been eliminated from main palette
    assert not any("Config: Open Settings Dialog" in t for t in titles)
    assert not any("Config: Ollama Backend" in t for t in titles)
    assert not any("Config: LLM Model" in t for t in titles)
    assert not any("Config: API Keys & Cloud AI" in t for t in titles)
    assert not any("Config: Database Path" in t for t in titles)
    assert not any("Config: Tools Directory" in t for t in titles)

    # Verify exact conventional command order (6 streamlined items)
    assert any("Toggle Animations" in t for t in titles)
    assert any("Tool Health" in t for t in titles)
    assert "Config" in titles
    assert "Hotkeys" in titles
    assert "Screenshot" in titles
    assert titles[-1] == "Quit"

    # Verify legacy Textual 'Keys' command is replaced by our 'Hotkeys'
    assert "Keys" not in titles


@pytest.mark.asyncio
async def test_command_palette_exact_order(tmp_path):
    """Verify Command Palette displays the streamlined 6-item conventional menu order without Theme or Toggle Sidebar."""
    from textual.command import CommandList

    db_file = str(tmp_path / "test_palette_order.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        cl = app.screen.query_one(CommandList)
        prefixes = [
            "Toggle Animations",
            "Tool Health",
            "Config",
            "Hotkeys",
            "Screenshot",
            "Quit",
        ]
        prompts = []
        for opt in cl.options:
            line = str(opt.prompt).split("\n")[0]
            matched = next((p for p in prefixes if line.startswith(p)), line)
            prompts.append(matched)

        assert prompts == prefixes


@pytest.mark.asyncio
async def test_legacy_help_panel_replaced_by_shortcuts_dialog(tmp_path):
    """Verify action_show_help_panel opens the F1 Shortcuts dialog instead of Textual's legacy half window."""
    db_file = str(tmp_path / "test_help_panel.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_help_panel()
        await pilot.pause()
        assert type(app.screen).__name__ == "ShortcutsDialog"


@pytest.mark.asyncio
async def test_shortcuts_dialog_f1_toggle_and_holding_resilience(tmp_path):
    """Verify F1 toggles ShortcutsDialog open and closed, and holding F1 does not cause ScreenStackError."""
    from textual import events

    db_file = str(tmp_path / "test_f1_toggle.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # 1. Press F1 to open
        await pilot.press("f1")
        assert type(app.screen).__name__ == "ShortcutsDialog"

        # 2. Press F1 again to close (fast toggle)
        await pilot.pause(0.3)
        await pilot.press("f1")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "DashboardScreen"

        # 3. Press F1 to reopen
        await pilot.pause(0.3)
        await pilot.press("f1")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "ShortcutsDialog"

        # 4. Simulate rapid key repeat from holding F1
        for _ in range(25):
            app.screen.post_message(events.Key("f1", None))
        await pilot.pause(0.05)
        assert len(app._screen_stack) >= 2

        # 5. Simulate rapid key repeat from holding Escape
        if type(app.screen).__name__ == "ShortcutsDialog":
            for _ in range(20):
                app.screen.post_message(events.Key("escape", None))
            await pilot.pause(0.05)
        assert type(app.screen).__name__ == "DashboardScreen"
        assert len(app._screen_stack) == 2


def test_markdown_amber_warm_gold_theme():
    """Verify console markdown theme uses Matte Warm Gold / Amber palette instead of conflicting sky blue."""
    app = CyGuideApp(db_path=":memory:")
    assert "c89b3c" in str(app.console.get_style("markdown.h1").color)
    assert "c89b3c" in str(app.console.get_style("markdown.h2").color)
    assert "b4832e" in str(app.console.get_style("markdown.h3").color)
    assert "d5c4a1" in str(app.console.get_style("markdown.code").color)


@pytest.mark.asyncio
async def test_config_provider_hierarchy(tmp_path):
    """Verify ConfigProvider discover presents clean top-level categories without clutter."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file, use_ollama=True)
    mock_screen = MagicMock()
    mock_screen.app = app
    provider = ConfigProvider(mock_screen)
    provider._app = app

    hits = [hit async for hit in provider.discover()]
    displays = [str(h.prompt) for h in hits]

    # Clean hierarchical categories
    assert any("Open Full Configuration Panel" in d for d in displays)
    assert any("Ollama (Local LLM)" in d and "ON" in d for d in displays)
    assert any("API Keys & Cloud AI" in d for d in displays)
    assert any("Database Settings" in d for d in displays)
    assert any("Tools Directory" in d for d in displays)
    assert any("Reset Configuration to Defaults" in d for d in displays)

    # Verify exactly 6 category items in discover (no duplicates)
    assert len(displays) == 6


@pytest.mark.asyncio
async def test_config_provider_deep_search(tmp_path):
    """Verify that searching inside ConfigProvider matches specific parameters across categories."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)
    mock_screen = MagicMock()
    mock_screen.app = app
    provider = ConfigProvider(mock_screen)
    provider._app = app

    # Search for "model" matches both category and individual options
    model_hits = [h async for h in provider.search("model")]
    assert len(model_hits) >= 2

    # Search for "database"
    db_hits = [h async for h in provider.search("database")]
    assert len(db_hits) >= 1

    # Search for "tools"
    tools_hits = [h async for h in provider.search("tools")]
    assert len(tools_hits) >= 1


@pytest.mark.asyncio
async def test_nested_sub_palette_providers(tmp_path):
    """Verify individual nested sub-palette providers expose their respective parameters."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(
        db_path=db_file, use_ollama=True, ollama_model="llama3", tools_dir="extra_tools"
    )
    mock_screen = MagicMock()
    mock_screen.app = app

    # 1. Ollama Sub-palette
    ollama_provider = OllamaConfigProvider(mock_screen)
    ollama_hits = [h async for h in ollama_provider.discover()]
    ollama_displays = [str(h.prompt) for h in ollama_hits]
    assert any("Toggle Local LLM" in d and "ON" in d for d in ollama_displays)
    assert any("Ollama Model" in d and "llama3" in d for d in ollama_displays)
    assert any("Ollama Base URL" in d for d in ollama_displays)

    # 2. Cloud API Sub-palette
    cloud_provider = CloudAPIConfigProvider(mock_screen)
    cloud_hits = [h async for h in cloud_provider.discover()]
    cloud_displays = [str(h.prompt) for h in cloud_hits]
    assert any("API Key" in d for d in cloud_displays)
    assert any("Provider Type" in d for d in cloud_displays)
    assert any("Cloud Model" in d for d in cloud_displays)
    assert any("API Base URL" in d for d in cloud_displays)

    # 3. Database Sub-palette
    db_provider = DatabaseConfigProvider(mock_screen)
    db_hits = [h async for h in db_provider.discover()]
    db_displays = [str(h.prompt) for h in db_hits]
    assert any("Database Path" in d and "test.db" in d for d in db_displays)

    # 4. Tools Sub-palette
    tools_provider = ToolsConfigProvider(mock_screen)
    tools_hits = [h async for h in tools_provider.discover()]
    tools_displays = [str(h.prompt) for h in tools_hits]
    assert any("Tools Directory Path" in d and "extra_tools" in d for d in tools_displays)


@pytest.mark.asyncio
async def test_nested_palette_navigation(tmp_path):
    """Verify parent_action callback is executed on left arrow in nested sub-palettes."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)

    parent_called = False

    def mock_parent_action():
        nonlocal parent_called
        parent_called = True

    palette = CyGuideCommandPalette(
        providers=[OllamaConfigProvider],
        is_sub_palette=True,
        parent_action=mock_parent_action,
    )
    palette._app = app
    palette.dismiss = MagicMock()
    palette.handle_left_arrow()

    assert parent_called is True
    assert palette.dismiss.called


@pytest.mark.asyncio
async def test_config_modal_save_and_apply(tmp_path):
    """Verify saving settings in ConfigModal updates app state, env, and settings.json."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        # Modify values
        modal.query_one("#cfg_use_ollama", Switch).value = True
        modal.query_one("#cfg_ollama_model", Input).value = "mistral"
        modal.query_one("#cfg_api_key", Input).value = "gsk_test12345678"
        modal.query_one("#cfg_api_type", Input).value = "groq"
        modal.query_one("#cfg_api_model", Input).value = "llama-3.3-70b-versatile"
        modal.query_one("#cfg_api_base", Input).value = "https://api.groq.com/openai/v1"
        custom_tools = str(tmp_path / "custom_tools")
        modal.query_one("#cfg_tools_dir", Input).value = custom_tools

        # Click save button
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        # Verify app properties updated
        assert app.use_ollama is True
        assert app.ollama_model == "mistral"
        assert app.tools_dir == custom_tools
        assert os.environ.get("CYGUIDE_API_KEY") == "gsk_test12345678"
        assert os.environ.get("CYGUIDE_API_TYPE") == "groq"

        # Verify explainer reloaded with Ollama prefer mode and configured model
        assert isinstance(app.explainer_backend, ExplanationTutor)
        assert app.explainer_backend.prefer_ollama is True
        assert app.explainer_backend.ollama_backend is not None
        assert app.explainer_backend.ollama_backend.model == "mistral"

        # Verify persisted to settings.json
        settings_path = app._get_settings_path()
        assert os.path.exists(settings_path)
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["use_ollama"] is True
            assert data["ollama_model"] == "mistral"
            assert data["api_key"] == "gsk_test12345678"
            assert data["tools_dir"] == custom_tools


@pytest.mark.asyncio
async def test_config_modal_cloud_backend_switch(tmp_path):
    """Verify that disabling Ollama with an API key switches backend to CloudAPIBackend."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        modal.query_one("#cfg_use_ollama", Switch).value = False
        modal.query_one("#cfg_api_key", Input).value = "sk-test-key"
        modal.query_one("#cfg_api_type", Input).value = "openai"
        modal.query_one("#cfg_api_model", Input).value = "gpt-4o"

        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert app.use_ollama is False
        assert isinstance(app.explainer_backend, ExplanationTutor)
        assert app.explainer_backend.model == "gpt-4o"


@pytest.mark.asyncio
async def test_config_modal_reset_to_defaults(tmp_path):
    """Verify clicking Reset Defaults resets the input fields to CLI standard values."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        # Set non-default values
        modal.query_one("#cfg_use_ollama", Switch).value = True
        modal.query_one("#cfg_ollama_model", Input).value = "custom-model"
        modal.query_one("#cfg_tools_dir", Input).value = "custom_path"

        # Click reset button
        await pilot.click("#cfg_reset_btn")
        await pilot.pause()

        # Verify fields were reset
        assert modal.query_one("#cfg_use_ollama", Switch).value is False
        assert modal.query_one("#cfg_ollama_model", Input).value == "gemma"
        assert modal.query_one("#cfg_tools_dir", Input).value == ""


@pytest.mark.asyncio
async def test_toggle_ollama_action(tmp_path):
    """Verify action_toggle_ollama toggles state and updates explainer."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file, use_ollama=False)

    async with app.run_test(size=(100, 40)) as pilot:
        assert app.use_ollama is False
        app.action_toggle_ollama()
        await pilot.pause()
        assert app.use_ollama is True
        assert isinstance(app.explainer_backend, ExplanationTutor)
        assert app.explainer_backend.prefer_ollama is True

        app.action_toggle_ollama()
        await pilot.pause()
        assert app.use_ollama is False


def test_app_init_loads_saved_settings(tmp_path, monkeypatch):
    """Verify CyGuideApp initializes with saved settings from settings.json."""
    monkeypatch.delenv("CYGUIDE_API_KEY", raising=False)
    db_file = str(tmp_path / "test_saved.db")
    base_dir = tmp_path
    settings_file = base_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "use_ollama": True,
                "ollama_model": "deepseek-coder",
                "tools_dir": "extra_tools/",
                "cloud_keys": [
                    {
                        "id": "key_1",
                        "name": "Primary Key",
                        "provider": "openai",
                        "api_key": "saved_key_123",
                        "model": "gpt-4o",
                        "base_url": "",
                        "enabled": True,
                    }
                ],
            }
        )
    )

    app = CyGuideApp(db_path=db_file)
    assert app.use_ollama is True
    assert app.ollama_model == "deepseek-coder"
    assert app.tools_dir == "extra_tools/"
    assert os.environ.get("CYGUIDE_API_KEY") == "saved_key_123"


def test_db_path_normalization_edge_cases(tmp_path):
    """Verify database path normalization handles directory paths, :memory:, and empty inputs."""
    from cyguide.paths import get_default_db_path
    from cyguide.ui.screens.config_modal import normalize_and_validate_db_path

    # 1. Empty string yields default
    res, err = normalize_and_validate_db_path("", data_dir=str(tmp_path))
    assert res == get_default_db_path(str(tmp_path))
    assert err is None

    # 2. :memory: is preserved
    res, err = normalize_and_validate_db_path(":memory:")
    assert res == ":memory:"
    assert err is None

    # 3. Directory path automatically appends cyguide.db
    test_dir = str(tmp_path / "custom_data")
    os.makedirs(test_dir, exist_ok=True)
    res, err = normalize_and_validate_db_path(test_dir)
    assert res == os.path.join(test_dir, "cyguide.db")
    assert err is None

    # 4. Trailing slash appends cyguide.db
    res, err = normalize_and_validate_db_path(f"{test_dir}/")
    assert res == os.path.join(test_dir, "cyguide.db")
    assert err is None


def test_tools_dir_validation_edge_cases(tmp_path):
    """Verify tools directory validation detects non-existent paths and files."""
    from cyguide.ui.screens.config_modal import normalize_and_validate_tools_dir

    # 1. Empty string yields None (bundled tools)
    res, err = normalize_and_validate_tools_dir("")
    assert res is None
    assert err is None

    # 2. Non-existent path returns error
    non_existent = str(tmp_path / "does_not_exist_folder")
    res, err = normalize_and_validate_tools_dir(non_existent)
    assert "does not exist" in (err or "")

    # 3. File instead of directory returns error
    fake_file = tmp_path / "fake.txt"
    fake_file.write_text("hello")
    res, err = normalize_and_validate_tools_dir(str(fake_file))
    assert "not a directory" in (err or "")

    # 4. Valid directory returns no error
    valid_dir = tmp_path / "my_tools"
    valid_dir.mkdir()
    res, err = normalize_and_validate_tools_dir(str(valid_dir))
    assert err is None
    assert res == str(valid_dir)


def test_ollama_url_normalization():
    """Verify Ollama URL normalization ensures http/https scheme and strips trailing slashes."""
    from cyguide.ui.screens.config_modal import normalize_ollama_url

    assert normalize_ollama_url("localhost:11434") == "http://localhost:11434"
    assert normalize_ollama_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert (
        normalize_ollama_url("https://myollama.remote.io:11434///")
        == "https://myollama.remote.io:11434"
    )
    assert normalize_ollama_url("") == "http://localhost:11434"


@pytest.mark.asyncio
async def test_switch_database_runtime(tmp_path):
    """Verify switch_database safely switches active store and updates references."""
    db1 = str(tmp_path / "db1.db")
    db2 = str(tmp_path / "db2.db")
    app = CyGuideApp(db_path=db1)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.db_path == db1
        assert app.store.db_path == db1

        # Switch to db2
        await app.switch_database(db2)
        await pilot.pause()

        assert app.db_path == db2
        assert app.store.db_path == db2
        assert app.executor.store == app.store
        assert app.power_facade.store == app.store


@pytest.mark.asyncio
async def test_config_modal_diagnostics_button(tmp_path):
    """Verify clicking Test Status button updates feedback banner with live diagnostics."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        # Click Test Status button
        await pilot.click("#cfg_test_btn")
        await pilot.pause()

        banner = modal.query_one("#config_feedback_banner")
        # Banner should have updated with results
        banner_text = str(banner.render())
        assert (
            "tested" in banner_text.lower()
            or "issues" in banner_text.lower()
            or "ready" in banner_text.lower()
        )


@pytest.mark.asyncio
async def test_palette_reopening_resets_to_first_option(tmp_path):
    """Verify command palette resets highlight to first option upon fresh opening, but preserves it during traversal."""
    from textual.command import CommandList

    from cyguide.ui.screens.config_modal import ConfigModal

    db_file = str(tmp_path / "test_nav.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        # 1. Open command palette
        await pilot.press("ctrl+p")
        await pilot.pause()
        cl = app.screen.query_one(CommandList)
        assert cl.highlighted == 0  # starts on first option (Toggle Animations)

        # 2. Navigate down to Config
        cfg_idx = next(i for i, opt in enumerate(cl.options) if "Config" in str(opt.prompt))
        cl.highlighted = cfg_idx
        await pilot.pause()

        # 3. Open Config modal (executes action and closes palette)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ConfigModal)

        # 4. Close Config modal
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ConfigModal)

        # 5. Reopen command palette from scratch -> MUST reset to first option (index 0)
        await pilot.press("ctrl+p")
        await pilot.pause()
        cl_reopened = app.screen.query_one(CommandList)
        assert cl_reopened.highlighted == 0
        assert "Toggle Animations" in str(cl_reopened.get_option_at_index(0).prompt)

        # 6. Test traversal: Right arrow on Config moves in, Left arrow moves back with highlight preserved
        cl_reopened.highlighted = cfg_idx
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.screen, ConfigModal)

        # Left arrow traverses back to palette
        await pilot.press("left")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "CyGuideCommandPalette"
        cl_back = app.screen.query_one(CommandList)
        assert cl_back.highlighted == cfg_idx
        assert "Config" in str(cl_back.get_option_at_index(cl_back.highlighted).prompt)


@pytest.mark.asyncio
async def test_config_modal_consistent_height_and_tab_specific_diagnostics(tmp_path, monkeypatch):
    """Verify that ConfigModal maintains consistent dimensions across all tabs and runs tab-specific diagnostics."""
    monkeypatch.delenv("CYGUIDE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    db_file = str(tmp_path / "test_fixed.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(120, 42)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        card = modal.query_one("#config_card")
        tabs = modal.query_one("#config_tabs")
        btn = modal.query_one("#cfg_test_btn")
        banner = modal.query_one("#config_feedback_banner")

        # Initial tab is Ollama
        initial_height = card.size.height
        assert "Ollama" in str(btn.label)

        # Tab: Cloud AI
        tabs.active = "tab_cloud"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Cloud" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        banner_text = str(banner.render()).lower()
        assert "cloud" in banner_text or "api" in banner_text
        assert "ollama" not in banner_text

        # Tab: Database
        tabs.active = "tab_db"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Database" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        banner_text = str(banner.render()).lower()
        assert "database" in banner_text
        assert "ollama" not in banner_text

        # Tab: Tools
        tabs.active = "tab_tools"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Tools" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        banner_text = str(banner.render()).lower()
        assert "tools" in banner_text
        assert "ollama" not in banner_text

        # Tab: Ollama
        tabs.active = "tab_ollama"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Ollama" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)
        banner_text = str(banner.render()).lower()
        assert "ollama" in banner_text


@pytest.mark.asyncio
async def test_config_modal_test_cloud_api_non_blocking_worker(monkeypatch):
    """Verify that clicking Test Cloud API triggers background worker without freezing UI."""
    from textual.widgets import TabbedContent

    app = CyGuideApp(db_path=":memory:")
    async with app.run_test() as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        tabs = modal.query_one("#config_tabs", TabbedContent)
        tabs.active = "tab_cloud"
        await pilot.pause()

        test_called = False

        async def mock_test_cloud(*args, **kwargs):
            nonlocal test_called
            test_called = True
            return True, "Cloud API authenticated (20ms) · openai / gpt-4o"

        monkeypatch.setattr(modal, "_test_cloud_api", mock_test_cloud)

        modal.query_one("#cfg_api_key", Input).value = "sk-test-live-key-123"
        await pilot.click("#cfg_test_btn")
        await app.workers.wait_for_complete()
        await pilot.pause(0.1)

        assert test_called is True
        banner = modal.query_one("#config_feedback_banner", Label)
        assert "authenticated" in str(banner.render()).lower()


@pytest.mark.asyncio
async def test_power_palette_async_git_branch():
    """Verify CommandPalette initializes git branch asynchronously without blocking construction."""
    from cyguide.ui.widgets.power import CommandPalette

    palette = CommandPalette()
    assert palette.branch == ""


@pytest.mark.asyncio
async def test_database_provider_includes_export_and_report(tmp_path):
    """Verify DatabaseConfigProvider discovers export and report options."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)
    mock_screen = MagicMock()
    mock_screen.app = app
    provider = DatabaseConfigProvider(mock_screen)
    provider._app = app

    hits = [h async for h in provider.discover()]
    displays = [str(h.prompt) for h in hits]
    assert any("Database Path" in d for d in displays)
    assert any("Session Exports Directory" in d for d in displays)
    assert any("Markdown Reports Directory" in d for d in displays)


@pytest.mark.asyncio
async def test_config_provider_search_export_and_report(tmp_path):
    """Verify searching for 'export' and 'report' in ConfigProvider matches options."""
    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)
    mock_screen = MagicMock()
    mock_screen.app = app
    provider = ConfigProvider(mock_screen)
    provider._app = app

    export_hits = [h async for h in provider.search("export")]
    assert any("Session Exports Directory" in str(h.prompt) for h in export_hits)

    report_hits = [h async for h in provider.search("report")]
    assert any("Markdown Reports Directory" in str(h.prompt) for h in report_hits)


@pytest.mark.asyncio
async def test_config_modal_export_and_report_save(tmp_path):
    """Verify configuring custom exports and reports directories persists and updates app paths."""
    from textual.widgets import TabbedContent

    db_file = str(tmp_path / "test.db")
    app = CyGuideApp(db_path=db_file)
    custom_exports = str(tmp_path / "custom_exports")
    custom_reports = str(tmp_path / "custom_reports")

    async with app.run_test() as pilot:
        modal = ConfigModal(focus_target="exports_dir")
        await app.push_screen(modal)
        await pilot.pause()

        tabs = modal.query_one("#config_tabs", TabbedContent)
        assert tabs.active == "tab_db"

        modal.query_one("#cfg_exports_dir", Input).value = custom_exports
        modal.query_one("#cfg_reports_dir", Input).value = custom_reports

        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert app.exports_dir == custom_exports
        assert app.reports_dir == custom_reports
        assert app.get_exports_dir() == custom_exports
        assert app.get_reports_dir() == custom_reports

        settings_path = app._get_settings_path()
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("exports_dir") == custom_exports
        assert data.get("reports_dir") == custom_reports


def test_app_action_switch_active_key(tmp_path):
    """Verify action_switch_active_key switches active key and saves to settings."""
    db_file = str(tmp_path / "test.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [
                    {
                        "id": "k1",
                        "name": "Key 1",
                        "provider": "openai",
                        "api_key": "sk-1",
                        "model": "gpt-4o",
                    },
                    {
                        "id": "k2",
                        "name": "Key 2",
                        "provider": "groq",
                        "api_key": "gsk-2",
                        "model": "llama-3.3",
                    },
                ],
                "active_key_id": "k1",
            }
        )
    )

    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))
    assert app.active_key_id == "k1"
    assert app.get_active_cloud_key()["name"] == "Key 1"

    app.action_switch_active_key("k2")
    assert app.active_key_id == "k2"
    assert app.get_active_cloud_key()["name"] == "Key 2"

    assert isinstance(app.explainer_backend, ExplanationTutor)
    assert app.explainer_backend.active_key_id == "k2"
    assert app.explainer_backend.model == "llama-3.3"


@pytest.mark.asyncio
async def test_config_modal_preserves_keys_on_reset(tmp_path):
    """Verify that Reset Defaults preserves saved API keys and only resets standard parameters."""
    db_file = str(tmp_path / "test_empty.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [
                    {
                        "id": "k1",
                        "name": "Preserved Key",
                        "provider": "openai",
                        "api_key": "sk-keep-me-123",
                        "model": "custom-model",
                        "base_url": "https://custom.url",
                        "enabled": True,
                    }
                ],
                "active_key_id": "k1",
            }
        )
    )
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        await pilot.click("#cfg_reset_btn")
        await pilot.pause()

        # Key and identity preserved!
        assert modal.query_one("#cfg_api_key", Input).value == "sk-keep-me-123"
        assert len(modal.cloud_keys) == 1
        assert modal.cloud_keys[0]["id"] == "k1"
        assert modal.cloud_keys[0]["api_key"] == "sk-keep-me-123"
        # Standard parameters for Ollama/DB/tools reset to defaults
        assert modal.query_one("#cfg_use_ollama", Switch).value is False
        assert modal.query_one("#cfg_ollama_model", Input).value == "gemma"


@pytest.mark.asyncio
async def test_config_modal_add_switch_and_save_multiple_keys(tmp_path, monkeypatch):
    """Verify adding multiple keys, setting active, and saving in ConfigModal."""
    db_file = str(tmp_path / "test_multi.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [],
            }
        )
    )
    monkeypatch.delenv("CYGUIDE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        tabs = modal.query_one("#config_tabs")
        tabs.active = "tab_cloud"
        await pilot.pause()

        # Add first key via + Add Key button (opens editor)
        await pilot.click("#cfg_key_add_btn")
        await pilot.pause()

        modal.query_one("#cfg_key_name", Input).value = "My Groq"
        modal.query_one("#cfg_api_type", Input).value = "groq"
        modal.query_one("#cfg_api_key", Input).value = "gsk_first_key"
        modal.query_one("#cfg_api_model", Input).value = "llama-3.3-70b-versatile"
        modal.query_one("#cfg_api_base", Input).value = "https://api.groq.com/openai/v1"
        await pilot.pause()

        # Return to list view via Save & Back
        modal.query_one("#cfg_editor_save_btn").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_editor_save_btn")
        await pilot.pause()

        # Add second key
        modal.query_one("#cfg_key_add_btn").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_key_add_btn")
        await pilot.pause()
        assert not modal.query_one("#cfg_key_editor").has_class("hidden")

        modal.query_one("#cfg_key_name", Input).value = "My OpenAI"
        modal.query_one("#cfg_api_type", Input).value = "openai"
        modal.query_one("#cfg_api_key", Input).value = "sk_second_key"
        modal.query_one("#cfg_api_model", Input).value = "gpt-4o"
        modal.query_one("#cfg_api_base", Input).value = "https://api.openai.com/v1"
        await pilot.pause()

        # Return to list view via Save & Back
        modal.query_one("#cfg_editor_save_btn").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_editor_save_btn")
        await pilot.pause()

        # Set active key on list card (Set Active is exclusively on list cards)
        second_key_id = modal.cloud_keys[-1]["id"]
        act_btn = modal.query_one(f"#cfg_activate_key_{second_key_id}")
        act_btn.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(act_btn)
        await pilot.pause()
        assert modal.active_key_id == second_key_id

        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert len(app.cloud_keys) >= 2
        active_prof = app.get_active_cloud_key()
        assert active_prof["name"] == "My OpenAI"
        assert active_prof["api_key"] == "sk_second_key"

        settings_path = app._get_settings_path()
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["cloud_keys"]) >= 2
            assert data["active_key_id"] == active_prof["id"]


@pytest.mark.asyncio
async def test_cloud_palette_provider_multi_key_switch(tmp_path):
    """Verify CloudAPIConfigProvider exposes fast key switching options when multiple keys are configured."""
    db_file = str(tmp_path / "test_palette.db")
    app = CyGuideApp(db_path=db_file)
    app.cloud_keys = [
        {
            "id": "k1",
            "name": "Groq Llama",
            "provider": "groq",
            "api_key": "gsk_1",
            "model": "llama-3.3",
        },
        {
            "id": "k2",
            "name": "OpenAI GPT-4o",
            "provider": "openai",
            "api_key": "sk_2",
            "model": "gpt-4o",
        },
    ]
    app.active_key_id = "k1"

    mock_screen = MagicMock()
    mock_screen.app = app
    provider = CloudAPIConfigProvider(mock_screen)
    provider._app = app

    hits = [h async for h in provider.discover()]
    prompts = [str(h.prompt) for h in hits]

    assert any("Switch Active Key: Groq Llama" in p and "Active" in p for p in prompts)
    assert any("Switch Active Key: OpenAI GPT-4o" in p and "Switch" in p for p in prompts)
    assert any("API Key" in p for p in prompts)
    assert any("Provider Type" in p for p in prompts)
    assert any("Toggle Cloud AI Access" in p for p in prompts)


@pytest.mark.asyncio
async def test_cloud_api_toggle_and_action(tmp_path):
    """Verify action_toggle_cloud_api flips state, reloads explainer, and persists."""
    db_file = str(tmp_path / "test_toggle.db")
    app = CyGuideApp(db_path=db_file)
    assert app.use_cloud_api is True

    with patch.object(app, "reload_explainer") as mock_reload:
        app.action_toggle_cloud_api()
        assert app.use_cloud_api is False
        mock_reload.assert_called_once()

        app.action_toggle_cloud_api()
        assert app.use_cloud_api is True


@pytest.mark.asyncio
async def test_config_modal_cloud_toggle_and_key_bar_layout(tmp_path):
    """Verify ConfigModal has Enable Cloud AI Access switch, key list cards, editor, and saves toggle state."""
    db_file = str(tmp_path / "test_modal_layout.db")
    app = CyGuideApp(db_path=db_file)

    async with app.run_test(size=(100, 40)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()

        tabs = modal.query_one("#config_tabs")
        tabs.active = "tab_cloud"
        await pilot.pause()

        # Cloud AI toggle switch & badge
        cloud_switch = modal.query_one("#cfg_use_cloud_api", Switch)
        badge = modal.query_one("#cfg_cloud_switch_badge")
        assert cloud_switch.value is True
        assert "ON" in str(badge.render())

        # Toggle switch to OFF
        cloud_switch.value = False
        await pilot.pause()
        assert "OFF" in str(badge.render())

        # Key list and editor structure
        add_btn = modal.query_one("#cfg_key_add_btn")
        keys_list = modal.query_one("#cfg_keys_list")
        key_editor = modal.query_one("#cfg_key_editor")
        save_btn = key_editor.query_one("#cfg_editor_save_btn")
        cancel_btn = key_editor.query_one("#cfg_editor_cancel_btn")
        del_btn = key_editor.query_one("#cfg_key_del_btn")
        assert add_btn is not None
        assert keys_list is not None
        assert key_editor is not None
        assert save_btn is not None
        assert cancel_btn is not None
        assert del_btn is not None
        # Set Active is only on list cards, not in key editor
        assert len(key_editor.query("#cfg_key_set_active_btn")) == 0

        # TabPane and Input scrolling styling checks (no scrollbars covering text, no horiz page scroll)
        tab_cloud_pane = modal.query_one("#tab_cloud")
        assert tab_cloud_pane.styles.overflow_y == "auto"
        assert tab_cloud_pane.styles.overflow_x == "hidden"
        name_input = modal.query_one("#cfg_key_name", Input)
        assert name_input.styles.overflow_x == "hidden"
        assert name_input.styles.overflow_y == "hidden"

        # Save & Apply and verify app.use_cloud_api is persisted as False
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert app.use_cloud_api is False


@pytest.mark.asyncio
async def test_duplicate_api_key_security_rejection(tmp_path):
    """Verify that entering duplicate API keys across profiles is rejected by security validation."""
    db_file = str(tmp_path / "test_dup.db")
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # Key 1
        modal.query_one("#cfg_key_name", Input).value = "OpenAI 1"
        modal.query_one("#cfg_api_type", Input).value = "openai"
        modal.query_one("#cfg_api_key", Input).value = "sk-shared-credential-12345"
        await pilot.pause()

        # Click + Add to start Key 2
        await pilot.click("#cfg_key_add_btn")
        await pilot.pause()

        # Key 2 with DUPLICATE key
        modal.query_one("#cfg_key_name", Input).value = "OpenAI 2"
        modal.query_one("#cfg_api_type", Input).value = "groq"
        modal.query_one("#cfg_api_key", Input).value = "sk-shared-credential-12345"
        await pilot.pause()

        # Click Save & Apply -> Must fail validation
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        banner = modal.query_one("#config_feedback_banner")
        banner_text = str(banner.render())
        assert "Duplicate API key" in banner_text


@pytest.mark.asyncio
async def test_deleted_key_remains_deleted_and_no_resurrection(tmp_path):
    """Verify that deleting all keys persists and doesn't resurrect default key on reopen."""
    db_file = str(tmp_path / "test_del.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [
                    {
                        "id": "k1",
                        "name": "Key to Remove",
                        "provider": "openai",
                        "api_key": "sk-remove-123",
                        "model": "gpt-4o",
                        "base_url": "",
                        "enabled": True,
                    }
                ],
                "active_key_id": "k1",
            }
        )
    )

    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # Delete the key via per-card delete button on list
        modal.query_one("#cfg_delete_key_k1").scroll_visible(animate=False)
        await pilot.click("#cfg_delete_key_k1")
        await pilot.pause()

        assert len(modal.cloud_keys) == 0

        # Save & Apply (keeps modal open)
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert len(app.cloud_keys) == 0
        assert app.active_key_id is None

        # Close first modal cleanly
        await pilot.click("#cfg_close_btn")
        await pilot.pause()

        # Reopen modal
        modal2 = ConfigModal()
        await app.push_screen(modal2)
        await pilot.pause()
        modal2.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # Must still be 0, no ghost Default Key
        assert len(modal2.cloud_keys) == 0
        assert modal2.active_key_id is None
        assert modal2.query_one("#cfg_api_key", Input).value == ""
        assert "No Cloud API Key set" in str(modal2.query_one("#cfg_cloud_status_msg").render())


@pytest.mark.asyncio
async def test_in_place_parameter_modification_does_not_add_extra_keys(tmp_path):
    """Verify that editing fields for an existing key modifies that key in-place and does not add extra profiles."""
    db_file = str(tmp_path / "test_inplace.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [
                    {
                        "id": "k1",
                        "name": "Key One",
                        "provider": "openai",
                        "api_key": "sk-one-1234",
                        "model": "gpt-4o",
                        "base_url": "",
                        "enabled": True,
                    }
                ],
                "active_key_id": "k1",
            }
        )
    )
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        assert len(modal.cloud_keys) == 1
        assert modal.query_one("#cfg_key_name", Input).value == "Key One"
        assert modal.query_one("#cfg_api_model", Input).value == "gpt-4o"

        # Modify parameters in-place
        modal.query_one("#cfg_key_name", Input).value = "Key One Renamed"
        modal.query_one("#cfg_api_model", Input).value = "gpt-4o-mini"
        await pilot.pause()

        # Still exactly 1 key, modified in-place
        assert len(modal.cloud_keys) == 1
        assert modal.cloud_keys[0]["name"] == "Key One Renamed"
        assert modal.cloud_keys[0]["model"] == "gpt-4o-mini"
        assert modal.cloud_keys[0]["id"] == "k1"

        # Click Save & Apply (keeps modal open)
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        # Modal is still open!
        assert isinstance(app.screen, ConfigModal)
        assert len(modal.cloud_keys) == 1
        assert len(app.cloud_keys) == 1
        assert app.cloud_keys[0]["name"] == "Key One Renamed"
        assert app.cloud_keys[0]["model"] == "gpt-4o-mini"

        # Verify feedback banner shows success
        banner = modal.query_one("#config_feedback_banner")
        assert "Configuration saved and applied successfully" in str(banner.render())


@pytest.mark.asyncio
async def test_credential_missing_indicators_for_blank_key(tmp_path):
    """Verify that a profile without an API key displays credential missing indicators and is safely saved."""
    db_file = str(tmp_path / "test_missing.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [],
            }
        )
    )
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # Create new profile with name and model but NO API key
        await pilot.click("#cfg_key_add_btn")
        await pilot.pause()

        modal.query_one("#cfg_key_name", Input).value = "Pending Profile"
        modal.query_one("#cfg_api_type", Input).value = "openai"
        modal.query_one("#cfg_api_model", Input).value = "gpt-4o"
        await pilot.pause()

        # Check status shows missing credential
        status_msg = str(modal.query_one("#cfg_cloud_status_msg").render())
        assert "has no API key" in status_msg or "Missing Credentials" in status_msg

        # Save & Apply - incomplete profile is preserved, not purged
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert len(modal.cloud_keys) == 1
        assert modal.cloud_keys[0]["name"] == "Pending Profile"
        assert modal.cloud_keys[0]["api_key"] == ""
        assert len(app.cloud_keys) == 1


@pytest.mark.asyncio
async def test_key_list_cards_interaction_and_per_key_actions(tmp_path):
    """Verify key card list renders info, fallback badge, and inline actions work seamlessly."""
    db_file = str(tmp_path / "test_cards.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [
                    {
                        "id": "k1",
                        "name": "Primary OpenAI",
                        "provider": "openai",
                        "api_key": "sk-openai-12345",
                        "model": "gpt-4o",
                        "base_url": "https://api.openai.com/v1",
                        "enabled": True,
                    },
                    {
                        "id": "k2",
                        "name": "Backup Groq",
                        "provider": "groq",
                        "api_key": "gsk-groq-67890",
                        "model": "llama-3.3-70b",
                        "base_url": "https://api.groq.com/openai/v1",
                        "enabled": False,
                    },
                ],
                "active_key_id": "k1",
            }
        )
    )

    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # Check list has 2 cards
        card_1 = modal.query_one("#cfg_card_k1")
        card_2 = modal.query_one("#cfg_card_k2")
        assert card_1 is not None
        assert card_2 is not None

        # Verify initial active / standby pills
        pill_1 = modal.query_one("#cfg_pill_k1")
        pill_2 = modal.query_one("#cfg_pill_k2")
        assert "Active" in str(pill_1.render())
        assert "Standby" in str(pill_2.render())

        # Verify fallback badges
        fb_1 = modal.query_one("#cfg_fallback_k1")
        fb_2 = modal.query_one("#cfg_fallback_k2")
        assert "YES" in str(fb_1.render())
        assert "NO" in str(fb_2.render())

        # Click Set Active button on card 2
        await pilot.click("#cfg_activate_key_k2")
        await pilot.pause()

        assert modal.active_key_id == "k2"
        assert "Active" in str(pill_2.render())
        assert "Standby" in str(pill_1.render())

        # Initially list is visible, editor is hidden
        assert modal.query_one("#cfg_key_editor").has_class("hidden")
        assert not modal.query_one("#cfg_cloud_list_view").has_class("hidden")

        # Click Edit on card 1 -> switches to editor view and loads card 1
        await pilot.click("#cfg_edit_key_k1")
        await pilot.pause()

        assert not modal.query_one("#cfg_key_editor").has_class("hidden")
        assert modal.query_one("#cfg_cloud_list_view").has_class("hidden")
        assert len(modal.query("#cfg_key_editor #cfg_key_set_active_btn")) == 0

        assert modal.editing_profile_id == "k1"
        assert modal.query_one("#cfg_key_name", Input).value == "Primary OpenAI"
        assert "Primary OpenAI" in str(modal.query_one("#cfg_editor_title").render())

        # Toggle fallback switch for card 1
        modal.query_one("#cfg_key_enabled", Switch).value = False
        await pilot.pause()

        # Test long input does not break layout: Input styles overflow_x is hidden
        long_url = (
            "https://very-long-custom-enterprise-gateway.company.internal/v1/services/ai/inference"
        )
        url_input = modal.query_one("#cfg_api_base", Input)
        url_input.value = long_url
        await pilot.pause()
        assert url_input.styles.overflow_x == "hidden"
        assert url_input.styles.overflow_y == "hidden"

        # Return to list view via Save & Back
        save_btn = modal.query_one("#cfg_editor_save_btn")
        save_btn.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_editor_save_btn")
        await pilot.pause()

        assert modal.query_one("#cfg_key_editor").has_class("hidden")
        assert not modal.query_one("#cfg_cloud_list_view").has_class("hidden")
        assert "NO" in str(modal.query_one("#cfg_fallback_k1").render())

        # Test Just Back (cancel): Edit card 1, make unsaved changes, then click Back
        await pilot.click("#cfg_edit_key_k1")
        await pilot.pause()
        modal.query_one("#cfg_key_name", Input).value = "Modified Unsaved Name"
        await pilot.pause()
        modal.query_one("#cfg_editor_cancel_btn").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_editor_cancel_btn")
        await pilot.pause()

        # Should be back in list view and title is NOT the unsaved modification
        assert modal.query_one("#cfg_key_editor").has_class("hidden")
        assert not modal.query_one("#cfg_cloud_list_view").has_class("hidden")
        assert "Primary OpenAI" in str(modal.query_one("#cfg_title_k1").render())

        # Delete card 2 via per-card delete button on list
        modal.query_one("#cfg_delete_key_k2").scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click("#cfg_delete_key_k2")
        await pilot.pause()

        assert len(modal.cloud_keys) == 1
        assert modal.cloud_keys[0]["id"] == "k1"
        assert len(modal.query("#cfg_card_k2")) == 0

        # Save & Apply and verify
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        assert len(app.cloud_keys) == 1
        assert app.cloud_keys[0]["id"] == "k1"
        assert app.cloud_keys[0]["enabled"] is False


@pytest.mark.asyncio
async def test_cloud_ai_view_switching_and_editor_behavior(tmp_path, monkeypatch):
    """Verify clean view transitions: List default, Add Key -> Editor, Save & Back -> List, and Delete in Editor."""
    db_file = str(tmp_path / "test_views.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "cloud_keys": [],
            }
        )
    )
    monkeypatch.delenv("CYGUIDE_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))

    async with app.run_test(size=(120, 45)) as pilot:
        modal = ConfigModal()
        await app.push_screen(modal)
        await pilot.pause()
        modal.query_one("#config_tabs").active = "tab_cloud"
        await pilot.pause()

        # 1. Default state: List visible, editor hidden
        list_view = modal.query_one("#cfg_cloud_list_view")
        editor_view = modal.query_one("#cfg_key_editor")
        assert not list_view.has_class("hidden")
        assert editor_view.has_class("hidden")

        # 2. Add Key switches to editor view
        modal.query_one("#cfg_key_add_btn", Button).press()
        await pilot.pause()

        new_id = modal.editing_profile_id
        assert new_id is not None

        assert list_view.has_class("hidden")
        assert not editor_view.has_class("hidden")
        assert len(modal.query("#cfg_key_editor #cfg_key_set_active_btn")) == 0

        modal.query_one("#cfg_key_name", Input).value = "Anthropic Production"
        modal.query_one("#cfg_api_type", Input).value = "anthropic"
        modal.query_one("#cfg_api_key", Input).value = "sk-ant-123456789"
        await pilot.pause()

        # 3. Save & Back returns to list view
        modal.query_one("#cfg_editor_save_btn", Button).press()
        await pilot.pause()

        assert not list_view.has_class("hidden")
        assert editor_view.has_class("hidden")

        # Verify new card is displayed in list
        new_card = modal.query_one(f"#cfg_card_{new_id}")
        assert new_card is not None
        assert "Anthropic Production" in str(modal.query_one(f"#cfg_title_{new_id}").render())

        # 4. Open editor via Edit button and delete from editor
        modal.query_one(f"#cfg_edit_key_{new_id}", Button).press()
        await pilot.pause()

        assert list_view.has_class("hidden")
        assert not editor_view.has_class("hidden")

        # Click delete in editor
        modal.query_one("#cfg_key_del_btn", Button).press()
        await pilot.pause()

        # Automatically returned to list view and profile deleted
        assert not list_view.has_class("hidden")
        assert editor_view.has_class("hidden")
        assert not any(k.get("id") == new_id for k in modal.cloud_keys)
