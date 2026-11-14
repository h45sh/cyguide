"""Unit tests for the WorkspaceRepository deep module."""

import pytest

from cyguide.engine.store import GraphStore
from cyguide.engine.workspace_repository import WorkspaceRepository


@pytest.mark.asyncio
async def test_workspace_crud_and_uniqueness():
    """Verify workspace creation, case-insensitive collision rejection, and renaming."""
    store = GraphStore(":memory:")
    await store.initialize()
    repo = WorkspaceRepository(store)

    try:
        # Create workspace
        ws_id = await repo.create_workspace("Client Engagement")
        assert ws_id is not None

        # Verify case-insensitive collision rejection
        with pytest.raises(ValueError, match="already exists"):
            await repo.create_workspace("client engagement")

        # Rename workspace
        await repo.rename_workspace(ws_id, "Client Engagement (Q4)")
        ws = await repo.get_workspace(ws_id)
        assert ws is not None
        assert ws["name"] == "Client Engagement (Q4)"

        # List workspaces
        workspaces = await repo.list_workspaces()
        names = [w["name"] for w in workspaces]
        assert "Client Engagement (Q4)" in names
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_session_lifecycle_and_move():
    """Verify session creation, renaming, moving, and deletion within workspaces."""
    store = GraphStore(":memory:")
    await store.initialize()
    repo = WorkspaceRepository(store)

    try:
        ws1 = await repo.create_workspace("Workspace A")
        ws2 = await repo.create_workspace("Workspace B")

        # Create session in ws1
        sess_id = await repo.create_session(ws1, "Recon Phase")
        assert sess_id is not None

        # Duplicate session name rejection within same workspace
        with pytest.raises(ValueError, match="already exists in this workspace"):
            await repo.create_session(ws1, "recon phase")

        # Same session name in different workspace is allowed
        sess2_id = await repo.create_session(ws2, "Recon Phase")
        assert sess2_id is not None

        # Moving sess_id to ws2 should fail due to collision
        with pytest.raises(ValueError, match="already exists in the target workspace"):
            await repo.move_session(sess_id, ws2)

        # Rename session
        await repo.rename_session(sess_id, "External Recon")
        sess_meta = await repo.get_session(sess_id)
        assert sess_meta["name"] == "External Recon"

        # Now move session to ws2 succeeds
        await repo.move_session(sess_id, ws2)
        sess_meta_after = await repo.get_session(sess_id)
        assert sess_meta_after["workspace_id"] == ws2

        # Delete session
        await repo.delete_session(sess_id)
        deleted = await repo.get_session(sess_id)
        assert deleted is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_session_and_workspace_close_reopen_audit():
    """Verify forensic closure, audit logging, and reopening of sessions and workspaces."""
    store = GraphStore(":memory:")
    await store.initialize()
    repo = WorkspaceRepository(store)

    try:
        ws_id = await repo.create_workspace("Audit Target")
        sess_id = await repo.create_session(ws_id, "Active Phase")

        # Close session
        await repo.close_session(sess_id)
        sess = await repo.get_session(sess_id)
        assert sess["status"] == "CLOSED"

        # Reopen session
        await repo.reopen_session(sess_id)
        sess = await repo.get_session(sess_id)
        assert sess["status"] == "ACTIVE"

        # Close workspace cascades to sessions
        await repo.close_workspace(ws_id)
        ws = await repo.get_workspace(ws_id)
        sess = await repo.get_session(sess_id)
        assert ws["status"] == "CLOSED"
        assert sess["status"] == "CLOSED"

        # Reopen workspace
        await repo.reopen_workspace(ws_id)
        ws = await repo.get_workspace(ws_id)
        assert ws["status"] == "ACTIVE"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_entity_alias_and_graph_queries():
    """Verify setting custom entity aliases and querying aggregate stats."""
    store = GraphStore(":memory:")
    await store.initialize()
    repo = WorkspaceRepository(store)

    try:
        ws_id = await repo.create_workspace("Graph WS")
        sess_id = await repo.create_session(ws_id, "Graph Sess")

        from cyguide.schemas.network import NetworkHost

        host = NetworkHost.create(ip="192.168.1.100", hostname="dev-box")
        host.status = "confirmed"
        node_id = await store.upsert_finding(sess_id, host)

        # Set friendly entity alias
        await repo.set_entity_alias(sess_id, node_id, "DC-Primary")
        node = await repo.get_node(sess_id, node_id)
        assert node is not None
        import json

        data = json.loads(node["data_json"])
        assert data.get("alias") == "DC-Primary"

        # Query all nodes and stats
        nodes = await repo.get_all_nodes(sess_id)
        assert len(nodes) == 1
        assert nodes[0]["id"] == node_id

        stats = await repo.get_stats(session_id=sess_id)
        assert stats.get("total", 0) >= 1
    finally:
        await store.close()
