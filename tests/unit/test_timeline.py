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

    # 5. Query timeline by schema_type and keyword
    filtered = await timeline.query_timeline(sess_id, schema_type="system.session_archived")
    assert len(filtered) == 1
    assert filtered[0]["schema_type"] == "system.session_archived"

    kw_filtered = await timeline.query_timeline(sess_id, keyword="Archived")
    assert len(kw_filtered) == 1

    no_match = await timeline.query_timeline(sess_id, keyword="nonexistent_xyz")
    assert len(no_match) == 0

    # 6. Replay session history
    replayed = await timeline.replay_session_history(sess_id)
    assert len(replayed) == 1
    assert replayed[0]["schema_type"] == "system.session_archived"
    assert replayed[0]["message"] == "Archived session"

    # 7. Compact timeline
    pruned = await timeline.compact_timeline(sess_id, keep_closed_events=0)
    assert pruned == 1
    assert await timeline.get_closed_events_count(sess_id) == 0

    await store.close()
