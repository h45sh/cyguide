"""Unit tests for the SQLMap adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.web import WebEndpoint, WebVulnerability
from tools.sqlmap.adapter import SqlmapAdapter


@pytest.fixture
def adapter():
    return SqlmapAdapter()


def test_sqlmap_build_command(adapter):
    endpoint = WebEndpoint.create(url="http://target.local/vuln.php?id=1")

    # 1. Default command must enforce --batch and -u
    cmd = adapter.build_command(endpoint, {})
    assert cmd[0] == "sqlmap"
    assert "--batch" in cmd
    assert "-u" in cmd
    u_idx = cmd.index("-u")
    assert cmd[u_idx + 1] == "http://target.local/vuln.php?id=1"

    # 2. Custom flags should be preserved and macro substituted
    cmd_custom = adapter.build_command(
        endpoint,
        {"raw_flags": "-u http://target.local/test --dbs --level=2"},
    )
    assert "--batch" in cmd_custom
    assert "--dbs" in cmd_custom
    assert "--level=2" in cmd_custom


def test_sqlmap_sanitize_output(adapter):
    raw = """
        ___
       __H__
 ___ ___[,]_____ ___ ___  {1.7.2#stable}
|_ -| . [']     | .'| . |
[*] starting @ 12:00:00 /2026-11-19/
[12:00:01] [INFO] testing connection to the target URL
sqlmap identified the following injection point(s):
[*] ending @ 12:00:10 /2026-11-19/
"""
    sanitized = adapter.sanitize_output(raw)
    assert "___" not in sanitized
    assert "starting @" not in sanitized
    assert "ending @" not in sanitized
    assert "testing connection" in sanitized


@pytest.mark.asyncio
async def test_sqlmap_parse_mock_output(adapter):
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "sqlmap.txt"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = WebEndpoint.create(url="http://example.com/items?id=1", host_ip="192.168.1.50")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    vulns = [f for f in findings if isinstance(f, WebVulnerability)]
    creds = [f for f in findings if isinstance(f, CredentialFound)]

    # Assert vulnerabilities discovered
    assert len(vulns) >= 1
    v = vulns[0]
    assert v.schema_type == "web.vulnerability"
    assert v.pik["vuln_type"] == "SQL Injection"
    assert v.pik["parameter"] == "id"
    assert "MySQL" in v.data.get("dbms", "")

    # Assert credentials dumped
    assert len(creds) == 2
    users = [c.pik["username"] for c in creds]
    assert "admin" in users
    assert "webuser" in users
    admin_cred = next(c for c in creds if c.pik["username"] == "admin")
    assert "*4ACFE3202A5FF5CF467898FC58AAB1D615029441" in admin_cred.data["password"]


@pytest.mark.asyncio
async def test_sqlmap_parse_empty_output(adapter):
    target = WebEndpoint.create(url="http://example.com")
    findings = [f async for f in adapter.parse_output("", target)]
    assert len(findings) == 0
