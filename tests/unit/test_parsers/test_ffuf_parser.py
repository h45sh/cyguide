"""Unit tests for the FFUF adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.vulnerability import AuditMisconfig
from cyguide.schemas.web import WebEndpoint
from tools.ffuf.adapter import FfufAdapter


@pytest.fixture
def adapter():
    return FfufAdapter()


def test_ffuf_build_command(adapter):
    # 1. Target is web.endpoint
    endpoint = WebEndpoint.create(url="http://example.com")
    cmd = adapter.build_command(endpoint, {})
    assert cmd[0] == "ffuf"
    assert "-u" in cmd
    idx_u = cmd.index("-u")
    assert cmd[idx_u + 1] == "http://example.com/FUZZ"
    assert "-w" in cmd
    assert "-of" in cmd
    assert "json" in cmd

    # 2. Macro substitution in raw flags
    cmd_custom = adapter.build_command(
        endpoint,
        {"raw_flags": "-u http://example.com/api/FUZZ -w {wordlist:common_dirs} -mc 200"},
    )
    assert "-mc" in cmd_custom
    assert "{wordlist:" not in " ".join(cmd_custom)


@pytest.mark.asyncio
async def test_ffuf_parse_json_output(adapter):
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "ffuf.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = WebEndpoint.create(url="http://example.com", host_ip="93.184.216.34")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    endpoints = [f for f in findings if isinstance(f, WebEndpoint)]
    misconfigs = [f for f in findings if isinstance(f, AuditMisconfig)]

    # 3 WebEndpoint findings
    assert len(endpoints) == 3
    urls = [e.pik["url"] for e in endpoints]
    assert "http://example.com/admin" in urls
    assert "http://example.com/.env" in urls
    assert "http://example.com/login" in urls

    env_endpoint = next(e for e in endpoints if e.pik["url"] == "http://example.com/.env")
    assert env_endpoint.data["status_code"] == 200
    assert env_endpoint.data["content_length"] == 450

    # Sensitive exposures detected as audit.misconfig
    assert len(misconfigs) >= 1
    env_misconfig = next(m for m in misconfigs if ".env" in m.pik["target"])
    assert env_misconfig.pik["check_id"] == "exposed-sensitive-file"
    assert env_misconfig.data["severity"] == "high"


@pytest.mark.asyncio
async def test_ffuf_parse_line_fallback(adapter):
    line_output = """
admin                   [Status: 200, Size: 1256, Words: 84, Lines: 15, Duration: 4ms]
login                   [Status: 302, Size: 0, Words: 0, Lines: 1, Duration: 3ms]
"""
    target = WebEndpoint.create(url="http://example.com")
    findings = [f async for f in adapter.parse_output(line_output, target)]

    assert len(findings) >= 2
    endpoints = [f for f in findings if isinstance(f, WebEndpoint)]
    assert len(endpoints) == 2
    assert endpoints[0].pik["url"] == "http://example.com/admin"
    assert endpoints[0].data["status_code"] == 200
    assert endpoints[0].data["content_length"] == 1256

