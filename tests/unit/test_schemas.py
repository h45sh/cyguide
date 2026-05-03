import pytest
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.dns import DnsRecord, DomainInfo
from cyguide.schemas.web import WebEndpoint
from cyguide.schemas.netblock import NetworkNetblock

def test_network_host_creation():
    host = NetworkHost.create(ip="192.168.1.1", hostname="test-host")
    assert host.schema_type == "network.host"
    assert host.pik == {"ip": "192.168.1.1"}
    assert host.data["hostname"] == "test-host"
    assert host.parent is None

def test_network_service_parent_wiring():
    service = NetworkService.create(host_ip="10.0.0.5", port=80, protocol="tcp", service_name="http")
    assert service.schema_type == "network.service"
    assert service.pik == {"host_ip": "10.0.0.5", "port": 80, "protocol": "tcp"}
    assert service.parent is not None
    assert service.parent.target_type == "network.host"
    assert service.parent.target_pik == {"ip": "10.0.0.5"}
    assert service.parent.via == "has_service"

def test_dns_record_associations():
    # Test with resolved IP
    dns = DnsRecord.create(domain="example.com", record_type="A", value="93.184.216.34", resolved_ip="93.184.216.34")
    assert dns.schema_type == "dns.record"
    assert len(dns.associations) == 1
    assert dns.associations[0].target_type == "network.host"
    assert dns.associations[0].target_pik == {"ip": "93.184.216.34"}
    assert dns.associations[0].via == "resolves_to"

def test_domain_info_associations():
    info = DomainInfo.create(domain="google.com", registrar="MarkMonitor Inc.")
    assert info.schema_type == "domain.info"
    assert len(info.associations) == 1
    assert info.associations[0].target_type == "dns.record"
    assert info.associations[0].target_pik["domain"] == "google.com"
    assert info.associations[0].via == "whois_data_for"

def test_web_endpoint_canonicalization():
    endpoint = WebEndpoint.create(url="http://EXAMPLE.com:80/PATH/")
    assert endpoint.pik["url"] == "http://example.com/PATH/"
    
def test_netblock_pik():
    nb = NetworkNetblock.create(cidr="192.168.0.0/24", organization="Private Network")
    assert nb.schema_type == "network.netblock"
    assert nb.pik == {"cidr": "192.168.0.0/24"}
