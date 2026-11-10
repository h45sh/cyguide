"""Unit tests for Multi-API key management, automatic fallback, and key switching."""

import json
import pytest
from unittest.mock import MagicMock, patch
from textual.widgets import Button, Input, Switch

from cyguide.app import CyGuideApp
from cyguide.engine.explainer import (
    CloudKeyProfile,
    MultiKeyCloudBackend,
    OllamaBackend,
)
from cyguide.ui.screens.config_modal import ConfigModal, CloudAPIConfigProvider


def test_cloud_key_profile_dataclass_and_cooldown():
    """Verify CloudKeyProfile serialization and cooldown logic."""
    profile = CloudKeyProfile(
        id="key_groq",
        name="Groq Llama 3.3",
        provider="groq",
        api_key="gsk_123456",
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        enabled=True,
    )

    data = profile.to_dict()
    assert data["id"] == "key_groq"
    assert data["provider"] == "groq"
    assert data["api_key"] == "gsk_123456"

    restored = CloudKeyProfile.from_dict(data)
    assert restored.id == profile.id
    assert restored.model == profile.model

    # Cooldown testing
    assert not profile.is_in_cooldown()
    profile.set_cooldown(10.0)
    assert profile.is_in_cooldown()
    assert profile.last_status == "rate_limited"


@pytest.mark.asyncio
async def test_multikey_backend_active_key_priority():
    """Verify priority chain puts the active key first."""
    k1 = CloudKeyProfile(id="k1", name="Key 1", provider="openai", api_key="sk-1", model="gpt-4o")
    k2 = CloudKeyProfile(id="k2", name="Key 2", provider="groq", api_key="gsk-2", model="llama-3.3")

    backend = MultiKeyCloudBackend(profiles=[k1, k2], active_key_id="k2")
    chain = backend.get_priority_chain()
    assert len(chain) == 2
    assert chain[0].id == "k2"
    assert chain[1].id == "k1"

    # Switch active key
    backend.set_active_key("k1")
    chain2 = backend.get_priority_chain()
    assert chain2[0].id == "k1"
    assert chain2[1].id == "k2"


@pytest.mark.asyncio
async def test_multikey_resilient_fallback_on_429():
    """Verify that when primary key returns 429, backend automatically falls back to secondary key."""
    k1 = CloudKeyProfile(id="k1", name="Primary OpenAI", provider="openai", api_key="sk-bad", model="gpt-4o")
    k2 = CloudKeyProfile(id="k2", name="Backup Groq", provider="groq", api_key="gsk-good", model="llama-3.3")

    backend = MultiKeyCloudBackend(profiles=[k1, k2], active_key_id="k1")

    call_count = 0

    class MockStreamContext:
        def __init__(self, status_code, chunks):
            self.status_code = status_code
            self._chunks = chunks

        async def __aenter__(self):
            class Response:
                def __init__(self, sc, ch):
                    self.status_code = sc
                    self._ch = ch

                async def aread(self):
                    return b"Rate limit exceeded"

                async def aiter_lines(self):
                    for c in self._ch:
                        yield f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}"
                    yield "data: [DONE]"

            return Response(self.status_code, self._chunks)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_stream(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "sk-bad" in kwargs.get("headers", {}).get("Authorization", ""):
            return MockStreamContext(429, [])
        return MockStreamContext(200, ["Hello", " from", " backup!"])

    with patch("httpx.AsyncClient.stream", side_effect=mock_stream):
        chunks = []
        async for chunk in backend.explain("Test prompt"):
            chunks.append(chunk)

        output = "".join(chunks)
        assert "Notice: Rate limit reached (429)" in output
        assert "Hello from backup!" in output
        assert call_count == 2
        assert k1.is_in_cooldown()


@pytest.mark.asyncio
async def test_multikey_fallback_to_ollama_when_all_cloud_keys_fail():
    """Verify that when all cloud keys fail, fallback to local Ollama occurs."""
    k1 = CloudKeyProfile(id="k1", name="Key 1", provider="openai", api_key="sk-bad")

    class MockOllama(OllamaBackend):
        async def explain(self, prompt: str):
            yield "Ollama fallback content"

    mock_ollama = MockOllama(model="gemma")
    backend = MultiKeyCloudBackend(profiles=[k1], active_key_id="k1", fallback_to_ollama=True, ollama_backend=mock_ollama)

    class MockErrContext:
        async def __aenter__(self):
            class ErrResp:
                status_code = 401
                async def aread(self):
                    return b"Unauthorized"
            return ErrResp()
        async def __aexit__(self, *args):
            pass

    with patch("httpx.AsyncClient.stream", return_value=MockErrContext()):
        chunks = []
        async for chunk in backend.explain("Test prompt"):
            chunks.append(chunk)

        full = "".join(chunks)
        assert "Falling back to Local Ollama" in full
        assert "Ollama fallback content" in full


def test_app_action_switch_active_key(tmp_path):
    """Verify action_switch_active_key switches active key and saves to settings."""
    db_file = str(tmp_path / "test.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "cloud_keys": [
            {"id": "k1", "name": "Key 1", "provider": "openai", "api_key": "sk-1", "model": "gpt-4o"},
            {"id": "k2", "name": "Key 2", "provider": "groq", "api_key": "gsk-2", "model": "llama-3.3"},
        ],
        "active_key_id": "k1",
    }))

    app = CyGuideApp(db_path=db_file, data_dir=str(tmp_path))
    assert app.active_key_id == "k1"
    assert app.get_active_cloud_key()["name"] == "Key 1"

    app.action_switch_active_key("k2")
    assert app.active_key_id == "k2"
    assert app.get_active_cloud_key()["name"] == "Key 2"

    assert isinstance(app.explainer_backend, MultiKeyCloudBackend)
    assert app.explainer_backend.active_key_id == "k2"
    assert app.explainer_backend.model == "llama-3.3"


@pytest.mark.asyncio
async def test_config_modal_preserves_keys_on_reset(tmp_path):
    """Verify that Reset Defaults preserves saved API keys and only resets standard parameters."""
    db_file = str(tmp_path / "test_empty.db")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "cloud_keys": [
            {"id": "k1", "name": "Preserved Key", "provider": "openai", "api_key": "sk-keep-me-123", "model": "custom-model", "base_url": "https://custom.url", "enabled": True}
        ],
        "active_key_id": "k1",
    }))
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
    settings_file.write_text(json.dumps({
        "cloud_keys": [],
    }))
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
        {"id": "k1", "name": "Groq Llama", "provider": "groq", "api_key": "gsk_1", "model": "llama-3.3"},
        {"id": "k2", "name": "OpenAI GPT-4o", "provider": "openai", "api_key": "sk_2", "model": "gpt-4o"},
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
    settings_file.write_text(json.dumps({
        "cloud_keys": [
            {"id": "k1", "name": "Key to Remove", "provider": "openai", "api_key": "sk-remove-123", "model": "gpt-4o", "base_url": "", "enabled": True}
        ],
        "active_key_id": "k1",
    }))

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
    settings_file.write_text(json.dumps({
        "cloud_keys": [
            {"id": "k1", "name": "Key One", "provider": "openai", "api_key": "sk-one-1234", "model": "gpt-4o", "base_url": "", "enabled": True}
        ],
        "active_key_id": "k1",
    }))
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
    settings_file.write_text(json.dumps({
        "cloud_keys": [],
    }))
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
    settings_file.write_text(json.dumps({
        "cloud_keys": [
            {"id": "k1", "name": "Primary OpenAI", "provider": "openai", "api_key": "sk-openai-12345", "model": "gpt-4o", "base_url": "https://api.openai.com/v1", "enabled": True},
            {"id": "k2", "name": "Backup Groq", "provider": "groq", "api_key": "gsk-groq-67890", "model": "llama-3.3-70b", "base_url": "https://api.groq.com/openai/v1", "enabled": False},
        ],
        "active_key_id": "k1",
    }))

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
        long_url = "https://very-long-custom-enterprise-gateway.company.internal/v1/services/ai/inference"
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
    settings_file.write_text(json.dumps({
        "cloud_keys": [],
    }))
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
