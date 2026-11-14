"""Web-related finding schemas."""

from typing import ClassVar, Optional

from cyguide.schemas.base import BaseFinding, Relation


class WebEndpoint(BaseFinding):
    """A reachable HTTP/S URL with response metadata. Child of network.service. Produced by gobuster, curl."""

    schema_type: str = "web.endpoint"
    pik_fields: ClassVar[list[str]] = ["url"]

    @classmethod
    def create(cls, url: str, host_ip: Optional[str] = None, port: Optional[int] = None, **kwargs):
        parent = None
        if host_ip and port:
            parent = Relation(
                target_type="network.service",
                target_pik={
                    "host_ip": host_ip,
                    "port": port,
                    "protocol": "tcp",  # Default for web
                },
                via="hosts_endpoint",
            )

        return cls(pik={"url": url}, parent=parent, data={"url": url, **kwargs})


class WebResource(BaseFinding):
    """A specific asset (JS, CSS, Image) found on a web endpoint. Child of web.endpoint. Produced by burp, crawler."""

    schema_type: str = "web.resource"
    pik_fields: ClassVar[list[str]] = ["url", "resource_path"]

    @classmethod
    def create(cls, url: str, resource_path: str, **kwargs):
        return cls(
            pik={"url": url, "resource_path": resource_path},
            parent=Relation(
                target_type="web.endpoint", target_pik={"url": url}, via="hosts_resource"
            ),
            data={"url": url, "resource_path": resource_path, **kwargs},
        )


class WebVulnerability(BaseFinding):
    """A web-specific flaw (XSS, SQLi) found on an endpoint. Child of web.endpoint. Produced by nikto, zap."""

    schema_type: str = "web.vulnerability"
    pik_fields: ClassVar[list[str]] = ["url", "vuln_type", "parameter"]

    @classmethod
    def create(cls, url: str, vuln_type: str, parameter: Optional[str] = None, **kwargs):
        return cls(
            pik={"url": url, "vuln_type": vuln_type, "parameter": parameter or ""},
            parent=Relation(
                target_type="web.endpoint", target_pik={"url": url}, via="has_web_vuln"
            ),
            data={"url": url, "vuln_type": vuln_type, "parameter": parameter, **kwargs},
        )


class WebTechnology(BaseFinding):
    """A detected web technology, framework, server, or CMS. Child of web.endpoint or network.service. Produced by whatweb, wappalyzer, httpx, nikto."""

    schema_type: str = "web.technology"
    pik_fields: ClassVar[list[str]] = ["url", "technology_name"]

    @classmethod
    def create(
        cls,
        url: str,
        technology_name: str,
        version: Optional[str] = None,
        categories: Optional[list[str]] = None,
        cpe: Optional[str] = None,
        confidence: float = 1.0,
        host_ip: Optional[str] = None,
        port: Optional[int] = None,
        **kwargs,
    ):
        parent = None
        if host_ip and port:
            parent = Relation(
                target_type="network.service",
                target_pik={
                    "host_ip": host_ip,
                    "port": port,
                    "protocol": "tcp",
                },
                via="service_uses_technology",
            )
        else:
            parent = Relation(
                target_type="web.endpoint",
                target_pik={"url": url},
                via="endpoint_uses_technology",
            )

        cls_kwargs = {}
        if "schema_version" in kwargs:
            cls_kwargs["schema_version"] = kwargs.pop("schema_version")
        if "status" in kwargs:
            cls_kwargs["status"] = kwargs.pop("status")

        data = {
            "url": url,
            "technology_name": technology_name,
            "version": version,
            "categories": categories or [],
            "cpe": cpe,
            "confidence": max(0.0, min(1.0, float(confidence))),
            **kwargs,
        }
        if host_ip:
            data["host_ip"] = host_ip
        if port:
            data["port"] = port

        return cls(
            pik={"url": url, "technology_name": technology_name},
            parent=parent,
            data=data,
            **cls_kwargs,
        )
