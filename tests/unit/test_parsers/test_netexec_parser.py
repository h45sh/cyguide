"""Unit tests for the NetExec (nxc) adapter and parser."""

from pathlib import Path

import pytest

from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.vulnerability import AuditMisconfig
from tools.netexec.adapter import NetexecAdapter


@pytest.fixture
def adapter():
    return NetexecAdapter()


def test_netexec_build_command(adapter):
    target = NetworkHost.create(ip="10.10.10.5")

    # 1. Default command should prepend binary, smb protocol, and target
    cmd = adapter.build_command(target, {})
    assert cmd[0] in ("nxc", "netexec")
    assert cmd[1] == "smb"
    assert "10.10.10.5" in cmd

    # 2. Custom protocol and flags
    cmd_ssh = adapter.build_command(
        target,
        {"raw_flags": "ssh 10.10.10.5 -u root -p password"},
    )
    assert cmd_ssh[0] in ("nxc", "netexec")
    assert cmd_ssh[1] == "ssh"
    assert "-u" in cmd_ssh
    assert "root" in cmd_ssh


def test_netexec_sanitize_output(adapter):
    raw = """
NetExec v1.3.0 (CrackMapExec)
[*] NetExec Active Directory & Protocol Auditor
SMB         10.10.10.5      445    DC01             [*] Windows 10.0 Build 17763 x64
"""
    sanitized = adapter.sanitize_output(raw)
    assert "NetExec v1.3.0" not in sanitized
    assert "Active Directory & Protocol Auditor" not in sanitized
    assert "Windows 10.0" in sanitized


@pytest.mark.asyncio
async def test_netexec_parse_mock_output(adapter):
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mock_tools" / "netexec.txt"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_output = f.read()

    target = NetworkHost.create(ip="10.10.10.5")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    hosts = [f for f in findings if isinstance(f, NetworkHost)]
    services = [f for f in findings if isinstance(f, NetworkService)]
    misconfigs = [f for f in findings if isinstance(f, AuditMisconfig)]
    creds = [f for f in findings if isinstance(f, CredentialFound)]

    # Assert hosts discovered
    assert len(hosts) == 2
    ips = [h.pik["ip"] for h in hosts]
    assert "10.10.10.5" in ips
    assert "10.10.10.6" in ips

    # Assert services discovered
    assert len(services) == 2
    assert all(s.pik["port"] == 445 for s in services)

    # Assert SMB signing misconfiguration
    assert len(misconfigs) == 1
    assert misconfigs[0].pik["check_id"] == "smb_signing_disabled"
    assert misconfigs[0].data["host_ip"] == "10.10.10.5"

    # Assert credentials extracted
    assert len(creds) == 2
    users = [c.pik["username"] for c in creds]
    assert "administrator" in users
    assert "backup_svc" in users

    admin_cred = next(c for c in creds if c.pik["username"] == "administrator")
    assert admin_cred.data["password"] == "Password123"
    assert admin_cred.data["pwn3d"] is True

    backup_cred = next(c for c in creds if c.pik["username"] == "backup_svc")
    assert backup_cred.data["password"] == "Summer2024!"
    assert backup_cred.data["pwn3d"] is False


@pytest.mark.asyncio
async def test_netexec_parse_empty_output(adapter):
    target = NetworkHost.create(ip="10.10.10.5")
    findings = [f async for f in adapter.parse_output("", target)]
    assert len(findings) == 0
