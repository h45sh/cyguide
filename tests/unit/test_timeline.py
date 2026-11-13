"""Unit tests for ActionTimelineRepository deep module."""

import pytest

from cyguide.engine.store import GraphStore
from cyguide.engine.timeline import ActionTimelineRepository
from cyguide.schemas.power import ActionRequest, ActionSource


@pytest.mark.asyncio
async def test_action_timeline_repository(tmp_path):
    db_file = str(tmp_path / "test_timeline.db")
    store = GraphStore(db_file)
    await store.initialize()

    ws_id = await store.create_workspace("Timeline WS")
    sess_id = await store.create_session(ws_id, "Timeline Session")

    timeline = ActionTimelineRepository(store)

    # 1. Record an execution event
    action = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        params={"raw_flags": "-sV 10.0.0.1"},
        triggered_by=ActionSource.USER,
    )
    await timeline.append_event(sess_id, action, {"output": "Port 80 open"}, "Ran nmap scan")

    # 2. Record an audit event
    await timeline.log_audit_event(sess_id, "session_archived", "Archived session", "CLOSED")

    # 3. Retrieve event log
    events = await timeline.get_event_log(sess_id)
    assert len(events) == 2
    assert events[0]["schema_type"] == "system.event"
    assert events[1]["schema_type"] == "system.session_archived"

    # 4. Check closed count and mark event closed
    assert await timeline.get_closed_events_count(sess_id) == 0
    await timeline.mark_event_closed(str(action.action_id), session_id=sess_id)
    assert await timeline.get_closed_events_count(sess_id) == 1

    # Non-closed log should now only have the audit event
    active_events = await timeline.get_event_log(sess_id)
    assert len(active_events) == 1
    assert active_events[0]["schema_type"] == "system.session_archived"

    await store.close()
