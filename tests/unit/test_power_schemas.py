import pytest
from uuid import uuid4
from cyguide.schemas.power import ActionRequest, ActionSource, PowerSession, JobStatus, JobStatusEnum, WorkspaceContext

def test_action_request_creation():
    session_id = uuid4()
    action = ActionRequest(
        session_id=session_id,
        tool_name="nmap",
        target_entity_id="host:127.0.0.1",
        params={"flags": "-sV"},
        triggered_by=ActionSource.USER
    )
    assert action.tool_name == "nmap"
    assert action.session_id == session_id
    assert action.triggered_by == ActionSource.USER

def test_workspace_context_defaults():
    session_id = uuid4()
    ctx = WorkspaceContext(
        session_id=session_id,
        session_name="Test Session"
    )
    assert ctx.session_name == "Test Session"
    assert ctx.resolved_vars == {}
    assert ctx.active_jobs == []
