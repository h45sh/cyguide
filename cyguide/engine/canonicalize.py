# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""Normalization filters for finding data."""

import urllib.parse


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
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Strip default ports
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        return urllib.parse.urlunparse(
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
