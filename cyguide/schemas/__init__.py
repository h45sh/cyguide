"""Canonical findings and intelligence schemas for CyGuide."""

from cyguide.schemas.base import BaseFinding, Relation
from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.dns import DnsRecord, DomainInfo, EntityAlias
from cyguide.schemas.host_internal import (
    FileSystemObject,
    ProcessRunning,
    SoftwarePackage,
)
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

__all__ = [
    "AuditMisconfig",
    "BaseFinding",
    "CredentialFound",
    "DnsRecord",
    "DomainInfo",
    "EntityAlias",
    "ExploitReference",
    "FileSystemObject",
    "NetworkHost",
    "NetworkNetblock",
    "NetworkService",
    "ProcessRunning",
    "Relation",
    "SoftwarePackage",
    "TLSCertificate",
    "VulnerabilityFound",
    "WebEndpoint",
    "WebResource",
    "WebTechnology",
    "WebVulnerability",
]
