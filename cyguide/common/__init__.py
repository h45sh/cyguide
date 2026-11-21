"""Common shared primitives and utility functions."""

import re
from typing import List, Optional

from cyguide.common.algorithms import (
    BloomFilter,
    DisjointSet,
    IPRadixTrie,
    MinHash,
    knapsack_01,
)

__all__ = [
    "ANSI_ESCAPE_RE",
    "BloomFilter",
    "CTF_FLAG_RE",
    "DisjointSet",
    "IPRadixTrie",
    "MinHash",
    "dfa_strip_ansi",
    "extract_ctf_flags",
    "is_placeholder_key",
    "knapsack_01",
    "strip_ansi",
    "strip_scanner_noise",
]

# Canonical ANSI escape sequence regex covering 7-bit and 8-bit C1 controls, CSI, and OSC
ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Standard CTF flag auto-detection regex (flag{}, CTF{}, HTB{}, THM{}, etc.)
CTF_FLAG_RE = re.compile(r"(?:flag|FLAG|ctf|CTF|htb|HTB|thm|THM)\{[A-Za-z0-9_!@#$%^&*+=?.-]+\}")

# DFA States for ECMA-48 unrolled parser
_STATE_TEXT = 0
_STATE_ESC = 1
_STATE_CSI = 2
_STATE_OSC = 3
_STATE_OSC_ESC = 4


def strip_ansi(text: str) -> str:
    """Strip ANSI color codes, cursor sequences, and OSC title strings in strict linear time O(N)

    using an unrolled state machine without regex engine overhead.
    """
    if not text or "\x1b" not in text:
        return text

    out: List[str] = []
    state = _STATE_TEXT
    chunk_start = 0

    for i, ch in enumerate(text):
        if state == _STATE_TEXT:
            if ch == "\x1b":
                if i > chunk_start:
                    out.append(text[chunk_start:i])
                state = _STATE_ESC
        elif state == _STATE_ESC:
            if ch == "[":
                state = _STATE_CSI
            elif ch == "]":
                state = _STATE_OSC
            else:
                # 2-character escape sequence (e.g. \x1bM, \x1b7, \x1b8)
                state = _STATE_TEXT
                chunk_start = i + 1
        elif state == _STATE_CSI:
            # CSI parameter characters: 0x30-0x3F (0-9:;<=>?)
            # Intermediate characters: 0x20-0x2F ( !"#$%&'()*+,-./)
            # Final characters: 0x40-0x7E (@A-Z[\]^_`a-z{|}~)
            ord_c = ord(ch)
            if 0x40 <= ord_c <= 0x7E:
                state = _STATE_TEXT
                chunk_start = i + 1
        elif state == _STATE_OSC:
            # OSC is terminated by BEL (\x07) or String Terminator (\x1b\)
            if ch == "\x07":
                state = _STATE_TEXT
                chunk_start = i + 1
            elif ch == "\x1b":
                state = _STATE_OSC_ESC
        elif state == _STATE_OSC_ESC:
            if ch == "\\":
                state = _STATE_TEXT
                chunk_start = i + 1
            else:
                state = _STATE_OSC

    if state == _STATE_TEXT and chunk_start < len(text):
        out.append(text[chunk_start:])

    return "".join(out)


# Alias for backward compatibility
dfa_strip_ansi = strip_ansi


def extract_ctf_flags(text: str) -> List[str]:
    """Extract distinct CTF flag strings from text in order of appearance."""
    if not text:
        return []
    flags: List[str] = []
    seen = set()
    for match in CTF_FLAG_RE.finditer(text):
        f = match.group(0)
        if f not in seen:
            seen.add(f)
            flags.append(f)
    return flags


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


def strip_scanner_noise(raw_text: str) -> str:
    """Filter out repetitive scanner banner headers, ASCII art, and progress bars before LLM prompting."""
    cleaned_text = ANSI_ESCAPE_RE.sub("", raw_text)
    lines = cleaned_text.splitlines()
    cleaned = []
    noise_prefixes = (
        "Starting Nmap",
        "Nmap done:",
        "Gobuster v",
        "by OJ Reeves",
        "[-] Loaded",
        "[-] Target:",
        "[-] Flags:",
        "[-] Method:",
        "[-] Wordlist:",
        "[-] Extensions:",
        "[-] Mode:",
        "[-] Threads:",
        "[-] Timeout:",
        "- Nikto v",
        "+ Target IP:",
        "+ Target Hostname:",
        "+ Target Port:",
        "+ Start Time:",
        "+ End Time:",
        "+ 0 host(s) tested",
        ":: Method :",
        ":: URL :",
        ":: Wordlist :",
        ":: Header :",
        ":: Output :",
        ":: Follow :",
        "[INF] Current nuclei version:",
        "[INF] New templates added in nuclei-templates",
        "[INF] Loading templates...",
        "[INF] Using",
        "[INF] Target:",
        "[INF] Templates cluster",
        "[INF] Scan stats:",
        "[INF] Enumerating subdomains for",
        "% This is the RIPE Database",
        "% Rights restricted",
        "# whois.arin.net",
        "NOTICE: The expiration date",
        "___",
        "---",
        "===",
        "***",
    )
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if all(c in "=-_*~#./\\ " for c in stripped) and len(stripped) > 4:
            continue
        if "Progress:" in stripped or "Stats:" in stripped or "ETA:" in stripped:
            continue
        normalized = re.sub(r"^\[[\+\*\-\!]\]\s*", "", stripped)
        if any(stripped.startswith(p) or normalized.startswith(p) for p in noise_prefixes):
            continue
        if sum(1 for c in stripped if c in "/\\|`_") > len(stripped) * 0.5 and len(stripped) > 5:
            continue
        cleaned.append(stripped)

    return "\n".join(cleaned[-60:]) if cleaned else raw_text[-1500:]
