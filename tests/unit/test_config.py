"""Unit tests for CyGuide configuration options and Command Palette integration."""

import os
import json
import asyncio
import pytest
from unittest.mock import MagicMock
from textual.widgets import Input, Switch, Label, Button

from cyguide.app import CyGuideApp, CyGuideCommandPalette
from cyguide.ui.screens.config_modal import (
    ConfigModal,
    ConfigProvider,
    OllamaConfigProvider,
    CloudAPIConfigProvider,
    DatabaseConfigProvider,
    ToolsConfigProvider,
)
from cyguide.engine.explainer import OllamaBackend, CloudAPIBackend


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

    # Verify exact conventional command order
    assert any("Toggle Animations" in t for t in titles)
    assert any("Tool Health" in t for t in titles)
    assert "Config" in titles
    assert "Theme" in titles
    assert "Hotkeys" in titles
    assert "Screenshot" in titles
    assert titles[-1] == "Quit"

    # Verify legacy Textual 'Keys' command is replaced by our 'Hotkeys'
    assert "Keys" not in titles


@pytest.mark.asyncio
async def test_command_palette_exact_order(tmp_path):
    """Verify Command Palette displays the streamlined 7-item conventional menu order without Toggle Sidebar."""
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
            "Theme",
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
    app = CyGuideApp(db_path=db_file, use_ollama=True, ollama_model="llama3", tools_dir="extra_tools")
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
        modal.query_one("#cfg_tools_dir", Input).value = "my_tools/"

        # Click save button
        await pilot.click("#cfg_save_btn")
        await pilot.pause()

        # Verify app properties updated
        assert app.use_ollama is True
        assert app.ollama_model == "mistral"
        assert app.tools_dir == "my_tools/"
        assert os.environ.get("CYGUIDE_API_KEY") == "gsk_test12345678"
        assert os.environ.get("CYGUIDE_API_TYPE") == "groq"

        # Verify explainer reloaded with Ollama
        assert isinstance(app.explainer_backend, OllamaBackend)
        assert app.explainer_backend.model == "mistral"

        # Verify persisted to settings.json
        settings_path = app._get_settings_path()
        assert os.path.exists(settings_path)
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["use_ollama"] is True
            assert data["ollama_model"] == "mistral"
            assert data["api_key"] == "gsk_test12345678"
            assert data["tools_dir"] == "my_tools/"


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
        assert isinstance(app.explainer_backend, CloudAPIBackend)
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
        assert isinstance(app.explainer_backend, OllamaBackend)

        app.action_toggle_ollama()
        await pilot.pause()
        assert app.use_ollama is False


def test_app_init_loads_saved_settings(tmp_path, monkeypatch):
    """Verify CyGuideApp initializes with saved settings from settings.json."""
    monkeypatch.delenv("CYGUIDE_API_KEY", raising=False)
    db_file = str(tmp_path / "test_saved.db")
    base_dir = tmp_path
    settings_file = base_dir / "settings.json"
    settings_file.write_text(json.dumps({
        "use_ollama": True,
        "ollama_model": "deepseek-coder",
        "tools_dir": "extra_tools/",
        "api_key": "saved_key_123",
    }))

    app = CyGuideApp(db_path=db_file)
    assert app.use_ollama is True
    assert app.ollama_model == "deepseek-coder"
    assert app.tools_dir == "extra_tools/"
    assert os.environ.get("CYGUIDE_API_KEY") == "saved_key_123"


def test_db_path_normalization_edge_cases(tmp_path):
    """Verify database path normalization handles directory paths, :memory:, and empty inputs."""
    from cyguide.ui.screens.config_modal import normalize_and_validate_db_path
    from cyguide.paths import get_default_db_path

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
    assert normalize_ollama_url("https://myollama.remote.io:11434///") == "https://myollama.remote.io:11434"
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
        assert app.recommendation_engine.store == app.store
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
        assert "tested" in banner_text.lower() or "issues" in banner_text.lower() or "ready" in banner_text.lower()


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
        await pilot.pause()
        banner_text = str(banner.render()).lower()
        assert "cloud" in banner_text or "api" in banner_text
        assert "ollama" not in banner_text

        # Tab: Database
        tabs.active = "tab_db"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Database" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await pilot.pause()
        banner_text = str(banner.render()).lower()
        assert "database" in banner_text
        assert "ollama" not in banner_text

        # Tab: Tools
        tabs.active = "tab_tools"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Tools" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await pilot.pause()
        banner_text = str(banner.render()).lower()
        assert "tools" in banner_text
        assert "ollama" not in banner_text

        # Tab: Ollama
        tabs.active = "tab_ollama"
        await pilot.pause()
        assert card.size.height == initial_height
        assert "Ollama" in str(btn.label)
        await pilot.click("#cfg_test_btn")
        await pilot.pause()
        banner_text = str(banner.render()).lower()
        assert "ollama" in banner_text


@pytest.mark.asyncio
async def test_config_modal_test_cloud_api_non_blocking_worker(monkeypatch):
    """Verify that clicking Test Cloud API triggers background worker without freezing UI."""
    from textual.widgets import TabbedContent, Button
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
            await asyncio.sleep(0.02)
            return True, "Cloud API authenticated (20ms) · openai / gpt-4o"

        monkeypatch.setattr(modal, "_test_cloud_api", mock_test_cloud)

        modal.query_one("#cfg_api_key", Input).value = "sk-test-live-key-123"

        btn = modal.query_one("#cfg_test_btn", Button)
        await pilot.click("#cfg_test_btn")
        await pilot.pause()
        await pilot.pause()

        assert test_called is True
        banner = modal.query_one("#config_feedback_banner", Label)
        assert "authenticated" in str(banner.render()).lower()


@pytest.mark.asyncio
async def test_power_palette_async_git_branch():
    """Verify CommandPalette initializes git branch asynchronously without blocking construction."""
    from cyguide.ui.widgets.power import CommandPalette
    palette = CommandPalette()
    assert palette.branch == ""
