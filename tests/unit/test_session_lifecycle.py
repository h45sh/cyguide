from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from cyguide.app import CyGuideApp
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.power import ActionRequest, ActionSource


@pytest.mark.asyncio
async def test_facade_close_reopen_and_guard():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    executor.stop_task = AsyncMock()
    registry = MagicMock()
    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await facade.workspaces.create_workspace("FacadeWS")
    sess_id = await facade.workspaces.create_session(ws_id, "Audited Engagement")

    # Close session via workspaces
    await facade.workspaces.close_session(sess_id)
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
    await facade.workspaces.reopen_session(sess_id)
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
