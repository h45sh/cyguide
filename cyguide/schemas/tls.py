"""TLS and certificate schemas."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_host, canonicalize_port


class TLSCertificate(BaseFinding):
    """A TLS certificate associated with a service. Child of network.service. Produced by sslscan, nmap-scripts."""
    schema_type: str = "tls.certificate"
    pik_fields: ClassVar[list[str]] = ["fingerprint"]

    @classmethod
    def create(cls, fingerprint: str, host_ip: str, port: int, **kwargs):
        normalized_ip = canonicalize_host(host_ip)
        normalized_port = canonicalize_port(port)
        
        return cls(
            pik={"fingerprint": fingerprint},
            parent=Relation(
                target_type="network.service",
                target_pik={"host_ip": normalized_ip, "port": normalized_port, "protocol": "tcp"},
                via="uses_certificate"
            ),
            data={"fingerprint": fingerprint, "host_ip": normalized_ip, "port": normalized_port, **kwargs}
        )
