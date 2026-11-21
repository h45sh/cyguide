"""Unit tests verifying SQLite-backed notes isolation across Power Mode and Learning Mode."""

import pytest

from cyguide.engine.learning import LearningSession
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.store import GraphStore


@pytest.mark.asyncio
async def test_notes_sqlite_storage_and_isolation():
    """Verify that GraphStore stores and isolates notes by scope and id."""
    store = GraphStore(":memory:")
    await store.initialize()

    # Store notes for Power Mode Session 1
    await store.save_notes("session", "sess-1", "# Red Team Notes\nTarget: 10.10.10.1")
    # Store notes for Power Mode Session 2
    await store.save_notes("session", "sess-2", "# Internal Scope\nDomain: corp.local")
    # Store notes for Learning Mode Lab
    await store.save_notes("learning", "lab-1", "Learned about -sS SYN stealth scan.")

    # Read back and verify strict isolation
    assert await store.get_notes("session", "sess-1") == "# Red Team Notes\nTarget: 10.10.10.1"
    assert await store.get_notes("session", "sess-2") == "# Internal Scope\nDomain: corp.local"
    assert await store.get_notes("learning", "lab-1") == "Learned about -sS SYN stealth scan."

    # Update session 1 notes
    await store.save_notes("session", "sess-1", "# Red Team Notes\nFound CVE-2024-1234")
    assert await store.get_notes("session", "sess-1") == "# Red Team Notes\nFound CVE-2024-1234"
    # Ensure lab notes were untouched
    assert await store.get_notes("learning", "lab-1") == "Learned about -sS SYN stealth scan."

    await store.close()


@pytest.mark.asyncio
async def test_learning_session_reset_never_touches_power_notes():
    """Verify that resetting a LearningSession clears lab notes without affecting Power Mode notes."""
    store = GraphStore(":memory:")
    await store.initialize()

    ws_id = await store.create_workspace("Client Engagement")
    power_sess_id = await store.create_session(ws_id, "External Network")
    learning_sess_id = await store.create_session(ws_id, "Nmap Tutorial")

    # Set notes in both modes
    await store.save_notes(
        "session", power_sess_id, "# Sensitive Findings\nAdministrator password leaked."
    )
    learning_session = LearningSession(
        store=store,
        registry=None,
        execution=None,
        session_id=learning_sess_id,
        workspace_id=ws_id,
    )
    await learning_session.save_notes("Student notes: Nmap timing templates -T0 to -T5.")

    # Verify both notes exist
    assert (
        await store.get_notes("session", power_sess_id)
        == "# Sensitive Findings\nAdministrator password leaked."
    )
    assert await learning_session.get_notes() == "Student notes: Nmap timing templates -T0 to -T5."

    # Reset learning session
    await learning_session.reset_session()

    # Learning notes must be empty
    assert await learning_session.get_notes() == ""
    assert await store.get_notes("learning", str(learning_sess_id)) == ""

    # Power Mode notes MUST remain completely intact
    assert (
        await store.get_notes("session", power_sess_id)
        == "# Sensitive Findings\nAdministrator password leaked."
    )

    await store.close()


@pytest.mark.asyncio
async def test_power_facade_notes_operations():
    """Verify that PowerWorkspaceFacade coordinates session notes with SQLite."""
    store = GraphStore(":memory:")
    await store.initialize()

    ws_id = await store.create_workspace("Red Team")
    sess_id = await store.create_session(ws_id, "Recon")

    facade = PowerWorkspaceFacade(store, executor=None, registry=None)

    assert await facade.get_notes(sess_id) == ""
    await facade.save_notes("Subfinder found 42 subdomains.", session_id=sess_id)
    assert await facade.get_notes(sess_id) == "Subfinder found 42 subdomains."

    # Verify directly in SQLite store
    assert await store.get_notes("session", sess_id) == "Subfinder found 42 subdomains."

    await store.close()


@pytest.mark.asyncio
async def test_session_deletion_cascades_notes():
    """Verify that deleting a session or workspace deletes its notes."""
    store = GraphStore(":memory:")
    await store.initialize()

    ws_id = await store.create_workspace("Engagement X")
    sess_id = await store.create_session(ws_id, "Session 1")

    await store.save_notes("session", sess_id, "Temporary notes.")
    assert await store.get_notes("session", sess_id) == "Temporary notes."

    await store.delete_session(sess_id)
    assert await store.get_notes("session", sess_id) == ""

    # Test workspace cascade
    sess_id2 = await store.create_session(ws_id, "Session 2")
    await store.save_notes("session", sess_id2, "Workspace notes.")
    await store.delete_workspace(ws_id)
    assert await store.get_notes("session", sess_id2) == ""

    await store.close()
