"""API key utilities and validation helpers."""

from typing import Optional

__all__ = ["is_placeholder_key"]


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
