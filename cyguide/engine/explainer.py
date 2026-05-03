"""Explanation engine for Learning Mode."""

import abc
import asyncio
import json
import httpx
from typing import AsyncIterator, Dict, Any, List, Optional
from cyguide.engine.manifest import Manifest

class ExplainerBackend(abc.ABC):
    """Abstract base class for explanation engines (Template, Ollama, etc)."""
    
    @abc.abstractmethod
    async def explain(self, prompt: str) -> AsyncIterator[str]:
        """Generate a streamed explanation for a given prompt."""
        pass


class TemplateBackend(ExplainerBackend):
    """Zero-dependency backend that fills manifest-driven slots."""
    
    async def explain(self, prompt: str) -> AsyncIterator[str]:
        # For the template backend, we just "stream" the prompt itself.
        # In a real version, this might do some basic enrichment or lookup.
        words = prompt.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.01)


class OllamaBackend(ExplainerBackend):
    """Backend that uses a local Ollama instance for LLM explanations."""

    def __init__(self, model: str = "gemma", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def explain(self, prompt: str) -> AsyncIterator[str]:
        """Stream from local Ollama API."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"Error: Ollama returned status {response.status_code}"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            chunk = data.get("response", "")
                            if chunk:
                                yield chunk
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"Error connecting to Ollama: {e}"


class LearningExplainer:
    """Orchestrates milestone-to-prompt conversion and backend calls."""
    
    def __init__(self, backend: ExplainerBackend):
        self.backend = backend

    async def get_explanation(
        self, 
        manifest: Manifest, 
        trigger: str, 
        data: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """
        Find the prompt for a trigger in the manifest and call the backend.
        """
        if not manifest.learning or not manifest.learning.explainer:
            return

        # 1. Find the milestone prompt
        milestone = next((m for m in manifest.learning.explainer.milestones if m.trigger == trigger), None)
        if not milestone:
            return

        # 2. Fill the template safely
        prompt = milestone.prompt
        try:
            # Simple format: replaces {key} with data[key]
            prompt = prompt.format(**data)
        except (KeyError, IndexError, ValueError):
            # If formatting fails (e.g. missing keys), use the raw prompt
            pass

        # 3. Stream from backend
        async for chunk in self.backend.explain(prompt):
            yield chunk
