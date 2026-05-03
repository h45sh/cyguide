"""Network netblock related schemas."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding


class NetworkNetblock(BaseFinding):
    """An IP range with ownership data — org, ASN, CIDR. Produced by whois against an IP."""
    schema_type: str = "network.netblock"
    pik_fields: ClassVar[list[str]] = ["cidr"]

    @classmethod
    def create(cls, cidr: str, organization: Optional[str] = None, asn: Optional[str] = None):
        pik = {"cidr": cidr.strip()}
        return cls(
            pik=pik,
            data={
                **pik,
                "organization": organization,
                "asn": asn
            }
        )
