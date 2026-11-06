import pytest
from typing import AsyncIterator
from cyguide.engine.explainer import LearningExplainer, ExplainerBackend

class DummyBackend(ExplainerBackend):
    async def explain(self, prompt: str) -> AsyncIterator[str]:
        words = prompt.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

@pytest.mark.asyncio
async def test_explainer_ask():
    backend = DummyBackend()
    explainer = LearningExplainer(backend)

    chunks = []
    async for chunk in explainer.ask("Hello World"):
        chunks.append(chunk)

    explanation = "".join(chunks)
    assert explanation == "Hello World"
