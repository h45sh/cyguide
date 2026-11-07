"""Explanation engine for Learning Mode."""

import abc
import json
import httpx
from typing import AsyncIterator, List, Optional, Dict, Any


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


from dataclasses import dataclass
import time
def is_placeholder_key(key: Optional[str]) -> bool:
    """Check if an API key is empty or a common placeholder/documentation string."""
    if not key:
        return True
    k = str(key).strip().strip('"\'').lower()
    if not k:
        return True
    placeholders = {
        "your_api_key_here",
        "your-api-key-here",
        "your_api_key",
        "your-api-key",
        "your_key_here",
        "api_key_here",
        "enter_your_key",
        "sk-...",
        "...",
        "none",
        "null",
        "dummy",
        "changeme",
        "placeholder",
    }
    return k in placeholders or k.startswith("your_api_key")


@dataclass
class CloudKeyProfile:
    """Represents a cloud AI API key profile with provider, endpoint, and status metrics."""
    id: str
    name: str = ""
    provider: str = "openai"  # openai, groq, anthropic, openrouter, etc.
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    enabled: bool = True
    cooldown_until: float = 0.0
    last_status: str = "ready"  # ready, ok, rate_limited, error

    def is_in_cooldown(self) -> bool:
        """Check if profile is currently in rate-limit cooldown."""
        return time.time() < self.cooldown_until

    def set_cooldown(self, seconds: float = 60.0) -> None:
        """Put profile on rate-limit cooldown."""
        self.cooldown_until = time.time() + seconds
        self.last_status = "rate_limited"

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary."""
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
        """Instantiate profile from dictionary."""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            provider=str(data.get("provider", "openai")),
            api_key=str(data.get("api_key", "")),
            model=str(data.get("model", "")),
            base_url=str(data.get("base_url", "")),
            enabled=bool(data.get("enabled", True)),
        )


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
            headers["HTTP-Referer"] = "https://github.com/h45sh/cyguide"
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


class MultiKeyCloudBackend(CloudAPIBackend):
    """Resilient Cloud API backend supporting multiple API keys, health tracking, and automatic fallback."""

    def __init__(
        self,
        profiles: List[CloudKeyProfile],
        active_key_id: Optional[str] = None,
        fallback_to_ollama: bool = False,
        ollama_backend: Optional[OllamaBackend] = None,
    ):
        self.profiles: List[CloudKeyProfile] = list(profiles or [])
        self.active_key_id: Optional[str] = active_key_id or (self.profiles[0].id if self.profiles else None)
        self.fallback_to_ollama: bool = fallback_to_ollama
        self.ollama_backend: Optional[OllamaBackend] = ollama_backend

        # Initialize base CloudAPIBackend properties from active profile
        active = self.get_active_profile()
        super().__init__(
            api_type=active.provider if active else "openai",
            api_base=active.base_url if active else "https://api.openai.com/v1",
            api_key=active.api_key if active else "",
            model=active.model if active else "gpt-4o",
        )

    def get_active_profile(self) -> Optional[CloudKeyProfile]:
        """Return the currently selected active profile."""
        if not self.profiles:
            return None
        for p in self.profiles:
            if p.id == self.active_key_id:
                return p
        return self.profiles[0]

    def set_active_key(self, key_id: str) -> bool:
        """Switch the active key by id."""
        for p in self.profiles:
            if p.id == key_id:
                self.active_key_id = key_id
                self.api_type = p.provider or "openai"
                self.api_base = p.base_url or "https://api.openai.com/v1"
                self.api_key = p.api_key
                self.model = p.model or "gpt-4o"
                return True
        return False

    def get_priority_chain(self) -> List[CloudKeyProfile]:
        """Return ordered list of enabled profiles to attempt: active key first, then secondary keys."""
        enabled = [p for p in self.profiles if p.enabled and p.api_key and not is_placeholder_key(p.api_key)]
        if not enabled:
            return []
        active = self.get_active_profile()
        chain: List[CloudKeyProfile] = []
        if active and active in enabled:
            chain.append(active)
        for p in enabled:
            if p not in chain:
                chain.append(p)
        return chain

    async def explain(self, prompt: str) -> AsyncIterator[str]:
        """Stream from cloud API with automatic fallback across configured keys and optional Ollama fallback."""
        chain = self.get_priority_chain()
        if not chain:
            if self.fallback_to_ollama and self.ollama_backend:
                async for chunk in self.ollama_backend.explain(prompt):
                    yield chunk
                return
            yield "[Error: No cloud API keys are configured or enabled. Please add an API key in Config.]\n"
            return

        last_errors = []
        for idx, profile in enumerate(chain):
            # Check rate-limit cooldown
            if profile.is_in_cooldown():
                # If there are other non-cooldown keys, skip this one
                non_cooldown = [p for p in chain if not p.is_in_cooldown()]
                if non_cooldown and profile not in non_cooldown:
                    continue

            api_type = (profile.provider or "openai").lower().strip()
            base_url = (profile.base_url or "").rstrip("/").strip()
            model = (profile.model or "").strip()
            api_key = profile.api_key.strip().strip('"\'')

            # Apply sensible provider defaults if base or model were left blank
            if not base_url:
                if api_type == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                elif api_type == "anthropic":
                    base_url = "https://api.anthropic.com/v1"
                elif api_type == "openrouter":
                    base_url = "https://openrouter.ai/api/v1"
                else:
                    base_url = "https://api.openai.com/v1"

            if not model:
                if api_type == "groq":
                    model = "llama-3.3-70b-versatile"
                elif api_type == "anthropic":
                    model = "claude-3-5-sonnet-20241022"
                elif api_type == "openrouter":
                    model = "meta-llama/llama-3.3-70b-instruct"
                else:
                    model = "gpt-4o"

            headers: Dict[str, str] = {}
            payload: Dict[str, Any] = {
                "model": model,
                "stream": True,
            }

            if api_type == "anthropic":
                req_url = f"{base_url}/messages"
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
                headers["content-type"] = "application/json"
                payload["max_tokens"] = 1024
                payload["messages"] = [{"role": "user", "content": prompt}]
            else:
                req_url = f"{base_url}/chat/completions"
                headers["Authorization"] = f"Bearer {api_key}"
                headers["content-type"] = "application/json"
                headers["HTTP-Referer"] = "https://github.com/h45sh/cyguide"
                headers["X-Title"] = "CyGuide"
                payload["messages"] = [{"role": "user", "content": prompt}]

            has_yielded = False
            try:
                timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    async with client.stream("POST", req_url, headers=headers, json=payload) as response:
                        if response.status_code == 429:
                            profile.set_cooldown(60.0)
                            err_body = (await response.aread()).decode("utf-8", errors="replace")
                            err_msg = f"Rate limit reached (429) on '{profile.name or profile.provider}'"
                            last_errors.append(err_msg)
                            if idx < len(chain) - 1:
                                yield f"[Notice: {err_msg}. Falling back to next key...]\n\n"
                                continue
                            break

                        if response.status_code in (401, 403):
                            profile.last_status = "error"
                            err_body = (await response.aread()).decode("utf-8", errors="replace")
                            err_msg = f"Authentication failed ({response.status_code}) on '{profile.name or profile.provider}'"
                            last_errors.append(err_msg)
                            if idx < len(chain) - 1:
                                yield f"[Notice: {err_msg}. Falling back to next key...]\n\n"
                                continue
                            break

                        if response.status_code >= 500:
                            profile.last_status = "error"
                            err_body = (await response.aread()).decode("utf-8", errors="replace")
                            err_msg = f"Server error ({response.status_code}) on '{profile.name or profile.provider}'"
                            last_errors.append(err_msg)
                            if idx < len(chain) - 1:
                                yield f"[Notice: {err_msg}. Falling back to next key...]\n\n"
                                continue
                            break

                        if response.status_code != 200:
                            err_body = (await response.aread()).decode("utf-8", errors="replace")
                            err_msg = f"API error ({response.status_code}) on '{profile.name or profile.provider}': {err_body}"
                            last_errors.append(err_msg)
                            if idx < len(chain) - 1:
                                yield f"[Notice: {err_msg}. Falling back to next key...]\n\n"
                                continue
                            break

                        # Successful response stream
                        profile.last_status = "ok"
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
                                if api_type == "anthropic":
                                    if data.get("type") == "content_block_delta":
                                        chunk = data.get("delta", {}).get("text", "")
                                else:
                                    choices = data.get("choices", [])
                                    if choices:
                                        chunk = choices[0].get("delta", {}).get("content", "")

                                if chunk:
                                    has_yielded = True
                                    yield chunk
                            except json.JSONDecodeError:
                                continue

                        if has_yielded:
                            return

            except Exception as e:
                profile.last_status = "error"
                err_msg = f"Connection error on '{profile.name or profile.provider}': {e}"
                last_errors.append(err_msg)
                if idx < len(chain) - 1:
                    yield f"[Notice: {err_msg}. Falling back to next key...]\n\n"
                    continue

        # If all cloud keys failed
        if self.fallback_to_ollama and self.ollama_backend:
            yield f"[Notice: All cloud keys failed. Falling back to Local Ollama ({self.ollama_backend.model})...]\n\n"
            async for chunk in self.ollama_backend.explain(prompt):
                yield chunk
            return

        summary = " | ".join(last_errors) if last_errors else "All cloud API keys failed"
        yield f"[Error: Cloud API request failed ({summary}). No explanation backend is available.]\n"


class LearningExplainer:
    """Orchestrates explanations via the configured backend."""

    def __init__(self, backend: ExplainerBackend):
        self.backend = backend

    async def ask(self, prompt: str) -> AsyncIterator[str]:
        """Stream explanation from the backend."""
        async for chunk in self.backend.explain(prompt):
            yield chunk
