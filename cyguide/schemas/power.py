"""Schemas for Power Mode sessions, actions, and context."""

from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Dict, List, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from cyguide.schemas.base import BaseFinding


class ActionSource(str, Enum):
    """Origin of a tool action."""
    USER = "USER"
    SUGGESTION = "SUGGESTION"
    AGENT = "AGENT"


class JobStatusEnum(str, Enum):
    """Current state of a tool execution job."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class PowerSession(BaseModel):
    """An investigation-scoped session."""
    session_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    name: Optional[str] = None


class ActionRequest(BaseModel):
    """A typed request to execute a tool action."""
    action_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    tool_name: str
    target_entity_id: Optional[str] = None  # Optional for general shell commands
    params: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: ActionSource = ActionSource.USER
    is_explicit_shell: bool = False  # True if prefix '!' was used
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobStatus(BaseModel):
    """Real-time status of a job in the queue."""
    job_id: UUID
    tool_name: str
    status: JobStatusEnum
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None


class WorkspaceContext(BaseModel):
    """Point-in-time snapshot of the Power Mode workspace."""
    session_id: UUID
    session_name: Optional[str]
    selected_entity: Optional[BaseFinding] = None
    resolved_vars: Dict[str, Any] = Field(default_factory=dict) # e.g. {"TARGET": "10.10.10.5"}
    active_jobs: List[JobStatus] = Field(default_factory=list)
    entity_counts: Dict[str, int] = Field(default_factory=dict)
    cwd: str = Field(default_factory=lambda: "/home/harsh/Documents/cyguide") # Default placeholder
