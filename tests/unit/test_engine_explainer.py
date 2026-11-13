from typing import AsyncIterator

import pytest

from cyguide.engine.explainer import ExplainerBackend


class DummyBackend(ExplainerBackend):
    async def explain(self, prompt: str) -> AsyncIterator[str]:
        words = prompt.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


@pytest.mark.asyncio
async def test_explainer_ask():
    backend = DummyBackend()

    chunks = []
    async for chunk in backend.explain("Hello World"):
        chunks.append(chunk)

    explanation = "".join(chunks)
    assert explanation == "Hello World"


@pytest.mark.asyncio
async def test_dual_ai_error_when_no_cloud_keys_and_ollama_offline():
    from cyguide.engine.explainer import ExplanationTutor, OllamaBackend

    ollama = OllamaBackend(model="gemma", base_url="http://127.0.0.1:54321")
    backend = ExplanationTutor(
        profiles=[],
        fallback_to_ollama=True,
        ollama_backend=ollama,
        prefer_ollama=False,
        cloud_enabled=True,
    )

    chunks = []
    async for chunk in backend.explain("Explain nmap scan"):
        chunks.append(chunk)

    result = "".join(chunks)
    assert "AI Tutor Unavailable" in result
    assert "Cloud AI Error" in result
    assert "No cloud API keys are configured" in result or "API key not configured" in result
    assert "Local Ollama Error" in result
    assert "Ollama connection failed" in result


@pytest.mark.asyncio
async def test_dual_ai_error_when_cloud_auth_fails_and_ollama_offline():
    from unittest.mock import patch

    from cyguide.engine.explainer import CloudKeyProfile, ExplanationTutor, OllamaBackend

    k1 = CloudKeyProfile(id="k1", name="Groq Primary", provider="groq", api_key="bad-key")
    ollama = OllamaBackend(model="gemma", base_url="http://127.0.0.1:54321")
    backend = ExplanationTutor(
        profiles=[k1],
        active_key_id="k1",
        fallback_to_ollama=True,
        ollama_backend=ollama,
    )

    class MockErrContext:
        async def __aenter__(self):
            class ErrResp:
                status_code = 401

                async def aread(self):
                    return b"Invalid API Key"

            return ErrResp()

        async def __aexit__(self, *args):
            pass

    with patch("httpx.AsyncClient.stream", return_value=MockErrContext()):
        chunks = []
        async for chunk in backend.explain("Explain scan"):
            chunks.append(chunk)

        result = "".join(chunks)
        assert "AI Tutor Unavailable" in result
        assert "Cloud AI Error" in result
        assert "Authentication failed (401)" in result
        assert "Groq Primary" in result
        assert "Local Ollama Error" in result
        assert "Ollama connection failed" in result or "Ollama returned status" in result
