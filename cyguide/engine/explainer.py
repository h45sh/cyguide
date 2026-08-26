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




class OllamaBackend(ExplainerBackend):
    """Backend that uses a local Ollama instance for LLM explanations."""

    def __init__(self, model: str = "gemma", base_url: str = "http://localhost:11434"):
        self.model = (model or "gemma").strip()
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")

    async def explain(self, prompt: str) -> AsyncIterator[str]:
        """Stream from local Ollama API."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }

        try:
            timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        yield f"Error: Ollama returned status {response.status_code}: {err_body.decode('utf-8', errors='replace')}"
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
            yield f"[Error: Ollama connection failed ({e}). Please ensure Ollama is running (`ollama serve`).]\n"


class CloudAPIBackend(ExplainerBackend):
    """Backend that uses cloud APIs (OpenAI, Anthropic, OpenRouter, Grok, Groq, etc)."""

    def __init__(self, api_type: str, api_base: str, api_key: str, model: str):
        self.api_type = (api_type or "openai").lower().strip()
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip('"\'')
        self.model = (model or "gpt-4o").strip().strip('"\'')

    async def explain(self, prompt: str) -> AsyncIterator[str]:
        """Stream from Cloud API."""
        headers = {}
        payload = {
            "model": self.model,
            "stream": True,
        }

        if self.api_type == "anthropic":
            url = f"{self.api_base}/messages"
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
            headers["content-type"] = "application/json"
            payload["max_tokens"] = 1024
            payload["messages"] = [{"role": "user", "content": prompt}]
        else:
            # Default to openai format (used by OpenAI, Groq, OpenRouter, Grok, etc)
            url = f"{self.api_base}/chat/completions"
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["content-type"] = "application/json"
            # Support openrouter specific headers optionally
            headers["HTTP-Referer"] = "https://github.com/Etrama0/cyguide"
            headers["X-Title"] = "CyGuide"
            payload["messages"] = [{"role": "user", "content": prompt}]

        try:
            timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        yield f"Error: API returned status {response.status_code}: {err_body.decode('utf-8', errors='replace')}"
                        return

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                            
                        try:
                            data = json.loads(data_str)
                            chunk = ""
                            if self.api_type == "anthropic":
                                if data.get("type") == "content_block_delta":
                                    chunk = data.get("delta", {}).get("text", "")
                            else:
                                choices = data.get("choices", [])
                                if choices:
                                    chunk = choices[0].get("delta", {}).get("content", "")
                            
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Error: cloud API request failed ({e}). No explanation backend is available.]\n"




class LearningExplainer:
    """Orchestrates explanations via the configured backend."""
    
    def __init__(self, backend: ExplainerBackend):
        self.backend = backend

    async def ask(self, prompt: str) -> AsyncIterator[str]:
        """Stream explanation from the backend."""
        async for chunk in self.backend.explain(prompt):
            yield chunk
