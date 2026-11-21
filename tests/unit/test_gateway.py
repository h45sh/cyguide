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


@pytest.mark.asyncio
async def test_gateway_blocks_cloud_metadata():
    store = GraphStore(":memory:")
    await store.initialize()

    mock_registry = MagicMock()
    mock_tool = MagicMock()
    mock_tool.input = {"accepts": ["network.host"]}
    mock_registry.get_tool.return_value = {"manifest": mock_tool, "adapter": MagicMock()}

    gateway = ActionGateway(mock_registry, store)

    # 1. Blocked via raw_flags
    action_flag = ActionRequest(
        session_id=uuid4(),
        tool_name="nmap",
        params={"raw_flags": "http://169.254.169.254/latest/meta-data/"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_flag)

    # 2. Blocked via tool_name
    action_name = ActionRequest(
        session_id=uuid4(),
        tool_name="curl 169.254.169.254",
        is_explicit_shell=True,
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_name)

    # 3. Blocked via Google metadata domain
    action_gcp = ActionRequest(
        session_id=uuid4(),
        tool_name="curl metadata.google.internal",
        is_explicit_shell=True,
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_gcp)

    await store.close()


@pytest.mark.asyncio
async def test_gateway_blocks_extended_metadata():
    store = GraphStore(":memory:")
    await store.initialize()

    mock_registry = MagicMock()
    gateway = ActionGateway(mock_registry, store)

    # 1. Azure / Generic link-local
    action_azure = ActionRequest(
        session_id=uuid4(),
        tool_name="nmap",
        params={"raw_flags": "169.254.169.250"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_azure)

    # 2. AWS IPv6 metadata
    action_ipv6 = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://[fd00:ec2::254]/latest/meta-data/"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_ipv6)

    # 3. Decimal IP notation
    action_dec = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://2852039166/"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(
        ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"
    ):
        await gateway.validate_action(action_dec)

    await store.close()


def test_gateway_imds_canonicalization_direct():
    from cyguide.engine.gateway import is_blocked_destination

    assert is_blocked_destination("169.254.169.254") is True
    assert is_blocked_destination("0251.0376.0251.0376") is True
    assert is_blocked_destination("0xa9.0xfe.0xa9.0xfe") is True
    assert is_blocked_destination("2852039166") is True
    assert is_blocked_destination("::ffff:169.254.169.254") is True
    assert is_blocked_destination("::ffff:a9fe:a9fe") is True
    assert is_blocked_destination("fd00:ec2::254") is True
    assert is_blocked_destination("fe80::1") is True
    assert is_blocked_destination("metadata.google.internal") is True

    assert is_blocked_destination("8.8.8.8") is False
    assert is_blocked_destination("1.1.1.1") is False
    assert is_blocked_destination("10.0.0.1") is False
    assert is_blocked_destination("192.168.1.100") is False
    assert is_blocked_destination("172.16.0.5") is False
    assert is_blocked_destination("example.com") is False


@pytest.mark.asyncio
async def test_gateway_imds_canonicalization_action_request():
    store = GraphStore(":memory:")
    await store.initialize()

    mock_registry = MagicMock()
    mock_tool = MagicMock()
    mock_tool.input = {"accepts": ["network.host"]}
    mock_registry.get_tool.return_value = {"manifest": mock_tool, "adapter": MagicMock()}

    gateway = ActionGateway(mock_registry, store)

    # Dotted-octal in raw_flags
    action_octal = ActionRequest(
        session_id=uuid4(),
        tool_name="nmap",
        params={"raw_flags": "0251.0376.0251.0376"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="strictly prohibited"):
        await gateway.validate_action(action_octal)

    # Dotted-hex in raw_flags
    action_hex = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://0xa9.0xfe.0xa9.0xfe/"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="strictly prohibited"):
        await gateway.validate_action(action_hex)

    # IPv4-mapped IPv6 in raw_flags
    action_mapped = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://[::ffff:169.254.169.254]/"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="strictly prohibited"):
        await gateway.validate_action(action_mapped)

    await store.close()


def test_adapter_flag_injection_prevention():
    from cyguide.schemas.web import WebEndpoint
    from tools.gobuster.adapter import GobusterAdapter
    from tools.nikto.adapter import NiktoAdapter
    from tools.subfinder.adapter import SubfinderAdapter

    # 1. Gobuster adapter with malicious URL containing spaces/flags
    gobuster = GobusterAdapter()
    malicious_url = "http://target.com/ -o /tmp/pwned.txt"
    target = WebEndpoint.create(url=malicious_url)
    cmd = gobuster.build_command(target, {"raw_flags": "dir -u {url} -w {wordlist}"})
    u_idx = cmd.index("-u")
    assert cmd[u_idx + 1] == malicious_url
    assert "-o" not in cmd

    # 2. Nikto adapter with malicious target containing flags
    nikto = NiktoAdapter()
    malicious_target = "10.0.0.1 -format htm"
    host_target = NetworkHost.create(ip=malicious_target)
    cmd_nikto = nikto.build_command(host_target, {"raw_flags": "-h {target} -p {port}"})
    h_idx = cmd_nikto.index("-h")
    assert cmd_nikto[h_idx + 1] == malicious_target
    assert "-format" not in cmd_nikto

    # 3. Subfinder adapter with malicious domain containing flags
    subfinder = SubfinderAdapter()
    malicious_domain = "example.com -o /tmp/evil"
    dummy_target = NetworkHost.create(ip="1.2.3.4")
    dummy_target.schema_type = "dns.record"
    dummy_target.pik = {"domain": malicious_domain}
    cmd_sub = subfinder.build_command(dummy_target, {"raw_flags": "-d {domain}"})
    d_idx = cmd_sub.index("-d")
    assert cmd_sub[d_idx + 1] == malicious_domain
    assert "-o" not in cmd_sub


@pytest.mark.asyncio
async def test_gateway_cidr_scope_enforcement(tmp_path):
    store = GraphStore(str(tmp_path / "cidr_scope.db"))
    await store.initialize()

    mock_registry = MagicMock()
    mock_tool = MagicMock()
    mock_tool.input = {"accepts": ["network.host"]}
    mock_registry.get_tool.return_value = {"manifest": mock_tool, "adapter": MagicMock()}

    # Gateway configured with authorized scope
    gateway = ActionGateway(mock_registry, store, allowed_cidrs=["10.0.0.0/8", "192.168.1.0/24"])

    # 1. In-scope action passes
    action_in_scope = ActionRequest(
        session_id=uuid4(),
        tool_name="nmap",
        params={"raw_flags": "-sV 10.50.1.20"},
        triggered_by=ActionSource.USER,
    )
    assert await gateway.validate_action(action_in_scope) is True

    # 2. Out-of-scope target in raw_flags raises ActionValidationError
    action_out_scope = ActionRequest(
        session_id=uuid4(),
        tool_name="nmap",
        params={"raw_flags": "-sV 172.16.0.5"},
        triggered_by=ActionSource.USER,
    )
    with pytest.raises(ActionValidationError, match="violates authorized engagement CIDR scope"):
        await gateway.validate_action(action_out_scope)

    # 3. Dynamic reconfiguration of scope
    gateway.set_allowed_cidrs(None)
    assert await gateway.validate_action(action_out_scope) is True

    await store.close()
