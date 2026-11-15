from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.dns import DnsRecord, DomainInfo
from cyguide.schemas.entity import EntityAlias
from cyguide.schemas.host_internal import FileSystemObject, ProcessRunning, SoftwarePackage
from cyguide.schemas.netblock import NetworkNetblock
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.tls import TLSCertificate
from cyguide.schemas.vulnerability import (
    AuditMisconfig,
    ExploitReference,
    VulnerabilityFound,
)
from cyguide.schemas.web import (
    WebEndpoint,
    WebResource,
    WebTechnology,
    WebVulnerability,
)


def test_network_host():
    host = NetworkHost.create(ip="192.168.1.1", hostname="TEST-HOST")
    assert host.schema_type == "network.host"
    assert host.pik == {"ip": "192.168.1.1"}
    assert host.data["hostname"] == "TEST-HOST"
    assert host.parent is None
    assert host.status == "confirmed"


def test_network_service():
    service = NetworkService.create(
        host_ip="10.0.0.5", port=80, protocol="TCP", service_name="HTTP"
    )
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
    dns = DnsRecord.create(
        domain="EXAMPLE.COM", record_type="A", value="93.184.216.34", resolved_ip="93.184.216.34"
    )
    assert dns.schema_type == "dns.record"
    assert dns.pik["domain"] == "example.com"
    assert len(dns.associations) == 1
    assert dns.associations[0].target_type == "network.host"
    assert dns.associations[0].target_pik == {"ip": "93.184.216.34"}
    assert dns.associations[0].via == "resolves_to"


def test_domain_info():
    info = DomainInfo.create(
        domain="EXAMPLE.COM", registrar="MarkMonitor Inc.", organization="Example Corp"
    )
    assert info.schema_type == "domain.info"
    assert info.pik["domain"] == "example.com"
    assert len(info.associations) == 1
    assert info.associations[0].target_type == "dns.record"
    assert info.associations[0].target_pik["domain"] == "example.com"
    assert info.associations[0].via == "whois_data_for"


def test_credential_found():
    # 1. With host_ip (creates parent relation)
    cred = CredentialFound.create(
        context="ssh", username="admin", password="password123", host_ip="192.168.1.1"
    )
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
    vuln_svc = VulnerabilityFound.create(
        host_ip="192.168.1.1", vuln_id="CVE-2021-44228", port=8080, severity="critical"
    )
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
    web_vuln = WebVulnerability.create(
        url="http://example.com/search", vuln_type="SQLi", parameter="q"
    )
    assert web_vuln.schema_type == "web.vulnerability"
    assert web_vuln.pik == {
        "url": "http://example.com/search",
        "vuln_type": "SQLi",
        "parameter": "q",
    }
    assert web_vuln.parent is not None
    assert web_vuln.parent.target_type == "web.endpoint"
    assert web_vuln.parent.target_pik == {"url": "http://example.com/search"}
    assert web_vuln.parent.via == "has_web_vuln"


def test_schema_status_toggle():
    host = NetworkHost.create(ip="10.10.10.10")
    assert host.status == "confirmed"

    host.status = "proposed"
    assert host.status == "proposed"


def test_declarative_canonicalization():
    from cyguide.schemas.base import BaseFinding, Relation

    finding = BaseFinding(
        schema_type="test.entity",
        pik={"ip": " LOCALHOST ", "port": "8080", "protocol": " TCP "},
        parent=Relation(
            target_type="network.service",
            target_pik={"host_ip": " 127.0.0.1 ", "port": "443"},
            via="test_rel",
        ),
        data={"url": "HTTP://EXAMPLE.COM:80/FOO", "raw": "  value  "},
    )

    assert finding.pik["ip"] == "127.0.0.1"
    assert finding.pik["port"] == 8080
    assert finding.pik["protocol"] == "tcp"
    assert finding.parent.target_pik["host_ip"] == "127.0.0.1"
    assert finding.parent.target_pik["port"] == 443
    assert finding.data["url"] == "http://example.com/FOO"
    assert finding.data["raw"] == "value"


def test_action_request_creation():
    from uuid import uuid4

    from cyguide.schemas.power import ActionRequest, ActionSource

    session_id = uuid4()
    action = ActionRequest(
        session_id=session_id,
        tool_name="nmap",
        target_entity_id="host:127.0.0.1",
        params={"flags": "-sV"},
        triggered_by=ActionSource.USER,
    )
    assert action.tool_name == "nmap"
    assert action.session_id == session_id
    assert action.triggered_by == ActionSource.USER


def test_workspace_context_defaults():
    from uuid import uuid4

    from cyguide.schemas.power import WorkspaceContext

    session_id = uuid4()
    ctx = WorkspaceContext(session_id=session_id, session_name="Test Session")
    assert ctx.session_name == "Test Session"
    assert ctx.resolved_vars == {}
    assert ctx.active_jobs == []


def test_schema_version_default_and_custom():
    host = NetworkHost.create(ip="10.0.0.1")
    assert host.schema_version == "1.0"

    exploit = ExploitReference.create(
        exploit_id="EDB-ID:50000",
        title="Apache 2.4.49 Path Traversal",
        schema_version="2.0",
    )
    assert exploit.schema_version == "2.0"


def test_exploit_reference():
    # 1. Linked to service with CVE association
    exp_svc = ExploitReference.create(
        exploit_id="EDB-ID:50000",
        title="Apache 2.4.49 Path Traversal",
        cve_id="CVE-2021-41773",
        platform="multiple",
        exploit_type="remote",
        verified=True,
        file_path="exploits/multiple/remote/50000.py",
        host_ip="192.168.1.100",
        port=80,
    )
    assert exp_svc.schema_type == "exploit.reference"
    assert exp_svc.pik == {"exploit_id": "EDB-ID:50000"}
    assert exp_svc.parent is not None
    assert exp_svc.parent.target_type == "network.service"
    assert exp_svc.parent.target_pik == {"host_ip": "192.168.1.100", "port": 80, "protocol": "tcp"}
    assert exp_svc.parent.via == "service_has_exploit"
    assert len(exp_svc.associations) == 1
    assert exp_svc.associations[0].target_type == "vulnerability.found"
    assert exp_svc.associations[0].target_pik == {
        "host_ip": "192.168.1.100",
        "vuln_id": "CVE-2021-41773",
    }
    assert exp_svc.associations[0].via == "exploits_cve"

    # 2. Linked directly to vulnerability
    exp_vuln = ExploitReference.create(
        exploit_id="EDB-ID:49999",
        title="Log4Shell RCE",
        vuln_id="CVE-2021-44228",
        host_ip="192.168.1.50",
    )
    assert exp_vuln.parent is not None
    assert exp_vuln.parent.target_type == "vulnerability.found"
    assert exp_vuln.parent.target_pik == {"host_ip": "192.168.1.50", "vuln_id": "CVE-2021-44228"}
    assert exp_vuln.parent.via == "vuln_has_exploit"


def test_web_technology():
    # 1. Linked to web.endpoint by default
    tech_ep = WebTechnology.create(
        url="http://example.com/blog",
        technology_name="WordPress",
        version="6.2.2",
        categories=["CMS", "Blogs"],
        cpe="cpe:2.3:a:wordpress:wordpress:6.2.2:*:*:*:*:*:*:*",
        confidence=0.95,
    )
    assert tech_ep.schema_type == "web.technology"
    assert tech_ep.pik == {"url": "http://example.com/blog", "technology_name": "WordPress"}
    assert tech_ep.parent is not None
    assert tech_ep.parent.target_type == "web.endpoint"
    assert tech_ep.parent.target_pik == {"url": "http://example.com/blog"}
    assert tech_ep.parent.via == "endpoint_uses_technology"
    assert tech_ep.data["version"] == "6.2.2"
    assert tech_ep.data["categories"] == ["CMS", "Blogs"]
    assert tech_ep.data["confidence"] == 0.95

    # 2. Linked to network.service if host and port provided
    tech_svc = WebTechnology.create(
        url="http://192.168.1.10:8080",
        technology_name="Apache Tomcat",
        version="9.0.50",
        host_ip="192.168.1.10",
        port=8080,
    )
    assert tech_svc.parent is not None
    assert tech_svc.parent.target_type == "network.service"
    assert tech_svc.parent.target_pik == {
        "host_ip": "192.168.1.10",
        "port": 8080,
        "protocol": "tcp",
    }
    assert tech_svc.parent.via == "service_uses_technology"


def test_audit_misconfig():
    # 1. URL target linked to web.endpoint
    mis_web = AuditMisconfig.create(
        target="http://example.com/.git/config",
        check_id="exposed-git-config",
        title="Exposed Git Configuration",
        severity="high",
        description="Publicly accessible Git repository config discloses repository metadata.",
        remediation="Disable public access to .git directories via web server rules.",
    )
    assert mis_web.schema_type == "audit.misconfig"
    assert mis_web.pik == {
        "target": "http://example.com/.git/config",
        "check_id": "exposed-git-config",
    }
    assert mis_web.parent is not None
    assert mis_web.parent.target_type == "web.endpoint"
    assert mis_web.parent.target_pik == {"url": "http://example.com/.git/config"}
    assert mis_web.parent.via == "endpoint_has_misconfig"
    assert mis_web.data["severity"] == "high"

    # 2. Host target linked to network.host
    mis_host = AuditMisconfig.create(
        target="192.168.1.1",
        check_id="default-snmp-community",
        title="Default SNMP Public Community String",
        severity="medium",
        host_ip="192.168.1.1",
    )
    assert mis_host.parent is not None
    assert mis_host.parent.target_type == "network.host"
    assert mis_host.parent.target_pik == {"ip": "192.168.1.1"}
    assert mis_host.parent.via == "host_has_misconfig"


def test_new_schemas_presentation_metadata():
    import json

    from cyguide.schemas.presentation import (
        format_activity_entry,
        format_node_label,
        get_schema_display_meta,
    )

    # 1. Display meta
    sym, color, name = get_schema_display_meta("exploit.reference")
    assert sym == "▲"
    assert name == "Exploits"

    sym, color, name = get_schema_display_meta("web.technology")
    assert sym == "●"
    assert name == "Technologies"

    sym, color, name = get_schema_display_meta("audit.misconfig")
    assert sym == "▲"
    assert name == "Misconfigurations"

    # 2. Activity formatting
    exp = ExploitReference.create(exploit_id="EDB-ID:50000", title="Test Exploit")
    act_exp = format_activity_entry(
        "Session 1", "exploit.reference", "Found exploit", finding_obj=exp
    )
    assert "Exploit: EDB-ID:50000" in act_exp

    tech = WebTechnology.create(url="http://test.local", technology_name="Nginx", version="1.18")
    act_tech = format_activity_entry("Session 1", "web.technology", "Found tech", finding_obj=tech)
    assert "Tech: Nginx 1.18" in act_tech

    # 3. Node labels
    node_exp = {
        "id": "node_1",
        "schema_type": "exploit.reference",
        "pik_json": json.dumps({"exploit_id": "EDB-ID:50000"}),
        "data_json": json.dumps({"title": "Apache Path Traversal"}),
    }
    lbl_exp = format_node_label(node_exp)
    assert "EDB-ID:50000: Apache Path Traversal" in lbl_exp

    node_tech = {
        "id": "node_2",
        "schema_type": "web.technology",
        "pik_json": json.dumps({"technology_name": "PHP"}),
        "data_json": json.dumps({"version": "8.1"}),
    }
    lbl_tech = format_node_label(node_tech)
    assert lbl_tech == "PHP 8.1"


def test_all_schemas_json_roundtrip_symmetry():
    """Rule: Every finding schema must support 100% loss-free round-trip JSON serialization.

    Validates model_dump_json() -> model_validate_json() preserves all fields, types, and associations.
    """
    sample_findings = [
        NetworkHost.create(ip="192.168.1.1", hostname="router.local"),
        NetworkService.create(
            host_ip="192.168.1.1", port=443, protocol="tcp", service_name="https"
        ),
        NetworkNetblock.create(cidr="192.168.0.0/16", organization="Test Corp"),
        DnsRecord.create(
            domain="example.com",
            record_type="A",
            value="93.184.216.34",
            resolved_ip="93.184.216.34",
        ),
        DomainInfo.create(domain="example.com", registrar="IANA", organization="ICANN"),
        TLSCertificate.create(
            fingerprint="SHA256:abcd",
            host_ip="192.168.1.1",
            port=443,
            subject_cn="example.com",
            issuer_cn="Let's Encrypt",
        ),
        VulnerabilityFound.create(
            host_ip="192.168.1.1",
            vuln_id="CVE-2023-1234",
            title="Sample Vuln",
            severity="high",
            port=443,
        ),
        ExploitReference.create(
            exploit_id="EDB-50000", title="Sample Exploit", cve_id="CVE-2023-1234"
        ),
        AuditMisconfig.create(
            target="192.168.1.1",
            check_id="SSH-ROOT-LOGIN",
            title="Root login permitted",
            severity="medium",
            host_ip="192.168.1.1",
        ),
        WebEndpoint.create(
            url="https://example.com/api",
            path="/api",
            method="POST",
            host_ip="192.168.1.1",
            port=443,
        ),
        WebResource.create(
            url="https://example.com/api",
            resource_path="/favicon.ico",
        ),
        WebTechnology.create(
            url="https://example.com",
            technology_name="React",
            version="18.2",
        ),
        WebVulnerability.create(
            url="https://example.com/login",
            vuln_type="SQLi",
        ),
        CredentialFound.create(
            context="ssh", username="admin", password="secret", host_ip="192.168.1.1"
        ),
        ProcessRunning.create(host_ip="192.168.1.1", pid=1001, name="sshd"),
        FileSystemObject.create(host_ip="192.168.1.1", path="/etc/shadow"),
        SoftwarePackage.create(
            host_ip="192.168.1.1", package_name="openssh-server", version="9.0p1"
        ),
        EntityAlias.create(
            source_id="host:192.168.1.1",
            target_id="gateway.local",
            relation_type="alias_of",
        ),
    ]

    for finding in sample_findings:
        cls = finding.__class__
        serialized = finding.model_dump_json()
        restored = cls.model_validate_json(serialized)
        assert restored == finding, f"Round-trip failed for {cls.__name__}"
        assert restored.schema_type == finding.schema_type
        assert restored.pik == finding.pik
