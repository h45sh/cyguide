from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from cyguide.app import CyGuideApp
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource


@pytest.mark.asyncio
async def test_store_session_lifecycle():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS")
    sess_id = await store.create_session(ws_id, "Session 1")

    # Initial state is ACTIVE
    sess = await store.get_session(sess_id)
    assert sess["status"] == "ACTIVE"
    assert sess.get("closed_at") is None

    # Close session
    await store.close_session(sess_id)
    sess = await store.get_session(sess_id)
    assert sess["status"] == "CLOSED"
    assert sess.get("closed_at") is not None

    # Filtered listing
    active = await store.list_sessions(ws_id, status_filter="ACTIVE")
    closed = await store.list_sessions(ws_id, status_filter="CLOSED")
    all_sess = await store.list_sessions(ws_id)
    assert len(active) == 0
    assert len(closed) == 1
    assert len(all_sess) == 1

    # Reopen session
    await store.reopen_session(sess_id)
    sess = await store.get_session(sess_id)
    assert sess["status"] == "ACTIVE"
    assert sess.get("closed_at") is None
    await store.close()


@pytest.mark.asyncio
async def test_store_workspace_lifecycle():
    store = GraphStore(":memory:")
    await store.initialize()
    ws_id = await store.create_workspace("TestWS2")
    ws = await store.get_workspace(ws_id)
    assert ws["status"] == "ACTIVE"
    assert ws.get("closed_at") is None

    await store.close_workspace(ws_id)
    ws = await store.get_workspace(ws_id)
    assert ws["status"] == "CLOSED"
    assert ws.get("closed_at") is not None

    active_ws = await store.list_workspaces(status_filter="ACTIVE")
    closed_ws = await store.list_workspaces(status_filter="CLOSED")
    assert all(w["id"] != ws_id for w in active_ws)
    assert any(w["id"] == ws_id for w in closed_ws)

    await store.reopen_workspace(ws_id)
    ws = await store.get_workspace(ws_id)
    assert ws["status"] == "ACTIVE"
    assert ws.get("closed_at") is None
    await store.close()


@pytest.mark.asyncio
async def test_facade_close_reopen_and_guard():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    executor.stop_task = AsyncMock()
    registry = MagicMock()
    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await facade.create_workspace("FacadeWS")
    sess_id = await facade.create_session(ws_id, "Audited Engagement")

    # Close session via facade
    await facade.close_session(sess_id)
    sess = await facade.store.get_session(sess_id)
    assert sess["status"] == "CLOSED"

    # Verify audit event was logged
    events = await facade.store.get_event_log(sess_id)
    assert any(e.get("schema_type") == "system.session_closed" for e in events)

    # Forensic execution guard: attempt to submit action to closed session
    action = ActionRequest(
        session_id=UUID(sess_id),
        tool_name="nmap",
        params={"raw_flags": "127.0.0.1"},
        triggered_by=ActionSource.USER,
    )

    with pytest.raises(PermissionError, match="Cannot execute actions in an archived session"):
        await facade.submit_action(action)

    # Reopen session
    await facade.reopen_session(sess_id)
    sess = await facade.store.get_session(sess_id)
    assert sess["status"] == "ACTIVE"

    # Verify reopen audit event
    events = await facade.store.get_event_log(sess_id)
    assert any(e.get("schema_type") == "system.session_reopened" for e in events)

    await store.close()


@pytest.mark.asyncio
async def test_dashboard_toggle_history_and_archive(tmp_path):
    db_file = str(tmp_path / "test_dash_hist.db")
    app = CyGuideApp(db_path=db_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        dash = app.screen
        assert hasattr(dash, "session_filter")
        assert dash.session_filter == "ACTIVE"

        # Create a workspace and session
        ws_id = await app.store.create_workspace("TestEngagement")
        sess_id = await app.store.create_session(ws_id, "ReconSession")
        await dash.show_workspace_details(ws_id)
        await pilot.pause()

        assert dash.selected_ws_id == ws_id
        assert dash.selected_session_id == sess_id

        # 1. Archive the active session
        await dash.action_toggle_archive_session()
        await pilot.pause()
        archived_sess = await app.store.get_session(sess_id)
        assert archived_sess["status"] == "CLOSED"

        # 2. Toggle to history view
        await dash.action_toggle_history_mode()
        await pilot.pause()
        assert dash.session_filter == "HISTORY"

        # 3. Reopen the session while in history view
        assert dash.selected_session_id == sess_id
        await dash.action_toggle_archive_session()
        await pilot.pause()
        reopened_sess = await app.store.get_session(sess_id)
        assert reopened_sess["status"] == "ACTIVE"

        # 4. Toggle back to active view
        await dash.action_toggle_history_mode()
        await pilot.pause()
        assert dash.session_filter == "ACTIVE"

        # 5. Verify physical keybindings (ctrl+a and ctrl+h)
        await pilot.press("ctrl+a")
        await pilot.pause()
        sess_after_key = await app.store.get_session(sess_id)
        assert sess_after_key["status"] == "CLOSED"

        await pilot.press("ctrl+h")
        await pilot.pause()
        assert dash.session_filter == "HISTORY"

        await pilot.press("ctrl+a")
        await pilot.pause()
        sess_reopened_key = await app.store.get_session(sess_id)
        assert sess_reopened_key["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_dashboard_handle_new_finding_throttling(tmp_path):
    from cyguide.app import CyGuideApp
    from cyguide.schemas.network import NetworkHost

    db_path = str(tmp_path / "test_finding_throttle.db")
    app = CyGuideApp(db_path=db_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        dash = app.screen
        ws_id = await app.store.create_workspace("ThrottleEngagement")
        sess_id = await app.store.create_session(ws_id, "ThrottleSession")
        await dash.show_workspace_details(ws_id)
        await pilot.pause()

        # Fire 50 findings rapidly
        for i in range(50):
            finding = NetworkHost.create(ip=f"10.0.0.{i}")
            await dash.handle_new_finding(sess_id, finding)

        # Metrics debounce task was created
        assert dash._metrics_debounce_task is not None
        await dash._metrics_debounce_task
        # Activity list was rate-limited, not flooded with 50 items
        act_list = dash.query_one("#activity_list")
        assert len(act_list.children) < 5

