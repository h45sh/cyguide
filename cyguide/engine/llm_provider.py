"""Low-level transport and provider adapters for LLM inference (OpenAI, Anthropic, Ollama)."""

import abc
import json
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

import httpx

__all__ = [
    "AnthropicProviderAdapter",
    "CloudKeyProfile",
    "ExplainerBackend",
    "MockProviderAdapter",
    "OllamaBackend",
    "OpenAIProviderAdapter",
    "ProviderAdapter",
    "ProviderResponseError",
    "create_provider_adapter",
]


class ExplainerBackend(abc.ABC):
    """Abstract base class for explanation engines (Template, Ollama, etc)."""

    @abc.abstractmethod
    async def explain(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Generate a streamed explanation for a given prompt."""
        pass


class ProviderResponseError(Exception):
    """Raised when an inference provider returns a non-200 HTTP response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        body: str = "",
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.retry_after = retry_after


@runtime_checkable
class ProviderAdapter(Protocol):
    """Protocol for interacting with an LLM inference provider."""

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream response chunks from the model."""
        ...


class OpenAIProviderAdapter:
    """Adapter for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
        max_tokens: int = 1500,
    ):
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip("\"'")
        self.model = (model or "gpt-4o").strip().strip("\"'")
        self.extra_headers = extra_headers or {}
        self.max_tokens = max_tokens

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
            "HTTP-Referer": "https://github.com/h45sh/cyguide",
            "X-Title": "CyGuide",
        }
        headers.update(self.extra_headers)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": messages,
        }
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens

        timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = (await response.aread()).decode("utf-8", errors="replace")
                    retry_after = None
                    headers_obj = getattr(response, "headers", None)
                    retry_header = (
                        headers_obj.get("retry-after") if hasattr(headers_obj, "get") else None
                    )
                    if retry_header:
                        try:
                            retry_after = float(str(retry_header).strip())
                        except (ValueError, TypeError):
                            pass
                    raise ProviderResponseError(
                        status_code=response.status_code,
                        message=f"API error ({response.status_code}): {err_body}",
                        body=err_body,
                        retry_after=retry_after,
                    )

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            chunk = choices[0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
                    except json.JSONDecodeError:
                        continue


class AnthropicProviderAdapter:
    """Adapter for Anthropic Messages API."""

    def __init__(self, api_base: str, api_key: str, model: str, max_tokens: int = 2048):
        self.api_base = (api_base or "https://api.anthropic.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip("\"'")
        self.model = (model or "claude-3-5-sonnet-20241022").strip().strip("\"'")
        self.max_tokens = max_tokens

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        url = f"{self.api_base}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = (await response.aread()).decode("utf-8", errors="replace")
                    retry_after = None
                    headers_obj = getattr(response, "headers", None)
                    retry_header = (
                        headers_obj.get("retry-after") if hasattr(headers_obj, "get") else None
                    )
                    if retry_header:
                        try:
                            retry_after = float(str(retry_header).strip())
                        except (ValueError, TypeError):
                            pass
                    raise ProviderResponseError(
                        status_code=response.status_code,
                        message=f"API error ({response.status_code}): {err_body}",
                        body=err_body,
                        retry_after=retry_after,
                    )

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            chunk = data.get("delta", {}).get("text", "")
                            if chunk:
                                yield chunk
                    except json.JSONDecodeError:
                        continue


class MockProviderAdapter:
    """Hermetic mock adapter for unit testing without network or OS dependencies."""

    def __init__(self, chunks: Optional[List[str]] = None, fail_with: Optional[Exception] = None):
        self.chunks = chunks or ["Mock explanation chunk."]
        self.fail_with = fail_with

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        if self.fail_with:
            raise self.fail_with
        for c in self.chunks:
            yield c


class OllamaBackend(ExplainerBackend):
    """Backend that uses a local Ollama instance for LLM explanations."""

    def __init__(
        self,
        model: str = "gemma",
        base_url: str = "http://localhost:11434",
        connect_timeout: float = 1.5,
    ):
        self.model = (model or "gemma").strip()
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.connect_timeout = float(connect_timeout)
        self.last_error: Optional[str] = None

    async def explain(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream from local Ollama API."""
        self.last_error = None
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            payload["system"] = system

        try:
            timeout_config = httpx.Timeout(
                connect=self.connect_timeout, read=60.0, write=10.0, pool=5.0
            )
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_body = (await response.aread()).decode("utf-8", errors="replace")
                        err_msg = (
                            f"Ollama returned status {response.status_code}: {err_body} "
                            f"(Ensure model '{self.model}' is installed via `ollama pull {self.model}`)"
                        )
                        self.last_error = err_msg
                        yield f"Error: Ollama returned status {response.status_code}: {err_body}"
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
            self.last_error = f"Ollama connection failed ({e}). Please ensure Ollama is running (`ollama serve`) at {self.base_url}."
            yield f"[Error: Ollama connection failed ({e}). Please ensure Ollama is running (`ollama serve`).]\n"

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Conform to ProviderAdapter protocol for unified streaming."""
        async for chunk in self.explain(prompt, system=system):
            yield chunk


@dataclass
class CloudKeyProfile:
    """Configuration profile for a single cloud AI API key with health tracking."""

    id: str
    name: str
    provider: str  # openai, groq, anthropic, openrouter, custom
    api_key: str
    model: str = "gpt-4o"
    base_url: str = ""
    enabled: bool = True
    cooldown_until: float = 0.0
    last_status: str = "unknown"  # unknown, ok, rate_limited, error

    def is_in_cooldown(self) -> bool:
        """Return True if key is currently rate-limited and within cooldown."""
        return time.time() < self.cooldown_until

    def set_cooldown(self, seconds: float = 60.0) -> None:
        """Mark this key in cooldown for a given duration."""
        self.cooldown_until = time.time() + seconds
        self.last_status = "rate_limited"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "api_key": self.api_key,
            "model": self.model,
            "base_url": self.base_url,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudKeyProfile":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            provider=data.get("provider", "openai"),
            api_key=data.get("api_key", ""),
            model=data.get("model", "gpt-4o"),
            base_url=data.get("base_url", ""),
            enabled=data.get("enabled", True),
        )


def create_provider_adapter(
    profile: CloudKeyProfile,
    custom_adapters: Optional[Dict[str, ProviderAdapter]] = None,
    max_tokens: int = 1500,
) -> ProviderAdapter:
    """Factory creating an appropriate ProviderAdapter for a CloudKeyProfile."""
    if custom_adapters and profile.id in custom_adapters:
        return custom_adapters[profile.id]

    api_type = (profile.provider or "openai").lower().strip()
    base_url = (profile.base_url or "").rstrip("/").strip()
    model = (profile.model or "").strip()
    api_key = profile.api_key.strip().strip("\"'")

    if not base_url:
        if api_type == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif api_type == "anthropic":
            base_url = "https://api.anthropic.com/v1"
        elif api_type == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = "https://api.openai.com/v1"

    if (
        not model
        or (api_type == "anthropic" and model == "gpt-4o")
        or (api_type == "groq" and model == "gpt-4o")
    ):
        if api_type == "groq":
            model = "llama-3.3-70b-versatile"
        elif api_type == "anthropic":
            model = "claude-3-5-sonnet-20241022"
        elif api_type == "openrouter":
            model = "meta-llama/llama-3.3-70b-instruct"
        else:
            model = "gpt-4o"

    if api_type == "anthropic":
        return AnthropicProviderAdapter(
            api_base=base_url, api_key=api_key, model=model, max_tokens=max_tokens
        )
    return OpenAIProviderAdapter(
        api_base=base_url, api_key=api_key, model=model, max_tokens=max_tokens
    )
