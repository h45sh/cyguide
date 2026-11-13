from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyguide.engine.explainer import OllamaBackend


class AsyncMockIterator:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0).encode()


@pytest.mark.asyncio
async def test_ollama_backend_logic():
    """Test the logic of OllamaBackend by mocking the client stream."""
    backend = OllamaBackend(model="test-model")

    # 1. Setup the response mock
    # Note: aiter_lines() is a method that returns an async iterator
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.return_value = AsyncMockIterator(
        ['{"response": "Cy", "done": false}', '{"response": "Guide", "done": true}']
    )

    # 2. Setup the client mock
    mock_client = MagicMock()
    # stream() returns an object that is an async context manager
    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    stream_cm.__aexit__ = AsyncMock()
    mock_client.stream.return_value = stream_cm

    # 3. Patch the AsyncClient class
    with patch("httpx.AsyncClient") as mock_client_cls:
        client_cm = MagicMock()
        client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        client_cm.__aexit__ = AsyncMock()
        mock_client_cls.return_value = client_cm

        chunks = []
        async for chunk in backend.explain("test prompt"):
            chunks.append(chunk)

        assert "".join(chunks) == "CyGuide"
