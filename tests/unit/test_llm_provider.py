"""Unit tests for cyguide.engine.llm_provider."""

import pytest

from cyguide.engine.llm_provider import (
    AnthropicProviderAdapter,
    CloudKeyProfile,
    MockProviderAdapter,
    OpenAIProviderAdapter,
    ProviderResponseError,
    create_provider_adapter,
)


@pytest.mark.asyncio
async def test_mock_provider_adapter():
    adapter = MockProviderAdapter(chunks=["Chunk 1", " Chunk 2"])
    chunks = [c async for c in adapter.stream("Test prompt")]
    assert "".join(chunks) == "Chunk 1 Chunk 2"

    failing = MockProviderAdapter(fail_with=RuntimeError("Simulated provider failure"))
    with pytest.raises(RuntimeError, match="Simulated provider failure"):
        _ = [c async for c in failing.stream("Test prompt")]


def test_create_provider_adapter_factory():
    custom = {"custom-1": MockProviderAdapter(chunks=["Custom"])}
    prof_custom = CloudKeyProfile(id="custom-1", name="Custom", provider="openai", api_key="sk-1")
    assert create_provider_adapter(prof_custom, custom_adapters=custom) is custom["custom-1"]

    prof_anthropic = CloudKeyProfile(
        id="ant-1", name="Claude", provider="anthropic", api_key="sk-ant"
    )
    adapter_ant = create_provider_adapter(prof_anthropic)
    assert isinstance(adapter_ant, AnthropicProviderAdapter)
    assert adapter_ant.model == "claude-3-5-sonnet-20241022"

    prof_openai = CloudKeyProfile(id="oai-1", name="OpenAI", provider="openai", api_key="sk-oai")
    adapter_oai = create_provider_adapter(prof_openai)
    assert isinstance(adapter_oai, OpenAIProviderAdapter)
    assert adapter_oai.model == "gpt-4o"

    prof_groq = CloudKeyProfile(id="groq-1", name="Groq", provider="groq", api_key="gsk-1")
    adapter_groq = create_provider_adapter(prof_groq)
    assert isinstance(adapter_groq, OpenAIProviderAdapter)
    assert adapter_groq.api_base == "https://api.groq.com/openai/v1"
    assert adapter_groq.model == "llama-3.3-70b-versatile"


def test_cloud_key_profile_cooldown():
    profile = CloudKeyProfile(id="p1", name="Test", provider="openai", api_key="sk-test")
    assert profile.is_in_cooldown() is False
    profile.set_cooldown(10.0)
    assert profile.is_in_cooldown() is True
    assert profile.last_status == "rate_limited"


def test_provider_response_error_properties():
    err = ProviderResponseError(
        status_code=429, message="Rate limit", body="Limit reached", retry_after=5.5
    )
    assert err.status_code == 429
    assert err.retry_after == 5.5
    assert "Rate limit" in str(err)
