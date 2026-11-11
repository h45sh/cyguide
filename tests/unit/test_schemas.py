from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.dns import DnsRecord, DomainInfo
from cyguide.schemas.entity import EntityAlias
from cyguide.schemas.host_internal import FileSystemObject, ProcessRunning, SoftwarePackage
from cyguide.schemas.netblock import NetworkNetblock
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.tls import TLSCertificate
from cyguide.schemas.vulnerability import VulnerabilityFound
from cyguide.schemas.web import WebEndpoint, WebResource, WebVulnerability


def test_network_host():
    host = NetworkHost.create(ip="192.168.1.1", hostname="TEST-HOST")
    assert host.schema_type == "network.host"
    assert host.pik == {"ip": "192.168.1.1"}
    assert host.data["hostname"] == "TEST-HOST"
    assert host.parent is None
    assert host.status == "confirmed"

def test_network_service():
    service = NetworkService.create(host_ip="10.0.0.5", port=80, protocol="TCP", service_name="HTTP")
    assert service.schema_type == "network.service"
    assert service.pik == {"host_ip": "10.0.0.5", "port": 80, "protocol": "tcp"}
    assert service.parent is not None
    assert service.parent.target_type == "network.host"
    assert service.parent.target_pik == {"ip": "10.0.0.5"}
    assert service.parent.via == "has_service"

def test_network_netblock():
    nb = NetworkNetblock.create(cidr="10.0.0.0/24", organization="Internal Corp")
    assert nb.schema_type == "network.netblock"
    assert nb.pik == {"cidr": "10.0.0.0/24"}
    assert nb.data["organization"] == "Internal Corp"

def test_dns_record():
    dns = DnsRecord.create(domain="EXAMPLE.COM", record_type="A", value="93.184.216.34", resolved_ip="93.184.216.34")
    assert dns.schema_type == "dns.record"
    assert dns.pik["domain"] == "example.com"
    assert len(dns.associations) == 1
    assert dns.associations[0].target_type == "network.host"
    assert dns.associations[0].target_pik == {"ip": "93.184.216.34"}
    assert dns.associations[0].via == "resolves_to"

def test_domain_info():
    info = DomainInfo.create(domain="EXAMPLE.COM", registrar="MarkMonitor Inc.", organization="Example Corp")
    assert info.schema_type == "domain.info"
    assert info.pik["domain"] == "example.com"
    assert len(info.associations) == 1
    assert info.associations[0].target_type == "dns.record"
    assert info.associations[0].target_pik["domain"] == "example.com"
    assert info.associations[0].via == "whois_data_for"

def test_credential_found():
    # 1. With host_ip (creates parent relation)
    cred = CredentialFound.create(context="ssh", username="admin", password="password123", host_ip="192.168.1.1")
    assert cred.schema_type == "credential.found"
    assert cred.pik == {"context": "ssh", "username": "admin"}
    assert cred.parent is not None
    assert cred.parent.target_type == "network.host"
    assert cred.parent.target_pik == {"ip": "192.168.1.1"}
    assert cred.parent.via == "credential_for_host"

    # 2. Without host_ip
    cred_no_host = CredentialFound.create(context="web", username="root", password="toor")
    assert cred_no_host.parent is None

def test_entity_alias():
    alias = EntityAlias.create(source_id="host_1", target_id="host_2", relation_type="same_as")
    assert alias.schema_type == "entity.alias"
    assert alias.pik == {"source_id": "host_1", "target_id": "host_2"}
    assert alias.data["relation_type"] == "same_as"

def test_process_running():
    proc = ProcessRunning.create(host_ip="10.0.0.1", pid=1337, name="nginx")
    assert proc.schema_type == "process.running"
    assert proc.pik == {"host_ip": "10.0.0.1", "pid": 1337}
    assert proc.parent is not None
    assert proc.parent.target_type == "network.host"
    assert proc.parent.target_pik == {"ip": "10.0.0.1"}
    assert proc.parent.via == "hosts_process"

def test_file_system_object():
    fso = FileSystemObject.create(host_ip="10.0.0.1", path="/etc/shadow")
    assert fso.schema_type == "file.system_object"
    assert fso.pik == {"host_ip": "10.0.0.1", "path": "/etc/shadow"}
    assert fso.parent is not None
    assert fso.parent.target_type == "network.host"
    assert fso.parent.target_pik == {"ip": "10.0.0.1"}
    assert fso.parent.via == "hosts_file"

def test_software_package():
    pkg = SoftwarePackage.create(host_ip="10.0.0.1", package_name="openssh-server", version="8.2p1")
    assert pkg.schema_type == "software.package"
    assert pkg.pik == {"host_ip": "10.0.0.1", "package_name": "openssh-server"}
    assert pkg.parent is not None
    assert pkg.parent.target_type == "network.host"
    assert pkg.parent.target_pik == {"ip": "10.0.0.1"}
    assert pkg.parent.via == "hosts_software"

def test_tls_certificate():
    tls = TLSCertificate.create(fingerprint="SHA256:abcd1234", host_ip="192.168.1.10", port=443)
    assert tls.schema_type == "tls.certificate"
    assert tls.pik == {"fingerprint": "SHA256:abcd1234"}
    assert tls.parent is not None
    assert tls.parent.target_type == "network.service"
    assert tls.parent.target_pik == {"host_ip": "192.168.1.10", "port": 443, "protocol": "tcp"}
    assert tls.parent.via == "uses_certificate"

def test_vulnerability_found():
    # 1. Linked to service
    vuln_svc = VulnerabilityFound.create(host_ip="192.168.1.1", vuln_id="CVE-2021-44228", port=8080, severity="critical")
    assert vuln_svc.schema_type == "vulnerability.found"
    assert vuln_svc.pik == {"host_ip": "192.168.1.1", "vuln_id": "CVE-2021-44228"}
    assert vuln_svc.parent.target_type == "network.service"
    assert vuln_svc.parent.target_pik == {"host_ip": "192.168.1.1", "port": 8080, "protocol": "tcp"}
    assert vuln_svc.parent.via == "service_has_vuln"

    # 2. Linked to host
    vuln_host = VulnerabilityFound.create(host_ip="192.168.1.1", vuln_id="KERNEL-PANIC-01")
    assert vuln_host.parent.target_type == "network.host"
    assert vuln_host.parent.target_pik == {"ip": "192.168.1.1"}
    assert vuln_host.parent.via == "host_has_vuln"

def test_web_endpoint():
    # 1. Standalone
    ep = WebEndpoint.create(url="http://EXAMPLE.com:80/api/v1")
    assert ep.schema_type == "web.endpoint"
    assert ep.pik == {"url": "http://example.com/api/v1"}
    assert ep.parent is None

    # 2. Linked to service
    ep_svc = WebEndpoint.create(url="http://192.168.1.1:80/login", host_ip="192.168.1.1", port=80)
    assert ep_svc.parent is not None
    assert ep_svc.parent.target_type == "network.service"
    assert ep_svc.parent.target_pik == {"host_ip": "192.168.1.1", "port": 80, "protocol": "tcp"}
    assert ep_svc.parent.via == "hosts_endpoint"

def test_web_resource():
    res = WebResource.create(url="http://example.com/app", resource_path="/static/main.js")
    assert res.schema_type == "web.resource"
    assert res.pik == {"url": "http://example.com/app", "resource_path": "/static/main.js"}
    assert res.parent is not None
    assert res.parent.target_type == "web.endpoint"
    assert res.parent.target_pik == {"url": "http://example.com/app"}
    assert res.parent.via == "hosts_resource"

def test_web_vulnerability():
    web_vuln = WebVulnerability.create(url="http://example.com/search", vuln_type="SQLi", parameter="q")
    assert web_vuln.schema_type == "web.vulnerability"
    assert web_vuln.pik == {"url": "http://example.com/search", "vuln_type": "SQLi", "parameter": "q"}
    assert web_vuln.parent is not None
    assert web_vuln.parent.target_type == "web.endpoint"
    assert web_vuln.parent.target_pik == {"url": "http://example.com/search"}
    assert web_vuln.parent.via == "has_web_vuln"

def test_schema_status_toggle():
    host = NetworkHost.create(ip="10.10.10.10")
    assert host.status == "confirmed"

    host.status = "proposed"
    assert host.status == "proposed"
