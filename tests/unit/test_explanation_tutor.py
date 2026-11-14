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


@pytest.mark.asyncio
async def test_prefer_ollama_falls_back_to_cloud_when_unreachable():
    """Verify ExplanationTutor gracefully falls back to Cloud AI when Ollama is unreachable."""
    from cyguide.engine.explainer import TutorStatus

    ollama = OllamaBackend(model="gemma", base_url="http://127.0.0.1:54321")
    cloud_profile = CloudKeyProfile(
        id="k1", name="Cloud Provider", provider="openai", api_key="sk-real-key", model="gpt-4o"
    )
    tutor = ExplanationTutor(
        profiles=[cloud_profile],
        active_key_id="k1",
        ollama_backend=ollama,
        prefer_ollama=True,
        cloud_enabled=True,
    )
    tutor._custom_adapters["k1"] = MockProviderAdapter(
        chunks=["Cloud answer after Ollama offline."]
    )

    events = []
    async for ev in tutor.stream("Explain nmap scan"):
        events.append(ev)

    statuses = [e for e in events if isinstance(e, TutorStatus)]
    tokens = [e for e in events if isinstance(e, TutorToken)]

    assert len(statuses) >= 1
    assert "Falling back to Cloud AI" in statuses[0].message
    assert "".join(t.text for t in tokens) == "Cloud answer after Ollama offline."


@pytest.mark.asyncio
async def test_prefer_ollama_midstream_disconnect_falls_back_to_cloud():
    """Verify that if Ollama drops mid-stream, ExplanationTutor recovers and falls back to Cloud AI."""
    from typing import AsyncIterator

    from cyguide.engine.explainer import TutorStatus

    class MidstreamFailingOllama(OllamaBackend):
        async def explain(self, prompt: str, system=None) -> AsyncIterator[str]:
            yield "Partial token before crash. "
            yield "[Error: Ollama connection failed (Server closed). Please ensure Ollama is running (`ollama serve`).]\n"

    ollama = MidstreamFailingOllama(model="gemma")
    cloud_profile = CloudKeyProfile(
        id="k1", name="Cloud Provider", provider="openai", api_key="sk-real-key", model="gpt-4o"
    )
    tutor = ExplanationTutor(
        profiles=[cloud_profile],
        active_key_id="k1",
        ollama_backend=ollama,
        prefer_ollama=True,
        cloud_enabled=True,
    )
    tutor._custom_adapters["k1"] = MockProviderAdapter(chunks=["Complete answer from Cloud."])

    events = []
    async for ev in tutor.stream("Explain sqlmap"):
        events.append(ev)

    statuses = [e for e in events if isinstance(e, TutorStatus)]
    tokens = [e for e in events if isinstance(e, TutorToken)]

    assert any("dropped mid-stream" in s.message for s in statuses)
    assert tokens[0].text == "Partial token before crash. "
    assert any("Complete answer from Cloud." in t.text for t in tokens)


@pytest.mark.asyncio
async def test_prefer_ollama_subsequent_questions_recover_without_manual_toggle():
    """Verify subsequent questions automatically retry and fall back to cloud without manual intervention."""
    ollama = OllamaBackend(model="gemma", base_url="http://127.0.0.1:54321")
    cloud_profile = CloudKeyProfile(
        id="k1", name="Cloud Provider", provider="openai", api_key="sk-real-key", model="gpt-4o"
    )
    tutor = ExplanationTutor(
        profiles=[cloud_profile],
        active_key_id="k1",
        ollama_backend=ollama,
        prefer_ollama=True,
        cloud_enabled=True,
    )
    tutor._custom_adapters["k1"] = MockProviderAdapter(chunks=["Answer 1"])

    # First question
    tokens1 = [e.text async for e in tutor.stream("Q1") if isinstance(e, TutorToken)]
    assert "".join(tokens1) == "Answer 1"

    # Second question (Ollama still offline, user does not need to toggle off Ollama)
    tutor._custom_adapters["k1"] = MockProviderAdapter(chunks=["Answer 2"])
    tokens2 = [e.text async for e in tutor.stream("Q2") if isinstance(e, TutorToken)]
    assert "".join(tokens2) == "Answer 2"
