import pytest

from cyguide.schemas.network import NetworkService
from cyguide.schemas.web import WebEndpoint
from tools.gobuster.adapter import GobusterAdapter


@pytest.fixture
def adapter():
    return GobusterAdapter()


def test_gobuster_validate_install(adapter):
    assert isinstance(adapter.validate_install(), bool)


def test_gobuster_build_command(adapter):
    # 1. Target is web.endpoint
    endpoint = WebEndpoint.create(url="http://10.10.10.5/app")
    cmd = adapter.build_command(endpoint, {"raw_flags": "dir -u {url} -w {wordlist}"})
    assert cmd[0] == "gobuster"
    assert "dir" in cmd
    assert "-u" in cmd
    assert "http://10.10.10.5/app" in cmd
    assert any("wordlist.txt" in arg for arg in cmd)

    # 2. Target is network.service (HTTP)
    http_svc = NetworkService.create(host_ip="192.168.1.100", port=80, protocol="tcp")
    cmd_http = adapter.build_command(http_svc, {"raw_flags": "dir -u {url}"})
    assert "http://192.168.1.100:80" in cmd_http

    # 3. Target is network.service (HTTPS)
    https_svc = NetworkService.create(host_ip="192.168.1.100", port=443, protocol="tcp")
    cmd_https = adapter.build_command(https_svc, {"raw_flags": "dir -u {url}"})
    assert "https://192.168.1.100:443" in cmd_https


@pytest.mark.asyncio
async def test_gobuster_parse_output(adapter):
    sample_output = """
===============================================================
Gobuster v3.5
by OJ Reeves (@TheColonial) & Christian Mehlmauer (@firefart)
===============================================================
[+] Url:                     http://10.10.10.50:8080
[+] Method:                  GET
[+] Threads:                 10
[+] Wordlist:                /path/to/wordlist.txt
===============================================================
\x1b[2K/admin               (Status: 200) [Size: 1024]
\x1b[2K/login               (Status: 302) [Size: 0] [--> /auth/login]
\x1b[2K/config.php          (Status: 403) [Size: 280]
\x1b[2K/static              (Status: 301) [Size: 150]
===============================================================
Finished
"""
    endpoint = WebEndpoint.create(url="http://10.10.10.50:8080")
    findings = [f async for f in adapter.parse_output(sample_output, endpoint)]

    assert len(findings) == 4
    for f in findings:
        assert f.schema_type == "web.endpoint"
        assert f.data["method"] == "GET"

    assert findings[0].pik["url"] == "http://10.10.10.50:8080/admin"
    assert findings[0].data["status_code"] == 200

    assert findings[1].pik["url"] == "http://10.10.10.50:8080/login"
    assert findings[1].data["status_code"] == 302

    assert findings[2].pik["url"] == "http://10.10.10.50:8080/config.php"
    assert findings[2].data["status_code"] == 403

    assert findings[3].pik["url"] == "http://10.10.10.50:8080/static"
    assert findings[3].data["status_code"] == 301


@pytest.mark.asyncio
async def test_gobuster_parse_fallback_context(adapter):
    # Test when target is None, but context contains raw_flags with -u
    sample_output = "/dashboard (Status: 200) [Size: 500]"
    context = {"params": {"raw_flags": "dir -u http://target.local:8000"}}

    findings = [f async for f in adapter.parse_output(sample_output, None, context)]
    assert len(findings) == 1
    assert findings[0].pik["url"] == "http://target.local:8000/dashboard"
    assert findings[0].data["status_code"] == 200
