from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cyguide.engine.gateway import ActionGateway, ActionValidationError
from cyguide.engine.store import GraphStore
from cyguide.schemas.dns import DnsRecord
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.power import ActionRequest, ActionSource


def get_mock_registry():
    registry = MagicMock()

    # Mock nmap tool accepting network.host
    nmap_manifest = MagicMock()
    nmap_manifest.meta.name = "nmap"
    nmap_manifest.input = {"accepts": ["network.host"]}

    # Mock gobuster tool accepting web.endpoint and network.service
    gobuster_manifest = MagicMock()
    gobuster_manifest.meta.name = "gobuster"
    gobuster_manifest.input = {"accepts": ["web.endpoint", "network.service"]}

    def get_tool_mock(name):
        if name == "nmap":
            return {"manifest": nmap_manifest, "adapter": MagicMock()}
        elif name == "gobuster":
            return {"manifest": gobuster_manifest, "adapter": MagicMock()}
        return None

    registry.get_tool.side_effect = get_tool_mock
    return registry


@pytest.mark.asyncio
async def test_gateway_user_explicit_shell():
    store = GraphStore(":memory:")
    await store.initialize()
    gateway = ActionGateway(get_mock_registry(), store)

    # 1. USER with explicit shell prefix '!' is allowed
    action = ActionRequest(
        session_id=uuid4(),
        tool_name="ping 127.0.0.1",
        is_explicit_shell=True,
        triggered_by=ActionSource.USER,
    )
    assert await gateway.validate_action(action) is True

    # 2. USER without explicit shell prefix on unregistered tool is rejected
    action_no_prefix = ActionRequest(
        session_id=uuid4(),
        tool_name="ping 127.0.0.1",
        is_explicit_shell=False,
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="is not a registered tool"):
        await gateway.validate_action(action_no_prefix)
    await store.close()


@pytest.mark.asyncio
async def test_gateway_agent_shell_restriction():
    store = GraphStore(":memory:")
    await store.initialize()
    gateway = ActionGateway(get_mock_registry(), store)

    # AGENT attempting raw shell command must be rejected even with explicit flag
    action = ActionRequest(
        session_id=uuid4(),
        tool_name="whoami",
        is_explicit_shell=True,
        triggered_by=ActionSource.AGENT,
    )
    with pytest.raises(ActionValidationError, match="is not a registered tool"):
        await gateway.validate_action(action)
    await store.close()


@pytest.mark.asyncio
async def test_gateway_registered_tool_schema_compatibility():
    store = GraphStore(":memory:")
    await store.initialize()
    gateway = ActionGateway(get_mock_registry(), store)
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Sess")

    # 1. Compatible target (nmap on network.host)
    host = NetworkHost.create(ip="10.0.0.1")
    host_id = await store.upsert_finding(sess_id, host)

    action_valid = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        target_entity_id=host_id,
        triggered_by=ActionSource.USER,
    )
    assert await gateway.validate_action(action_valid) is True

    # 2. Incompatible target (nmap on dns.record)
    dns = DnsRecord.create(domain="example.com", record_type="A", value="1.2.3.4")
    dns_id = await store.upsert_finding(sess_id, dns)

    action_invalid = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        target_entity_id=dns_id,
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="does not accept input type 'dns.record'"):
        await gateway.validate_action(action_invalid)
    await store.close()


@pytest.mark.asyncio
async def test_gateway_nonexistent_target_entity():
    store = GraphStore(":memory:")
    await store.initialize()
    gateway = ActionGateway(get_mock_registry(), store)
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Sess")

    action = ActionRequest(
        session_id=sess_id,
        tool_name="nmap",
        target_entity_id="nonexistent_entity_id",
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Target entity 'nonexistent_entity_id' not found"
    ):
        await gateway.validate_action(action)
    await store.close()


@pytest.mark.asyncio
async def test_gateway_missing_target_entity_by_agent():
    store = GraphStore(":memory:")
    await store.initialize()
    gateway = ActionGateway(get_mock_registry(), store)
    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Sess")

    # AGENT calling tool without target entity is rejected
    action = ActionRequest(
        session_id=sess_id, tool_name="nmap", target_entity_id=None, triggered_by=ActionSource.AGENT
    )
    with pytest.raises(ActionValidationError, match="requires a selected target entity"):
        await gateway.validate_action(action)
    await store.close()
