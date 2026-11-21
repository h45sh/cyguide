import pytest

from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.dns import DnsRecord, DomainInfo, EntityAlias
from cyguide.schemas.host_internal import FileSystemObject, ProcessRunning, SoftwarePackage
from cyguide.schemas.network import (
    NetworkHost,
    NetworkNetblock,
    NetworkService,
    TLSCertificate,
)
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

SCHEMA_CONTRACT_CASES = [
    # (factory_fn, expected_type, expected_pik_subset, expected_parent, expected_assocs)
    (
        lambda: NetworkHost.create(ip="192.168.1.1", hostname="TEST-HOST"),
        "network.host",
        {"ip": "192.168.1.1"},
        None,
        [],
    ),
    (
        lambda: NetworkService.create(
            host_ip="10.0.0.5", port=80, protocol="TCP", service_name="HTTP"
        ),
        "network.service",
        {"host_ip": "10.0.0.5", "port": 80, "protocol": "tcp"},
        ("network.host", {"ip": "10.0.0.5"}, "has_service"),
        [],
    ),
    (
        lambda: NetworkNetblock.create(cidr="10.0.0.0/24", organization="Internal Corp"),
        "network.netblock",
        {"cidr": "10.0.0.0/24"},
        None,
        [],
    ),
    (
        lambda: DnsRecord.create(
            domain="EXAMPLE.COM",
            record_type="A",
            value="93.184.216.34",
            resolved_ip="93.184.216.34",
        ),
        "dns.record",
        {"domain": "example.com", "type": "A", "value": "93.184.216.34"},
        None,
        [("network.host", {"ip": "93.184.216.34"}, "resolves_to")],
    ),
    (
        lambda: DomainInfo.create(
            domain="EXAMPLE.COM", registrar="MarkMonitor Inc.", organization="Example Corp"
        ),
        "domain.info",
        {"domain": "example.com"},
        None,
        [
            (
                "dns.record",
                {"domain": "example.com", "type": "ANY", "value": "ANY"},
                "whois_data_for",
            )
        ],
    ),
    (
        lambda: CredentialFound.create(
            context="ssh", username="admin", password="password123", host_ip="192.168.1.1"
        ),
        "credential.found",
        {"context": "ssh", "username": "admin"},
        ("network.host", {"ip": "192.168.1.1"}, "credential_for_host"),
        [],
    ),
    (
        lambda: CredentialFound.create(context="web", username="root", password="toor"),
        "credential.found",
        {"context": "web", "username": "root"},
        None,
        [],
    ),
    (
        lambda: EntityAlias.create(source_id="host_1", target_id="host_2", relation_type="same_as"),
        "entity.alias",
        {"source_id": "host_1", "target_id": "host_2"},
        None,
        [],
    ),
    (
        lambda: ProcessRunning.create(host_ip="10.0.0.1", pid=1337, name="nginx"),
        "process.running",
        {"host_ip": "10.0.0.1", "pid": 1337},
        ("network.host", {"ip": "10.0.0.1"}, "hosts_process"),
        [],
    ),
    (
        lambda: FileSystemObject.create(host_ip="10.0.0.1", path="/etc/shadow"),
        "file.system_object",
        {"host_ip": "10.0.0.1", "path": "/etc/shadow"},
        ("network.host", {"ip": "10.0.0.1"}, "hosts_file"),
        [],
    ),
    (
        lambda: SoftwarePackage.create(
            host_ip="10.0.0.1", package_name="openssh-server", version="8.2p1"
        ),
        "software.package",
        {"host_ip": "10.0.0.1", "package_name": "openssh-server"},
        ("network.host", {"ip": "10.0.0.1"}, "hosts_software"),
        [],
    ),
    (
        lambda: TLSCertificate.create(
            fingerprint="SHA256:abcd1234", host_ip="192.168.1.10", port=443
        ),
        "tls.certificate",
        {"fingerprint": "SHA256:abcd1234"},
        (
            "network.service",
            {"host_ip": "192.168.1.10", "port": 443, "protocol": "tcp"},
            "uses_certificate",
        ),
        [],
    ),
    (
        lambda: VulnerabilityFound.create(
            host_ip="192.168.1.1", vuln_id="CVE-2021-44228", port=8080, severity="critical"
        ),
        "vulnerability.found",
        {"host_ip": "192.168.1.1", "vuln_id": "CVE-2021-44228"},
        (
            "network.service",
            {"host_ip": "192.168.1.1", "port": 8080, "protocol": "tcp"},
            "service_has_vuln",
        ),
        [],
    ),
    (
        lambda: VulnerabilityFound.create(host_ip="192.168.1.1", vuln_id="KERNEL-PANIC-01"),
        "vulnerability.found",
        {"host_ip": "192.168.1.1", "vuln_id": "KERNEL-PANIC-01"},
        ("network.host", {"ip": "192.168.1.1"}, "host_has_vuln"),
        [],
    ),
    (
        lambda: WebEndpoint.create(url="http://EXAMPLE.com:80/api/v1"),
        "web.endpoint",
        {"url": "http://example.com/api/v1"},
        None,
        [],
    ),
    (
        lambda: WebEndpoint.create(
            url="http://192.168.1.1:80/login", host_ip="192.168.1.1", port=80
        ),
        "web.endpoint",
        {"url": "http://192.168.1.1/login"},
        (
            "network.service",
            {"host_ip": "192.168.1.1", "port": 80, "protocol": "tcp"},
            "hosts_endpoint",
        ),
        [],
    ),
    (
        lambda: WebResource.create(url="http://example.com/app", resource_path="/static/main.js"),
        "web.resource",
        {"url": "http://example.com/app", "resource_path": "/static/main.js"},
        ("web.endpoint", {"url": "http://example.com/app"}, "hosts_resource"),
        [],
    ),
    (
        lambda: WebVulnerability.create(
            url="http://example.com/search", vuln_type="SQLi", parameter="q"
        ),
        "web.vulnerability",
        {"url": "http://example.com/search", "vuln_type": "SQLi", "parameter": "q"},
        ("web.endpoint", {"url": "http://example.com/search"}, "has_web_vuln"),
        [],
    ),
    (
        lambda: ExploitReference.create(
            exploit_id="EDB-ID:50000",
            title="Apache 2.4.49 Path Traversal",
            cve_id="CVE-2021-41773",
            host_ip="192.168.1.100",
            port=80,
        ),
        "exploit.reference",
        {"exploit_id": "EDB-ID:50000"},
        (
            "network.service",
            {"host_ip": "192.168.1.100", "port": 80, "protocol": "tcp"},
            "service_has_exploit",
        ),
        [
            (
                "vulnerability.found",
                {"host_ip": "192.168.1.100", "vuln_id": "CVE-2021-41773"},
                "exploits_cve",
            )
        ],
    ),
    (
        lambda: ExploitReference.create(
            exploit_id="EDB-ID:49999",
            title="Log4Shell RCE",
            vuln_id="CVE-2021-44228",
            host_ip="192.168.1.50",
        ),
        "exploit.reference",
        {"exploit_id": "EDB-ID:49999"},
        (
            "vulnerability.found",
            {"host_ip": "192.168.1.50", "vuln_id": "CVE-2021-44228"},
            "vuln_has_exploit",
        ),
        [],
    ),
    (
        lambda: WebTechnology.create(
            url="http://example.com/blog",
            technology_name="WordPress",
            version="6.2.2",
        ),
        "web.technology",
        {"url": "http://example.com/blog", "technology_name": "WordPress"},
        ("web.endpoint", {"url": "http://example.com/blog"}, "endpoint_uses_technology"),
        [],
    ),
    (
        lambda: WebTechnology.create(
            url="http://192.168.1.10:8080",
            technology_name="Apache Tomcat",
            version="9.0.50",
            host_ip="192.168.1.10",
            port=8080,
        ),
        "web.technology",
        {"url": "http://192.168.1.10:8080", "technology_name": "Apache Tomcat"},
        (
            "network.service",
            {"host_ip": "192.168.1.10", "port": 8080, "protocol": "tcp"},
            "service_uses_technology",
        ),
        [],
    ),
    (
        lambda: AuditMisconfig.create(
            target="http://example.com/.git/config",
            check_id="exposed-git-config",
            title="Exposed Git Configuration",
            severity="high",
        ),
        "audit.misconfig",
        {"target": "http://example.com/.git/config", "check_id": "exposed-git-config"},
        ("web.endpoint", {"url": "http://example.com/.git/config"}, "endpoint_has_misconfig"),
        [],
    ),
    (
        lambda: AuditMisconfig.create(
            target="192.168.1.1",
            check_id="default-snmp-community",
            title="Default SNMP Public Community String",
            severity="medium",
            host_ip="192.168.1.1",
        ),
        "audit.misconfig",
        {"target": "192.168.1.1", "check_id": "default-snmp-community"},
        ("network.host", {"ip": "192.168.1.1"}, "host_has_misconfig"),
        [],
    ),
]


@pytest.mark.parametrize(
    "factory_fn, expected_type, expected_pik, expected_parent, expected_assocs",
    SCHEMA_CONTRACT_CASES,
)
def test_core_schema_contracts(
    factory_fn, expected_type, expected_pik, expected_parent, expected_assocs
):
    finding = factory_fn()
    assert finding.schema_type == expected_type
    assert finding.status == "confirmed"
    for k, v in expected_pik.items():
        assert finding.pik.get(k) == v, (
            f"PIK key {k} mismatch: expected {v}, got {finding.pik.get(k)}"
        )

    if expected_parent is None:
        assert finding.parent is None
    else:
        target_type, target_pik, via = expected_parent
        assert finding.parent is not None
        assert finding.parent.target_type == target_type
        assert finding.parent.target_pik == target_pik
        assert finding.parent.via == via

    assert len(finding.associations) == len(expected_assocs)
    for i, (t_type, t_pik, via) in enumerate(expected_assocs):
        assert finding.associations[i].target_type == t_type
        assert finding.associations[i].target_pik == t_pik
        assert finding.associations[i].via == via


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


def test_base_finding_from_data_automatic_pik_derivation():
    """Verify that BaseFinding.from_data extracts declarative pik_fields automatically."""
    data = {"ip": "10.10.10.10", "hostname": "target.htb", "os": "Linux"}
    host = NetworkHost.from_data(data)
    assert host.schema_type == "network.host"
    assert host.pik == {"ip": "10.10.10.10"}
    assert host.data["hostname"] == "target.htb"
    assert host.parent is None
