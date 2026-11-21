"""Network-related finding schemas."""

from typing import ClassVar, Optional

from cyguide.schemas.base import BaseFinding, Relation


class NetworkHost(BaseFinding):
    """A discovered machine on the network, identified by IP. Root entity for most scans. Produced by nmap."""

    schema_type: str = "network.host"
    pik_fields: ClassVar[list[str]] = ["ip"]

    @classmethod
    def create(cls, ip: str, hostname: Optional[str] = None, os: Optional[str] = None, **kwargs):
        return cls.from_data({"ip": ip, "hostname": hostname, "os": os, **kwargs})


class NetworkService(BaseFinding):
    """A listening port on a host. Child of network.host. Produced by nmap -sV."""

    schema_type: str = "network.service"
    pik_fields: ClassVar[list[str]] = ["host_ip", "port", "protocol"]

    @classmethod
    def create(
        cls,
        host_ip: str,
        port: int,
        protocol: str = "tcp",
        service_name: Optional[str] = None,
        **kwargs,
    ):
        pik = {"host_ip": host_ip, "port": port, "protocol": protocol}

        return cls(
            pik=pik,
            parent=Relation(
                target_type="network.host", target_pik={"ip": host_ip}, via="has_service"
            ),
            data={**pik, "service_name": service_name, **kwargs},
        )


class NetworkNetblock(BaseFinding):
    """An IP range with ownership data — org, ASN, CIDR. Produced by whois against an IP."""

    schema_type: str = "network.netblock"
    pik_fields: ClassVar[list[str]] = ["cidr"]

    @classmethod
    def create(cls, cidr: str, organization: Optional[str] = None, asn: Optional[str] = None):
        pik = {"cidr": cidr.strip()}
        return cls(pik=pik, data={**pik, "organization": organization, "asn": asn})


class TLSCertificate(BaseFinding):
    """A TLS certificate associated with a service. Child of network.service. Produced by sslscan, nmap-scripts."""

    schema_type: str = "tls.certificate"
    pik_fields: ClassVar[list[str]] = ["fingerprint"]

    @classmethod
    def create(cls, fingerprint: str, host_ip: str, port: int, **kwargs):
        return cls(
            pik={"fingerprint": fingerprint},
            parent=Relation(
                target_type="network.service",
                target_pik={"host_ip": host_ip, "port": port, "protocol": "tcp"},
                via="uses_certificate",
            ),
            data={
                "fingerprint": fingerprint,
                "host_ip": host_ip,
                "port": port,
                **kwargs,
            },
        )
