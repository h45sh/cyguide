"""Unit tests for the SearchSploit adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.vulnerability import ExploitReference, VulnerabilityFound
from tools.searchsploit.adapter import SearchSploitAdapter


@pytest.fixture
def adapter():
    return SearchSploitAdapter()


def test_searchsploit_build_command(adapter):
    # 1. Target is network.service
    service = NetworkService.create(
        host_ip="192.168.1.10",
        port=80,
        protocol="tcp",
        service_name="Apache",
        version="2.4.49",
    )
    cmd = adapter.build_command(service, {})
    assert cmd[0] == "searchsploit"
    assert "--json" in cmd
    assert "Apache 2.4.49" in cmd

    # 2. Target is vulnerability.found with CVE
    vuln = VulnerabilityFound.create(
        host_ip="192.168.1.10",
        vuln_id="CVE-2021-41773",
        title="Path Traversal",
        severity="critical",
    )
    cmd_vuln = adapter.build_command(vuln, {})
    assert "--cve" in cmd_vuln
    assert "CVE-2021-41773" in cmd_vuln

    # 3. Missing recognizable metadata raises ValueError
    empty_host = NetworkHost.create(ip="192.168.1.1")
    with pytest.raises(ValueError, match="recognizable service or CVE"):
        adapter.build_command(empty_host, {})


@pytest.mark.asyncio
async def test_searchsploit_parse_output(adapter):
    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "searchsploit.json"
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = NetworkService.create(
        host_ip="192.168.1.50",
        port=80,
        protocol="tcp",
        service_name="Apache",
        version="2.4.49",
    )
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    assert len(findings) == 2
    for f in findings:
        assert isinstance(f, ExploitReference)
        assert f.schema_type == "exploit.reference"

    # First exploit: EDB-50383
    f1 = findings[0]
    assert f1.pik["exploit_id"] == "EDB-50383"
    assert "Path Traversal & Remote Code Execution" in f1.data["title"]
    assert f1.data["cve_id"] == "CVE-2021-41773"
    assert f1.data["verified"] is True
    assert f1.data["exploit_type"] == "remote"
    assert f1.data["platform"] == "multiple"
    assert f1.parent is not None
    assert f1.parent.target_type == "network.service"
    assert f1.parent.target_pik["host_ip"] == "192.168.1.50"
    assert f1.parent.target_pik["port"] == 80

    # Second exploit: EDB-29290
    f2 = findings[1]
    assert f2.pik["exploit_id"] == "EDB-29290"
    assert f2.data["cve_id"] == "CVE-2012-1823"
    assert f2.data["verified"] is False
