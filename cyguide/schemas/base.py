# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""Foundational Pydantic models for CyGuide findings."""

from datetime import datetime, UTC
from typing import Optional, Dict, List, Any, ClassVar, Literal
from pydantic import BaseModel, Field, field_validator
from cyguide.engine.canonicalize import canonicalize


class Relation(BaseModel):
    """Represents an edge in the entity graph."""
    target_type: str        # e.g. "network.host"
    target_pik: Dict[str, Any]  # The PIK fields of the target entity
    via: str                # Relationship name, e.g. "has_service"


class BaseFinding(BaseModel):
    """The base finding structure all schemas must follow."""
    schema_type: str        # e.g. "network.service"
    pik_fields: ClassVar[List[str]] = [] # Declarative PIK fields for registry/linter
    pik: Dict[str, Any]     # Primary Identity Key fields
    parent: Optional[Relation] = None
    associations: List[Relation] = Field(default_factory=list)
    data: Dict[str, Any]    # Additional finding data
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["confirmed", "proposed"] = "confirmed"

    @field_validator('*', mode='before')
    @classmethod
    def apply_canonicalization(cls, v):
        """Apply global normalization filters to all fields."""
        if isinstance(v, dict):
            return {k: canonicalize(val) for k, val in v.items()}
        if isinstance(v, list):
            return [canonicalize(val) for val in v]
        return canonicalize(v)
