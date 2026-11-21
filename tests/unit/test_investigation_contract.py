"""Unit tests verifying InvestigationSession protocol compliance across Power & Learning engines."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cyguide.engine.learning import LearningSession
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.engine.session import InvestigationSession
from cyguide.engine.store import GraphStore


@pytest.mark.asyncio
async def test_investigation_session_contract_conformance():
    store = GraphStore(":memory:")
    await store.initialize()
    executor = MagicMock()
    registry = MagicMock()
    registry.get_tool.return_value = None

    execution = MagicMock()
    learning = LearningSession(store=store, registry=registry, execution=execution)
    power = PowerWorkspaceFacade(store=store, executor=executor, registry=registry)

    # 1. Structural runtime protocol check
    assert isinstance(learning, InvestigationSession), (
        "LearningSession must implement InvestigationSession"
    )
    assert isinstance(power, InvestigationSession), (
        "PowerWorkspaceFacade must implement InvestigationSession"
    )

    # 2. Polymorphic attribute contracts
    for session in (learning, power):
        assert hasattr(session, "session_id")
        assert hasattr(session, "workspace_id")
        assert hasattr(session, "store")
        assert hasattr(session, "registry")
        assert hasattr(session, "execution")
        assert hasattr(session, "explainer")
        assert callable(session.extract_structured_findings)
        assert callable(session.verify_preflight)
        assert callable(session.get_graph_snapshot)
        assert callable(session.get_notes)
        assert callable(session.save_notes)
        assert callable(session.execute)

    # 3. Polymorphic behavior: Notes roundtrip
    learning.session_id = uuid4()
    await learning.save_notes("Learning note content")
    assert await learning.get_notes() == "Learning note content"

    ws_id = await power.workspaces.create_workspace("SeamWS")
    sess_id = await power.workspaces.create_session(ws_id, "SeamSession")
    power.session_id = sess_id
    await power.save_notes("Power note content")
    assert await power.get_notes() == "Power note content"

    # 4. Polymorphic behavior: Graph snapshots
    learning_graph = await learning.get_graph_snapshot()
    assert "nodes" in learning_graph and "edges" in learning_graph

    power_graph = await power.get_graph_snapshot()
    assert "nodes" in power_graph and "edges" in power_graph

    # 5. Polymorphic behavior: Finding extraction
    text, count = await learning.extract_structured_findings()
    assert isinstance(text, str)
    text_p, count_p = await power.extract_structured_findings()
    assert isinstance(text_p, str)

    await store.close()
