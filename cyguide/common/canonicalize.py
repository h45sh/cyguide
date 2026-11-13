"""Normalization filters for finding data."""

from urllib.parse import urlparse, urlunparse


def canonicalize(value):
    """Apply normalization rules based on the type of value."""
    if isinstance(value, str):
        # General string cleaning
        value = value.strip()

        # Lowercase hostnames (heuristic: no spaces, contains dots or is localhost)
        if "." in value or value.lower() == "localhost":
            if " " not in value and ":" not in value:
                return value.lower()

    return value


def canonicalize_host(ip_or_name: str) -> str:
    """Normalize IP addresses and hostnames."""
    val = ip_or_name.strip().lower()
    if val in ("localhost", "127.0.0.1", "::1"):
        return "127.0.0.1"
    # Basic IP normalization (lowercase IPv6, etc)
    return val


def canonicalize_url(url: str) -> str:
    """Normalize a URL: lowercase scheme/host, strip default ports."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Strip default ports
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        return urlunparse(
            (scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
    except Exception:
        return url


def canonicalize_port(port) -> int:
    """Ensure port is an integer."""
    try:
        return int(port)
    except (ValueError, TypeError):
        return 0


def canonicalize_field(key: str, value) -> object:
    """Normalize a specific key-value pair based on semantic key naming conventions."""
    if value is None:
        return None

    k = str(key).lower()
    if k in ("ip", "host_ip", "resolved_ip", "target_ip"):
        if isinstance(value, str):
            return canonicalize_host(value)
    elif k in ("port",):
        return canonicalize_port(value)
    elif k in ("url", "endpoint"):
        if isinstance(value, str):
            return canonicalize_url(value)
    elif k in ("protocol",):
        if isinstance(value, str):
            return value.strip().lower()

    return canonicalize(value)


def canonicalize_mapping(data: dict) -> dict:
    """Recursively canonicalize keys and values in a dictionary."""
    normalized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            normalized[k] = canonicalize_mapping(v)
        elif isinstance(v, list):
            normalized[k] = [
                canonicalize_mapping(item)
                if isinstance(item, dict)
                else canonicalize_field(k, item)
                for item in v
            ]
        else:
            normalized[k] = canonicalize_field(k, v)
    return normalized
