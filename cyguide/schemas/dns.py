"""DNS and Domain related schemas."""

from typing import Optional, List, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_host


class DnsRecord(BaseFinding):
    """A single DNS entry mapping a name to a value. Produced by dig, whois, or passive DNS tools."""
    schema_type: str = "dns.record"
    pik_fields: ClassVar[List[str]] = ["domain", "type", "value"]

    @classmethod
    def create(cls, domain: str, record_type: str, value: str, resolved_ip: Optional[str] = None):
        pik = {
            "domain": domain.lower().strip(),
            "type": record_type.upper(),
            "value": value.strip()
        }
        
        associations = []
        if resolved_ip:
            normalized_ip = canonicalize_host(resolved_ip)
            associations.append(Relation(
                target_type="network.host",
                target_pik={"ip": normalized_ip},
                via="resolves_to"
            ))
            
        return cls(
            pik=pik,
            associations=associations,
            data={
                **pik,
                "resolved_ip": resolved_ip
            }
        )

class DomainInfo(BaseFinding):
    """Whois registration data for a domain — owner, registrar, dates. Produced by whois."""
    schema_type: str = "domain.info"
    pik_fields: ClassVar[List[str]] = ["domain"]

    @classmethod
    def create(cls, domain: str, registrar: Optional[str] = None, organization: Optional[str] = None):
        pik = {"domain": domain.lower().strip()}
        
        # Link to the broad dns.record namespace for this domain
        associations = [
            Relation(
                target_type="dns.record",
                target_pik={"domain": pik["domain"], "type": "ANY", "value": "ANY"},
                via="whois_data_for"
            )
        ]
        
        return cls(
            pik=pik,
            associations=associations,
            data={
                **pik,
                "registrar": registrar,
                "organization": organization
            }
        )
