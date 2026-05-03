"""Credential finding schemas."""

from typing import Optional, ClassVar
from cyguide.schemas.base import BaseFinding, Relation
from cyguide.engine.canonicalize import canonicalize_host


class CredentialFound(BaseFinding):
    """A username/password or token discovery. Linked to a host or domain. Produced by hydra, medusa, leak-lookups."""
    schema_type: str = "credential.found"
    pik_fields: ClassVar[list[str]] = ["context", "username"]

    @classmethod
    def create(cls, context: str, username: str, password: Optional[str] = None, host_ip: Optional[str] = None, **kwargs):
        parent = None
        if host_ip:
            parent = Relation(
                target_type="network.host",
                target_pik={"ip": canonicalize_host(host_ip)},
                via="credential_for_host"
            )
            
        return cls(
            pik={"context": context, "username": username},
            parent=parent,
            data={
                "context": context,
                "username": username,
                "password": password,
                "host_ip": host_ip,
                **kwargs
            }
        )
