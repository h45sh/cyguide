"""Normalization filters for finding data.

Re-exported from cyguide.common.canonicalize for backward compatibility.
"""

from cyguide.common.canonicalize import (
    canonicalize,
    canonicalize_host,
    canonicalize_port,
    canonicalize_url,
)

__all__ = [
    "canonicalize",
    "canonicalize_host",
    "canonicalize_port",
    "canonicalize_url",
]
