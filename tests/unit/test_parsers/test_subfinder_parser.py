import pytest
from tools.subfinder.adapter import SubfinderAdapter
from cyguide.schemas.dns import DomainInfo, DnsRecord

@pytest.fixture
def adapter():
    return SubfinderAdapter()

def test_subfinder_validate_install(adapter):
    assert isinstance(adapter.validate_install(), bool)

def test_subfinder_build_command(adapter):
    # 1. Target is domain.info
    domain_info = DomainInfo.create(domain="example.com")
    cmd = adapter.build_command(domain_info, {"raw_flags": "-d {domain} -silent"})
    assert cmd[0] == "subfinder"
    assert "-d" in cmd
    assert "example.com" in cmd
    assert "-silent" in cmd

    # 2. Target is dns.record
    dns_rec = DnsRecord.create(domain="target.org", record_type="A", value="1.2.3.4")
    cmd_dns = adapter.build_command(dns_rec, {"raw_flags": "-d {domain}"})
    assert "target.org" in cmd_dns

@pytest.mark.asyncio
async def test_subfinder_parse_output(adapter):
    sample_output = r"""
               __    _____           __           
   _______  __/ /_  / __(_)___  ____/ /__  _____
  / ___/ / / / __ \/ /_/ / __ \/ __  / _ \/ ___/
 (__  ) /_/ / /_/ / __/ / / / / /_/ /  __/ /    
/____/\__,_/_.___/_/ /_/_/ /_/\__,_/\___/_/

[INF] Loading provider config from /root/.config/subfinder/provider-config.yaml
[INF] Enumerating subdomains for example.com
api.example.com
admin.example.com
dev.api.example.com
mail.example.com
[INF] Found 4 subdomains for example.com in 800 milliseconds
"""
    target = DomainInfo.create(domain="example.com")
    findings = [f async for f in adapter.parse_output(sample_output, target)]

    assert len(findings) == 4
    domains = [f.pik["domain"] for f in findings]
    
    assert "api.example.com" in domains
    assert "admin.example.com" in domains
    assert "dev.api.example.com" in domains
    assert "mail.example.com" in domains

    for f in findings:
        assert f.schema_type == "dns.record"
        assert f.pik["type"] == "A"
        assert f.pik["value"] == "unknown"
