# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""Foundational Pydantic models for CyGuide findings."""

from datetime import UTC, datetime
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from cyguide.common.canonicalize import canonicalize_mapping


class Relation(BaseModel):
    """Represents an edge in the entity graph."""

    target_type: str  # e.g. "network.host"
    target_pik: Dict[str, Any]  # The PIK fields of the target entity
    via: str  # Relationship name, e.g. "has_service"

    @field_validator("target_pik", mode="before")
    @classmethod
    def apply_canonicalization(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return canonicalize_mapping(v)
        return v


class BaseFinding(BaseModel):
    """The base finding structure all schemas must follow."""

    schema_type: str  # e.g. "network.service"
    pik_fields: ClassVar[List[str]] = []  # Declarative PIK fields for registry/linter
    pik: Dict[str, Any]  # Primary Identity Key fields
    parent: Optional[Relation] = None
    associations: List[Relation] = Field(default_factory=list)
    data: Dict[str, Any]  # Additional finding data
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["confirmed", "proposed"] = "confirmed"

    @field_validator("pik", "data", mode="before")
    @classmethod
    def apply_canonicalization(cls, v: Any) -> Any:
        """Apply declarative normalization filters to PIK and data dictionary fields."""
        if isinstance(v, dict):
            return canonicalize_mapping(v)
        return v
