import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.schemas.network import NetworkHost

@pytest.mark.asyncio
async def test_facade_get_context_resolution():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()

    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")

    # 1. Create a node
    host = NetworkHost.create(ip="10.0.0.5")
    node_id = await store.upsert_finding(sess_id, host)

    # 2. Get context with selected node
    ctx = await facade.get_context(sess_id, node_id)

    assert ctx.session_name == "Session"
    assert ctx.resolved_vars["TARGET"] == "10.0.0.5"
    assert ctx.entity_counts["network.host"] == 1

    await store.close()


@pytest.mark.asyncio
async def test_facade_submit_shell_action():
    from uuid import UUID
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    executor.run_tool = MagicMock()
    registry = MagicMock()
    registry.get_tool.return_value = None

    facade = PowerWorkspaceFacade(store, executor, registry)
    ws_id = await facade.create_workspace("TestWS")
    sess_id = await facade.create_session(ws_id, "ShellSess")

    action = ActionRequest(
        session_id=UUID(sess_id),
        tool_name="ls",
        params={"raw_flags": "-la"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True
    )

    job_id = await facade.submit_action(action)
    assert job_id == action.action_id
    assert job_id in facade._active_jobs
    assert facade._active_jobs[job_id].tool_name == "ls"
    await store.close()

@pytest.mark.asyncio
async def test_facade_submit_action_validation():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()

    # Mock registry to return a tool that accepts network.host
    manifest = MagicMock()
    manifest.meta.name = "nmap"
    manifest.input.get.return_value = ["network.host"]
    registry.get_tool.return_value = {"adapter": MagicMock(), "manifest": manifest}

    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await store.create_workspace("Test")
    sess_id = await store.create_session(ws_id, "Session")
    host = NetworkHost.create(ip="10.0.0.5")
    node_id = await store.upsert_finding(sess_id, host)

    action = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        target_entity_id=node_id,
        triggered_by=ActionSource.USER
    )

    # This should pass validation and start a background task
    job_id = await facade.submit_action(action)
    assert job_id == action.action_id
    assert job_id in facade._active_jobs

    await store.close()

@pytest.mark.asyncio
async def test_facade_uniqueness():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()
    facade = PowerWorkspaceFacade(store, executor, registry)

    # 1. Workspace uniqueness
    ws1_id = await facade.create_workspace("Project A")
    assert ws1_id is not None

    with pytest.raises(ValueError, match="Workspace with this name already exists"):
        await facade.create_workspace("project a")  # case-insensitive duplicate

    ws2_id = await facade.create_workspace("Project B")
    with pytest.raises(ValueError, match="Workspace with this name already exists"):
        await facade.rename_workspace(ws2_id, "project a")

    # 2. Session uniqueness
    sess1_id = await facade.create_session(ws1_id, "Session A")
    assert sess1_id is not None

    with pytest.raises(ValueError, match="Session with this name already exists"):
        await facade.create_session(ws1_id, "session a")

    sess2_id = await facade.create_session(ws1_id, "Session B")
    with pytest.raises(ValueError, match="Session with this name already exists"):
        await facade.rename_session(sess2_id, "session a")

    # 3. Move session uniqueness
    # Create Session A in Workspace B
    await facade.create_session(ws2_id, "Session A")
    with pytest.raises(ValueError, match="A session with this name already exists in the target workspace"):
        await facade.move_session(sess1_id, ws2_id) # Should fail as ws2 already has "Session A"

    await store.close()

@pytest.mark.asyncio
async def test_facade_deletion_cleanup():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = AsyncMock() # Use AsyncMock to mock stop_task
    registry = MagicMock()
    facade = PowerWorkspaceFacade(store, executor, registry)

    ws_id = await facade.create_workspace("Project A")
    sess_id = await facade.create_session(ws_id, "Session A")

    # Mock active jobs
    from cyguide.schemas.power import JobStatus, JobStatusEnum
    from uuid import UUID
    import datetime

    job_uuid = uuid4()
    job = JobStatus(
        job_id=job_uuid,
        session_id=UUID(sess_id),
        tool_name="nmap",
        status=JobStatusEnum.RUNNING,
        started_at=datetime.datetime.now(datetime.UTC)
    )
    facade._active_jobs[job_uuid] = job
    facade.closed_job_ids.add(str(job_uuid))

    # Delete session
    await facade.delete_session(sess_id)

    # Verify executor.stop_task called and facade tracking cleaned up
    executor.stop_task.assert_called_once_with(str(job_uuid))
    assert job_uuid not in facade._active_jobs
    assert str(job_uuid) not in facade.closed_job_ids

    await store.close()
