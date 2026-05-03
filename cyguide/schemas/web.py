"""Web-related finding schemas."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_url, canonicalize_host, canonicalize_port


class WebEndpoint(BaseFinding):
    """A reachable HTTP/S URL with response metadata. Child of network.service. Produced by gobuster, curl."""
    schema_type: str = "web.endpoint"
    pik_fields: ClassVar[list[str]] = ["url"]

    @classmethod
    def create(cls, url: str, host_ip: Optional[str] = None, port: Optional[int] = None, **kwargs):
        normalized_url = canonicalize_url(url)
        
        parent = None
        if host_ip and port:
            parent = Relation(
                target_type="network.service",
                target_pik={
                    "host_ip": canonicalize_host(host_ip),
                    "port": canonicalize_port(port),
                    "protocol": "tcp" # Default for web
                },
                via="hosts_endpoint"
            )
            
        return cls(
            pik={"url": normalized_url},
            parent=parent,
            data={
                "url": normalized_url,
                **kwargs
            }
        )

class WebResource(BaseFinding):
    """A specific asset (JS, CSS, Image) found on a web endpoint. Child of web.endpoint. Produced by burp, crawler."""
    schema_type: str = "web.resource"
    pik_fields: ClassVar[list[str]] = ["url", "resource_path"]

    @classmethod
    def create(cls, url: str, resource_path: str, **kwargs):
        normalized_url = canonicalize_url(url)
        return cls(
            pik={"url": normalized_url, "resource_path": resource_path},
            parent=Relation(target_type="web.endpoint", target_pik={"url": normalized_url}, via="hosts_resource"),
            data={"url": normalized_url, "resource_path": resource_path, **kwargs}
        )

class WebVulnerability(BaseFinding):
    """A web-specific flaw (XSS, SQLi) found on an endpoint. Child of web.endpoint. Produced by nikto, zap."""
    schema_type: str = "web.vulnerability"
    pik_fields: ClassVar[list[str]] = ["url", "vuln_type", "parameter"]

    @classmethod
    def create(cls, url: str, vuln_type: str, parameter: Optional[str] = None, **kwargs):
        normalized_url = canonicalize_url(url)
        return cls(
            pik={"url": normalized_url, "vuln_type": vuln_type, "parameter": parameter or ""},
            parent=Relation(target_type="web.endpoint", target_pik={"url": normalized_url}, via="has_web_vuln"),
            data={"url": normalized_url, "vuln_type": vuln_type, "parameter": parameter, **kwargs}
        )
