"""Unit tests for the Nuclei adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.network import NetworkHost
from cyguide.schemas.vulnerability import AuditMisconfig, VulnerabilityFound
from cyguide.schemas.web import WebEndpoint, WebTechnology
from tools.nuclei.adapter import NucleiAdapter


@pytest.fixture
def adapter():
    return NucleiAdapter()


def test_nuclei_build_command(adapter):
    # 1. Target is web.endpoint
    endpoint = WebEndpoint.create(url="http://example.com")
    cmd = adapter.build_command(endpoint, {})
    assert cmd[0] == "nuclei"
    assert "-u" in cmd
    url_idx = cmd.index("-u") + 1
    assert cmd[url_idx] == "http://example.com"
    assert "-jsonl" in cmd
    assert "-silent" in cmd

    # 2. Target is network.host
    host = NetworkHost.create(ip="10.0.0.1")
    cmd_host = adapter.build_command(host, {"raw_flags": "-severity critical"})
    assert "-u" in cmd_host
    assert "http://10.0.0.1" in cmd_host
    assert "-severity" in cmd_host
    assert "critical" in cmd_host


@pytest.mark.asyncio
async def test_nuclei_parse_jsonl_output(adapter):
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "nuclei.jsonl"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = WebEndpoint.create(url="http://example.com", host_ip="93.184.216.34")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    assert len(findings) == 3

    vulns = [f for f in findings if isinstance(f, VulnerabilityFound)]
    techs = [f for f in findings if isinstance(f, WebTechnology)]
    misconfigs = [f for f in findings if isinstance(f, AuditMisconfig)]

    # 1. Vulnerability finding
    assert len(vulns) == 1
    v = vulns[0]
    assert v.pik["vuln_id"] == "CVE-2021-41773"
    assert v.data["severity"] == "critical"
    assert v.pik["host_ip"] == "93.184.216.34"

    # 2. Technology detection
    assert len(techs) == 1
    t = techs[0]
    assert t.pik["technology_name"] == "Nginx Web Server"
    assert t.data["version"] == "1.18.0"
    assert t.data["confidence"] == 1.0

    # 3. Misconfiguration finding
    assert len(misconfigs) == 1
    m = misconfigs[0]
    assert m.pik["check_id"] == "git-config-exposure"
    assert m.data["severity"] == "medium"
    assert m.data["remediation"] == "Remove .git directory from public webroot."

