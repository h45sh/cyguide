"""Network-related finding schemas."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_host, canonicalize_port


class NetworkHost(BaseFinding):
    """A discovered machine on the network, identified by IP. Root entity for most scans. Produced by nmap."""
    schema_type: str = "network.host"
    pik_fields: ClassVar[list[str]] = ["ip"]

    @classmethod
    def create(cls, ip: str, hostname: Optional[str] = None, os: Optional[str] = None, **kwargs):
        normalized_ip = canonicalize_host(ip)
        return cls(
            pik={"ip": normalized_ip},
            data={
                "ip": normalized_ip,
                "hostname": hostname,
                "os": os,
                **kwargs
            }
        )


class NetworkService(BaseFinding):
    """A listening port on a host. Child of network.host. Produced by nmap -sV."""
    schema_type: str = "network.service"
    pik_fields: ClassVar[list[str]] = ["host_ip", "port", "protocol"]

    @classmethod
    def create(cls, host_ip: str, port: int, protocol: str = "tcp", service_name: Optional[str] = None, **kwargs):
        normalized_ip = canonicalize_host(host_ip)
        normalized_port = canonicalize_port(port)
        
        pik = {
            "host_ip": normalized_ip,
            "port": normalized_port,
            "protocol": protocol.lower()
        }
        
        return cls(
            pik=pik,
            parent=Relation(
                target_type="network.host",
                target_pik={"ip": normalized_ip},
                via="has_service"
            ),
            data={
                **pik,
                "service_name": service_name,
                **kwargs
            }
        )
