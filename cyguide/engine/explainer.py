"""Explanation engine for Learning Mode and AI Tutoring."""

import abc
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

import httpx

# --- Typed Tutor Stream Events ---


@dataclass(frozen=True)
class TutorEvent:
    """Base event emitted across the ExplanationTutor stream."""

    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class TutorToken(TutorEvent):
    """A streaming text chunk produced by the underlying AI model."""

    text: str = ""


@dataclass(frozen=True)
class TutorStatus(TutorEvent):
    """A status update or fallback notification (e.g. rate limit, key fallback)."""

    message: str = ""
    profile_id: Optional[str] = None
    is_warning: bool = False


@dataclass(frozen=True)
class TutorError(TutorEvent):
    """An error encountered during model communication."""

    error: str = ""
    is_fatal: bool = False
    cloud_error: Optional[str] = None
    ollama_error: Optional[str] = None


# --- Base Interfaces ---


class ExplainerBackend(abc.ABC):
    """Abstract base class for explanation engines (Template, Ollama, etc)."""

    @abc.abstractmethod
    async def explain(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Generate a streamed explanation for a given prompt."""
        pass

    async def ask(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream explanation from the backend (backward-compatible alias)."""
        import inspect

        sig = inspect.signature(self.explain)
        if "system" in sig.parameters:
            async for chunk in self.explain(prompt, system=system):
                yield chunk
        else:
            async for chunk in self.explain(prompt):
                yield chunk


def format_dual_ai_error(cloud_err: str, ollama_err: str) -> str:
    """Format a clear diagnostic block when both Cloud AI and Local Ollama fail."""
    c_clean = str(cloud_err or "").strip().strip("[]").removeprefix("Error: ").strip()
    o_clean = str(ollama_err or "").strip().strip("[]").removeprefix("Error: ").strip()
    if not c_clean:
        c_clean = "No cloud API keys are configured or enabled. Configure an API key in Settings (Ctrl+P -> Cloud API) or export CYGUIDE_API_KEY."
    if not o_clean:
        o_clean = "Ollama connection failed. Please ensure Ollama is running (`ollama serve`)."

    return (
        f"\n> [!] **AI Tutor Unavailable**\n"
        f">\n"
        f"> **Cloud AI Error:**\n"
        f"> • {c_clean}\n"
        f">\n"
        f"> **Local Ollama Error:**\n"
        f"> • {o_clean}\n"
        f">\n"
        f"> *To enable AI tutoring, either run `ollama serve` locally or configure a Cloud API key in Settings (Ctrl+P -> Cloud API).*\n"
    )


# --- Provider Adapters (Ports & Adapters) ---


class ProviderResponseError(Exception):
    """Raised when an inference provider returns a non-200 HTTP response."""

    def __init__(self, status_code: int, message: str, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


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
    ):
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip("\"'")
        self.model = (model or "gpt-4o").strip().strip("\"'")
        self.extra_headers = extra_headers or {}

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

        payload = {
            "model": self.model,
            "stream": True,
            "messages": messages,
        }

        timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = (await response.aread()).decode("utf-8", errors="replace")
                    raise ProviderResponseError(
                        status_code=response.status_code,
                        message=f"API error ({response.status_code}): {err_body}",
                        body=err_body,
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

    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = (api_base or "https://api.anthropic.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip("\"'")
        self.model = (model or "claude-3-5-sonnet-20241022").strip().strip("\"'")

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
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = (await response.aread()).decode("utf-8", errors="replace")
                    raise ProviderResponseError(
                        status_code=response.status_code,
                        message=f"API error ({response.status_code}): {err_body}",
                        body=err_body,
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


class OllamaProviderAdapter:
    """Adapter for local Ollama generate API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma"):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model = (model or "gemma").strip()

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            payload["system"] = system

        timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = (await response.aread()).decode("utf-8", errors="replace")
                    raise ProviderResponseError(
                        status_code=response.status_code,
                        message=f"Ollama returned status {response.status_code}: {err_body}",
                        body=err_body,
                    )

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


# --- Legacy / Standalone Ollama Backend ---


class OllamaBackend(ExplainerBackend):
    """Backend that uses a local Ollama instance for LLM explanations."""

    def __init__(self, model: str = "gemma", base_url: str = "http://localhost:11434"):
        self.model = (model or "gemma").strip()
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
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
            timeout_config = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        err_body = (await response.aread()).decode("utf-8", errors="replace")
                        err_msg = f"Ollama returned status {response.status_code}: {err_body} (Ensure model '{self.model}' is installed via `ollama pull {self.model}`)"
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


# --- Profile Management ---


def is_placeholder_key(key: Optional[str]) -> bool:
    """Check if an API key is empty or a common placeholder/documentation string."""
    if not key:
        return True
    k = key.strip().lower()
    placeholders = {
        "your_api_key_here",
        "your-api-key",
        "placeholder",
        "none",
        "sk-...",
        "gsk_...",
    }
    return k in placeholders or k.startswith("your_") or k.startswith("sk-placeholder")


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


class CloudAPIBackend(ExplainerBackend):
    """Backend that uses cloud APIs (OpenAI, Anthropic, OpenRouter, Grok, Groq, etc)."""

    def __init__(self, api_type: str, api_base: str, api_key: str, model: str):
        self.api_type = (api_type or "openai").lower().strip()
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/").strip()
        self.api_key = (api_key or "").strip().strip("\"'")
        self.model = (model or "gpt-4o").strip().strip("\"'")

    async def explain(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream from Cloud API."""
        adapter: ProviderAdapter
        if self.api_type == "anthropic":
            adapter = AnthropicProviderAdapter(
                api_base=self.api_base,
                api_key=self.api_key,
                model=self.model,
            )
        else:
            adapter = OpenAIProviderAdapter(
                api_base=self.api_base,
                api_key=self.api_key,
                model=self.model,
            )

        try:
            async for chunk in adapter.stream(prompt, system=system):
                yield chunk
        except ProviderResponseError as e:
            yield f"Error: API returned status {e.status_code}: {e.body}"
        except Exception as e:
            yield f"[Error: cloud API request failed ({e}). No explanation backend is available.]\n"


# --- Deep Module: ExplanationTutor ---


class ExplanationTutor(CloudAPIBackend):
    """Deep module coordinating multi-provider AI learning guidance, automatic fallback,

    resilient rate-limit cooldowns, and typed event streams.
    """

    def __init__(
        self,
        profiles: Optional[List[CloudKeyProfile]] = None,
        active_key_id: Optional[str] = None,
        fallback_to_ollama: bool = False,
        ollama_backend: Optional[OllamaBackend] = None,
        prefer_ollama: bool = False,
        cloud_enabled: bool = True,
    ):
        self.profiles: List[CloudKeyProfile] = list(profiles or [])
        self.active_key_id: Optional[str] = active_key_id or (
            self.profiles[0].id if self.profiles else None
        )
        self.fallback_to_ollama: bool = fallback_to_ollama
        self.ollama_backend: Optional[OllamaBackend] = ollama_backend
        self.prefer_ollama: bool = prefer_ollama
        self.cloud_enabled: bool = cloud_enabled

        # Internal custom adapters for testing injection
        self._custom_adapters: Dict[str, ProviderAdapter] = {}

        # Initialize base properties from active profile for backward compatibility
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
        """Switch the active key by id and update internal adapter state in place."""
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
        """Return ordered list of enabled profiles: active key first, then secondary keys."""
        if not self.cloud_enabled:
            return []
        enabled = [
            p
            for p in self.profiles
            if p.enabled and p.api_key and not is_placeholder_key(p.api_key)
        ]
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

    def get_adapter_for_profile(self, profile: CloudKeyProfile) -> ProviderAdapter:
        """Resolve the internal ProviderAdapter for a specific profile."""
        if profile.id in self._custom_adapters:
            return self._custom_adapters[profile.id]

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

        if not model:
            if api_type == "groq":
                model = "llama-3.3-70b-versatile"
            elif api_type == "anthropic":
                model = "claude-3-5-sonnet-20241022"
            elif api_type == "openrouter":
                model = "meta-llama/llama-3.3-70b-instruct"
            else:
                model = "gpt-4o"

        if api_type == "anthropic":
            return AnthropicProviderAdapter(api_base=base_url, api_key=api_key, model=model)
        return OpenAIProviderAdapter(api_base=base_url, api_key=api_key, model=model)

    def _call_ollama_explain(self, prompt: str, system: Optional[str] = None):
        """Invoke OllamaBackend with inspection of supported arguments."""
        if not self.ollama_backend:

            async def _empty():
                if False:
                    yield ""

            return _empty()
        import inspect

        sig = inspect.signature(self.ollama_backend.explain)
        if "system" in sig.parameters:
            return self.ollama_backend.explain(prompt, system=system)
        return self.ollama_backend.explain(prompt)

    async def stream(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[TutorEvent]:
        """Stream typed TutorEvents across priority chains, cooldowns, and fallbacks."""
        ollama_pre_err: Optional[str] = None

        if self.prefer_ollama:
            first = True
            ollama_failed = False
            if self.ollama_backend:
                try:
                    async for chunk in self._call_ollama_explain(prompt, system=system):
                        if first:
                            if chunk.startswith(
                                "[Error: Ollama connection failed"
                            ) or chunk.startswith("Error: Ollama returned status"):
                                ollama_failed = True
                                ollama_pre_err = (
                                    getattr(self.ollama_backend, "last_error", None)
                                    or chunk.strip()
                                )
                                break
                            first = False
                        yield TutorToken(text=chunk)
                except Exception as e:
                    ollama_failed = True
                    ollama_pre_err = f"Ollama connection failed ({e}). Ensure Ollama is running (`ollama serve`)."
            else:
                ollama_failed = True
                ollama_pre_err = "Local Ollama is not configured."

            if not ollama_failed:
                return

            if not self.cloud_enabled:
                yield TutorError(
                    error=format_dual_ai_error(
                        "Cloud AI access is disabled in settings.",
                        ollama_pre_err or "Ollama connection failed.",
                    ),
                    is_fatal=True,
                    cloud_error="Cloud AI access is disabled in settings.",
                    ollama_error=ollama_pre_err,
                )
                return

            chain = self.get_priority_chain()
            if not chain:
                yield TutorError(
                    error=format_dual_ai_error(
                        "No cloud API keys are configured or enabled. Please add an API key in Settings (Ctrl+P) or export CYGUIDE_API_KEY.",
                        ollama_pre_err or "Ollama connection failed.",
                    ),
                    is_fatal=True,
                    cloud_error="No cloud API keys are configured or enabled.",
                    ollama_error=ollama_pre_err,
                )
                return
        else:
            chain = self.get_priority_chain()

        if not chain:
            cloud_err = (
                "No cloud API keys are configured or enabled. Please add an API key in Settings (Ctrl+P) or export CYGUIDE_API_KEY."
                if self.cloud_enabled
                else "Cloud AI access is disabled in settings."
            )
            if self.fallback_to_ollama and self.ollama_backend:
                first = True
                ollama_failed = False
                ollama_err = ""
                try:
                    async for chunk in self._call_ollama_explain(prompt, system=system):
                        if first:
                            if chunk.startswith(
                                "[Error: Ollama connection failed"
                            ) or chunk.startswith("Error: Ollama returned status"):
                                ollama_failed = True
                                ollama_err = (
                                    getattr(self.ollama_backend, "last_error", None)
                                    or chunk.strip()
                                )
                                break
                            first = False
                            yield TutorStatus(
                                message=f"Cloud AI key not configured. Falling back to Local Ollama ({self.ollama_backend.model})..."
                            )
                        yield TutorToken(text=chunk)
                except Exception as e:
                    ollama_failed = True
                    ollama_err = f"Ollama connection failed ({e}). Ensure Ollama is running (`ollama serve`)."

                if ollama_failed:
                    yield TutorError(
                        error=format_dual_ai_error(cloud_err, ollama_err),
                        is_fatal=True,
                        cloud_error=cloud_err,
                        ollama_error=ollama_err,
                    )
                return

            yield TutorError(error=cloud_err, is_fatal=True, cloud_error=cloud_err)
            return

        last_errors = []
        for idx, profile in enumerate(chain):
            if profile.is_in_cooldown():
                non_cooldown = [p for p in chain if not p.is_in_cooldown()]
                if non_cooldown and profile not in non_cooldown:
                    continue

            adapter = self.get_adapter_for_profile(profile)
            has_yielded = False
            try:
                async for chunk in adapter.stream(prompt, system=system):
                    has_yielded = True
                    yield TutorToken(text=chunk)

                if has_yielded:
                    profile.last_status = "ok"
                    return

            except ProviderResponseError as e:
                sc = e.status_code
                if sc == 429:
                    profile.set_cooldown(60.0)
                    err_msg = f"Rate limit reached (429) on '{profile.name or profile.provider}'"
                    last_errors.append(err_msg)
                    if idx < len(chain) - 1:
                        yield TutorStatus(
                            message=f"{err_msg}. Falling back to next key...",
                            profile_id=profile.id,
                            is_warning=True,
                        )
                        continue
                    break

                if sc in (401, 403):
                    profile.last_status = "error"
                    err_msg = (
                        f"Authentication failed ({sc}) on '{profile.name or profile.provider}'"
                    )
                    last_errors.append(err_msg)
                    if idx < len(chain) - 1:
                        yield TutorStatus(
                            message=f"{err_msg}. Falling back to next key...",
                            profile_id=profile.id,
                            is_warning=True,
                        )
                        continue
                    break

                if sc >= 500:
                    profile.last_status = "error"
                    err_msg = f"Server error ({sc}) on '{profile.name or profile.provider}'"
                    last_errors.append(err_msg)
                    if idx < len(chain) - 1:
                        yield TutorStatus(
                            message=f"{err_msg}. Falling back to next key...",
                            profile_id=profile.id,
                            is_warning=True,
                        )
                        continue
                    break

                profile.last_status = "error"
                err_msg = f"API error ({sc}) on '{profile.name or profile.provider}': {e.body}"
                last_errors.append(err_msg)
                if idx < len(chain) - 1:
                    yield TutorStatus(
                        message=f"{err_msg}. Falling back to next key...",
                        profile_id=profile.id,
                        is_warning=True,
                    )
                    continue
                break

            except Exception as e:
                profile.last_status = "error"
                err_msg = f"Connection error on '{profile.name or profile.provider}': {e}"
                last_errors.append(err_msg)
                if idx < len(chain) - 1:
                    yield TutorStatus(
                        message=f"{err_msg}. Falling back to next key...",
                        profile_id=profile.id,
                        is_warning=True,
                    )
                    continue

        summary = " | ".join(last_errors) if last_errors else "All cloud API keys failed"
        if ollama_pre_err:
            yield TutorError(
                error=format_dual_ai_error(summary, ollama_pre_err),
                is_fatal=True,
                cloud_error=summary,
                ollama_error=ollama_pre_err,
            )
            return

        if self.fallback_to_ollama and self.ollama_backend:
            first = True
            ollama_failed = False
            ollama_err = ""
            try:
                async for chunk in self._call_ollama_explain(prompt, system=system):
                    if first:
                        if chunk.startswith("[Error: Ollama connection failed") or chunk.startswith(
                            "Error: Ollama returned status"
                        ):
                            ollama_failed = True
                            ollama_err = (
                                getattr(self.ollama_backend, "last_error", None) or chunk.strip()
                            )
                            break
                        first = False
                        yield TutorStatus(
                            message=f"All cloud keys failed. Falling back to Local Ollama ({self.ollama_backend.model})..."
                        )
                    yield TutorToken(text=chunk)
            except Exception as e:
                ollama_failed = True
                ollama_err = (
                    f"Ollama connection failed ({e}). Ensure Ollama is running (`ollama serve`)."
                )

            if ollama_failed:
                yield TutorError(
                    error=format_dual_ai_error(summary, ollama_err),
                    is_fatal=True,
                    cloud_error=summary,
                    ollama_error=ollama_err,
                )
            return

        yield TutorError(
            error=f"[Error: Cloud API request failed ({summary}). No explanation backend is available.]\n",
            is_fatal=True,
            cloud_error=summary,
        )

    async def explain(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream plain text tokens with formatted notices and errors for backward compatibility."""
        async for event in self.stream(prompt, system=system):
            if isinstance(event, TutorToken):
                yield event.text
            elif isinstance(event, TutorStatus):
                yield f"[Notice: {event.message}]\n\n"
            elif isinstance(event, TutorError):
                if event.error.startswith("[Error:") or event.error.startswith("\n> [!]"):
                    yield event.error
                else:
                    yield f"[Error: {event.error}]\n"


# --- Class Alias for Full Backward Compatibility ---

MultiKeyCloudBackend = ExplanationTutor
