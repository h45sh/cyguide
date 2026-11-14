"""Unit tests for the dnspython adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.dns import DnsRecord
from cyguide.schemas.network import NetworkHost
from tools.dnspython.adapter import DnsPythonAdapter


@pytest.fixture
def adapter():
    return DnsPythonAdapter()


def test_dnspython_validate_install(adapter):
    assert adapter.validate_install() is True


def test_dnspython_build_command(adapter):
    # 1. Target is dns.record
    dns_rec = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34")
    cmd = adapter.build_command(dns_rec, {"raw_flags": "-t MX"})
    assert "-m" in cmd
    assert "tools.dnspython.cli" in cmd
    assert "example.com" in cmd
    assert "--json" in cmd
    assert "-t" in cmd
    assert "MX" in cmd

    # 2. Target is network.host
    host = NetworkHost.create(ip="8.8.8.8")
    cmd_host = adapter.build_command(host, {"raw_flags": "-t PTR"})
    assert "8.8.8.8" in cmd_host
    assert "-t" in cmd_host
    assert "PTR" in cmd_host

    # 3. Missing query field raises ValueError
    empty_host = NetworkHost.create(ip="")
    empty_host.pik = {}
    with pytest.raises(ValueError, match="missing query field"):
        adapter.build_command(empty_host, {})


@pytest.mark.asyncio
async def test_dnspython_parse_output(adapter):
    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "dnspython.json"
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    assert len(findings) == 5
    types = [f.pik["type"] for f in findings]
    assert "A" in types
    assert "AAAA" in types
    assert "MX" in types
    assert "NS" in types
    assert "TXT" in types

    a_rec = next(f for f in findings if f.pik["type"] == "A")
    assert a_rec.pik["domain"] == "example.com"
    assert a_rec.data["value"] == "93.184.216.34"
    assert a_rec.data["resolved_ip"] == "93.184.216.34"
    assert len(a_rec.associations) == 1
    assert a_rec.associations[0].target_type == "network.host"
    assert a_rec.associations[0].target_pik["ip"] == "93.184.216.34"

    mx_rec = next(f for f in findings if f.pik["type"] == "MX")
    assert mx_rec.data["value"] == "10 mail.example.com"


@pytest.mark.asyncio
async def test_dnspython_parse_empty_or_malformed(adapter):
    target = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34")
    # Empty string
    findings = [f async for f in adapter.parse_output("", target)]
    assert len(findings) == 0

    # Malformed JSON
    findings = [f async for f in adapter.parse_output("random error message", target)]
    assert len(findings) == 0
