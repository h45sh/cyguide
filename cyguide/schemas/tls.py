"""TLS and certificate schemas."""

from typing import ClassVar

from cyguide.schemas.base import BaseFinding, Relation


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
