import pytest

from cyguide.schemas.dns import DnsRecord, DomainInfo
from tools.subfinder.adapter import SubfinderAdapter


@pytest.fixture
def adapter():
    return SubfinderAdapter()

def test_subfinder_validate_install(adapter):
    assert isinstance(adapter.validate_install(), bool)

def test_subfinder_build_command(adapter):
    # 1. Target is domain.info
    domain_info = DomainInfo.create(domain="example.com")
    cmd = adapter.build_command(domain_info, {"raw_flags": "-d {domain} -silent"})
    assert cmd == ["subfinder", "-d", "example.com", "-silent"]

    # 2. Target is dns.record
    dns_rec = DnsRecord.create(domain="target.org", record_type="A", value="1.2.3.4")
    cmd_dns = adapter.build_command(dns_rec, {"raw_flags": "-d {domain}"})
    assert cmd_dns == ["subfinder", "-d", "target.org"]

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
    
    assert set(domains) == {
        "api.example.com",
        "admin.example.com",
        "dev.api.example.com",
        "mail.example.com",
    }

    for f in findings:
        assert f.schema_type == "dns.record"
        assert f.pik["type"] == "A"
        assert f.pik["value"] == "unknown"
