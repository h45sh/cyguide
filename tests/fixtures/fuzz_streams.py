"""Fuzz stream fixtures and generator strategies for tool adapter stress testing.

Generates hostile and edge-case CLI stream outputs:
1. Malformed ANSI sequences and terminal control characters.
2. Truncated, incomplete, or corrupted JSON strings.
3. Giant single-line tokens without whitespace or newlines.
4. Binary noise, zero-byte sequences, and invalid UTF-8 decodings.
5. Unicode torture strings (surrogate halves, RTL overrides, zero-width spaces).
"""

from typing import List


def generate_fuzz_streams() -> List[str]:
    """Return a curated suite of hostile stdout/stderr streams to stress-test adapter parsers."""
    streams = [
        # 1. Empty and whitespace variations
        "",
        "   \t  \r\n\n\r  ",
        "\n" * 100,
        "\x00" * 50,
        # 2. Hostile / broken ANSI escape codes
        "\x1b[38;5;255m\x1b[48;5;0mText\x1b[0m",
        "\x1b[999;999;999mBrokenANSI\x1b[",
        "\x1b[1;2;3;4;5;6;7;8;9m" * 20,
        "Partial \x1b[31mRed text with no reset",
        # 3. Truncated / broken JSON
        '{"partial": true, "data": [1, 2, ',
        '{"status": 200, "url": "http://example.com/test", "nested": {',
        '{"key": "value"}\n{"unclosed": "brace"\n{"valid": 1}',
        # 4. Long single tokens (DOS/OOM prevention)
        "A" * 20000,
        ("Word " * 500) + ("\x1b[32mOK\x1b[0m " * 500),
        # 5. Unicode edge cases & control chars
        "Z̸a̷l̸g̷o̷ ̶t̶e̸x̵t̶ \u202eRTL_OVERRIDE\u202c \u200b\u200c\u200d\ufeff",
        "Emoji spam: 🚀🔥💀💥⚡️🛡️⚠️" * 50,
        # 6. Realistic mixed tool corruption (interrupted scan / crash banners)
        "Starting scan...\n[ERROR] Segmentation fault (core dumped)\n" + ("00" * 500),
        "PORT     STATE SERVICE\n80/tcp   open\n443/tcp\n---\n",
        # 7. Rapid alternating lines with special characters
        "\n".join(f"line_{i}: {'%' * (i % 20)} \t \x1b[33m{i}\x1b[0m" for i in range(100)),
    ]
    return streams
