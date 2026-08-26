import pytest
from tools.whois.adapter import WhoisAdapter
from cyguide.schemas.dns import DnsRecord, DomainInfo
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.netblock import NetworkNetblock

@pytest.fixture
def adapter():
    return WhoisAdapter()

def test_whois_validate_install(adapter):
    assert isinstance(adapter.validate_install(), bool)

def test_whois_build_command(adapter):
    # 1. Target is dns.record
    dns_rec = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34")
    cmd_dns = adapter.build_command(dns_rec, {})
    assert cmd_dns == ["whois", "example.com"]

    # 2. Target is network.host
    host = NetworkHost.create(ip="8.8.8.8")
    cmd_host = adapter.build_command(host, {"raw_flags": "-h whois.arin.net"})
    assert "-h" in cmd_host
    assert "8.8.8.8" in cmd_host

    # 3. Target missing query field raises ValueError
    empty_host = NetworkHost.create(ip="")
    empty_host.pik = {}
    with pytest.raises(ValueError, match="missing query field"):
        adapter.build_command(empty_host, {})

@pytest.mark.asyncio
async def test_whois_parse_domain_output(adapter):
    sample_output = """
Domain Name: EXAMPLE.COM
Registry Domain ID: 2336799_DOMAIN_COM-VRSN
Registrar WHOIS Server: whois.iana.org
Registrar: Internet Assigned Numbers Authority
Organization: Example Corporation
Updated Date: 2026-08-14T07:01:44Z
Creation Date: 1995-08-14T04:00:00Z
"""
    dns_target = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34")
    findings = [f async for f in adapter.parse_output(sample_output, dns_target)]

    # Should yield a DomainInfo and optionally Netblock if org matched
    domain_infos = [f for f in findings if f.schema_type == "domain.info"]
    assert len(domain_infos) == 1
    assert domain_infos[0].pik["domain"] == "example.com"
    assert domain_infos[0].data["registrar"] == "Internet Assigned Numbers Authority"
    assert domain_infos[0].data["organization"] == "Example Corporation"

@pytest.mark.asyncio
async def test_whois_parse_ip_output(adapter):
    sample_output = """
NetRange:       8.8.8.0 - 8.8.8.255
CIDR:           8.8.8.0/24
NetName:        GOGL
NetHandle:      NET-8-8-8-0-1
Organization:   Google LLC (GOGL)
RegDate:        2014-03-14
Updated:        2014-03-14
"""
    host_target = NetworkHost.create(ip="8.8.8.8")
    findings = [f async for f in adapter.parse_output(sample_output, host_target)]

    netblocks = [f for f in findings if f.schema_type == "network.netblock"]
    hosts = [f for f in findings if f.schema_type == "network.host"]

    assert len(netblocks) == 1
    assert netblocks[0].pik["cidr"] in ("8.8.8.0 - 8.8.8.255", "8.8.8.0/24")
    assert netblocks[0].data["organization"] == "Google LLC (GOGL)"

    assert len(hosts) == 1
    assert hosts[0].pik["ip"] == "8.8.8.8"
