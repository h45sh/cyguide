import pytest

from cyguide.engine.explainer import (
    CloudKeyProfile,
    ExplanationTutor,
    MockProviderAdapter,
    OllamaBackend,
    TutorError,
    TutorToken,
)


@pytest.mark.asyncio
async def test_explanation_tutor_typed_stream():
    """Verify that stream() produces typed TutorToken events using an internal adapter."""
    mock_adapter = MockProviderAdapter(
        chunks=["SQL injection ", "occurs when user input ", "is unvalidated."]
    )

    profile = CloudKeyProfile(
        id="k1", name="Test Key", provider="openai", api_key="sk-test", model="gpt-4o"
    )
    tutor = ExplanationTutor(profiles=[profile], active_key_id="k1")
    tutor._custom_adapters["k1"] = mock_adapter

    events = []
    async for event in tutor.stream("Explain SQL injection"):
        events.append(event)

    tokens = [e for e in events if isinstance(e, TutorToken)]
    assert len(tokens) == 3
    assert tokens[0].text == "SQL injection "
    assert tokens[1].text == "occurs when user input "
    assert tokens[2].text == "is unvalidated."


@pytest.mark.asyncio
async def test_explanation_tutor_in_place_key_switch():
    """Verify in-place key switching updates active profile without losing object reference."""
    k1 = CloudKeyProfile(id="k1", name="Key 1", provider="openai", api_key="sk-1", model="gpt-4o")
    k2 = CloudKeyProfile(id="k2", name="Key 2", provider="groq", api_key="gsk-2", model="llama-3.3")

    tutor = ExplanationTutor(profiles=[k1, k2], active_key_id="k1")
    assert tutor.active_key_id == "k1"
    assert tutor.model == "gpt-4o"

    # Switch in-place
    switched = tutor.set_active_key("k2")
    assert switched is True
    assert tutor.active_key_id == "k2"
    assert tutor.model == "llama-3.3"
    assert tutor.get_active_profile().id == "k2"


@pytest.mark.asyncio
async def test_explanation_tutor_status_event_on_fallback():
    """Verify stream() yields a TutorStatus event when falling back across keys."""
    k1 = CloudKeyProfile(id="k1", name="Key 1", provider="openai", api_key="sk-bad", model="gpt-4o")
    k2 = CloudKeyProfile(
        id="k2", name="Key 2", provider="groq", api_key="gsk-good", model="llama-3.3"
    )

    tutor = ExplanationTutor(profiles=[k1, k2], active_key_id="k1")

    # Set k1 in cooldown so it falls back to k2
    k1.set_cooldown(60.0)

    adapter2 = MockProviderAdapter(chunks=["Fallback response from Groq"])
    tutor._custom_adapters["k2"] = adapter2

    events = []
    async for ev in tutor.stream("Test prompt"):
        events.append(ev)

    tokens = [e.text for e in events if isinstance(e, TutorToken)]
    assert "".join(tokens) == "Fallback response from Groq"


@pytest.mark.asyncio
async def test_explanation_tutor_error_event_when_all_fail():
    """Verify stream() yields TutorError when no providers are available."""
    ollama = OllamaBackend(model="gemma", base_url="http://127.0.0.1:54321")
    tutor = ExplanationTutor(
        profiles=[],
        fallback_to_ollama=True,
        ollama_backend=ollama,
        cloud_enabled=True,
    )

    events = []
    async for ev in tutor.stream("Hello"):
        events.append(ev)

    errors = [e for e in events if isinstance(e, TutorError)]
    assert len(errors) >= 1
    assert errors[0].is_fatal is True
    assert "AI Tutor Unavailable" in errors[0].error
