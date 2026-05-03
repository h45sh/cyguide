"""Entity aliasing and linkage schemas."""

from typing import List, ClassVar
from cyguide.schemas.base import BaseFinding, Relation

class EntityAlias(BaseFinding):
    """Links two identifiers that represent the same entity (e.g. hostname to IP). Produced by resolvers."""
    schema_type: str = "entity.alias"
    pik_fields: ClassVar[list[str]] = ["source_id", "target_id"]

    @classmethod
    def create(cls, source_id: str, target_id: str, relation_type: str = "alias_of", **kwargs):
        # This is a meta-finding that doesn't necessarily have a structural parent,
        # but links two existing entities.
        return cls(
            pik={"source_id": source_id, "target_id": target_id},
            data={"source_id": source_id, "target_id": target_id, "relation_type": relation_type, **kwargs}
        )
