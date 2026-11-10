import pytest

from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.web import WebEndpoint
from tools.nikto.adapter import NiktoAdapter


@pytest.fixture
def adapter():
    return NiktoAdapter()

def test_nikto_validate_install(adapter):
    assert isinstance(adapter.validate_install(), bool)

def test_nikto_build_command(adapter):
    # 1. Target is web.endpoint
    endpoint = WebEndpoint.create(url="http://192.168.1.1:8080/test")
    cmd = adapter.build_command(endpoint, {"raw_flags": "-h {target} -Tuning x"})
    assert cmd[0] == "nikto"
    assert "-h" in cmd
    assert "http://192.168.1.1:8080/test" in cmd

    # 2. Target is network.service
    service = NetworkService.create(host_ip="10.0.0.5", port=443, protocol="tcp")
    cmd_svc = adapter.build_command(service, {"raw_flags": "-h {target} -p {port}"})
    assert "10.0.0.5" in cmd_svc
    assert "443" in cmd_svc

    # 3. Target is network.host
    host = NetworkHost.create(ip="127.0.0.1")
    cmd_host = adapter.build_command(host, {"raw_flags": "-h {target}"})
    assert "127.0.0.1" in cmd_host

@pytest.mark.asyncio
async def test_nikto_parse_output(adapter):
    sample_output = """
- Nikto v2.1.6
---------------------------------------------------------------------------
+ Target IP:          192.168.1.50
+ Target Hostname:    target.local
+ Target Port:        80
+ Start Time:         2026-08-26 12:00:00 (GMT0)
---------------------------------------------------------------------------
+ Server: Apache/2.4.41 (Ubuntu)
+ Retrieved x-powered-by header: PHP/7.4.3
+ /admin/: Directory indexing found.
+ OSVDB-3268: /icons/: Directory indexing found.
+ OSVDB-112004: /cgi-bin/test.cgi: Site appears vulnerable to the 'Shellshock' vulnerability.
+ OSVDB-3092: /test/: This might be interesting...
+ 0 host(s) tested
"""
    endpoint = WebEndpoint.create(url="http://192.168.1.50")
    findings = [f async for f in adapter.parse_output(sample_output, endpoint)]

    assert len(findings) >= 4
    
    # 1. Directory indexing finding
    dir_idx = next(f for f in findings if f.schema_type == "web.vulnerability" and "Directory indexing found" in f.data["description"] and "/admin/" in f.pik["url"])
    assert dir_idx.pik["url"] == "http://192.168.1.50/admin/"
    assert dir_idx.data["vuln_type"] == "misconfiguration"

    # 2. Shellshock OSVDB finding
    shellshock = next(f for f in findings if f.schema_type == "web.vulnerability" and "Shellshock" in f.data["description"])
    assert shellshock.pik["url"] == "http://192.168.1.50/cgi-bin/test.cgi"
    assert shellshock.data["vuln_type"] == "OSVDB-112004"

    # 3. Generic OSVDB finding with path
    osvdb_icon = next(f for f in findings if f.schema_type == "web.vulnerability" and "OSVDB-3268" in f.data["vuln_type"])
    assert osvdb_icon.pik["url"] == "http://192.168.1.50/icons/"

@pytest.mark.asyncio
async def test_nikto_parse_host_level_findings(adapter):
    sample_output = """
+ Server: Apache/2.4.41 (Ubuntu)
+ Retrieved x-powered-by header: PHP/7.4.3
"""
    host = NetworkHost.create(ip="10.0.0.1")
    findings = [f async for f in adapter.parse_output(sample_output, host)]

    assert len(findings) == 2
    for f in findings:
        assert f.schema_type == "vulnerability.found"
        assert f.pik["host_ip"] == "10.0.0.1"
        assert f.data["severity"] == "info"
