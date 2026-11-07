import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cyguide.engine.executor import sanitize_subprocess_env
from cyguide.engine.gateway import ActionGateway, ActionValidationError
from cyguide.engine.reporter import build_markdown_table_for_type
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.schemas.web import WebEndpoint
from tools.gobuster.adapter import GobusterAdapter
from tools.nikto.adapter import NiktoAdapter
from tools.subfinder.adapter import SubfinderAdapter


def test_sanitize_subprocess_env():
    raw_env = {
        "PATH": "/usr/bin:/bin",
        "USER": "analyst",
        "CYGUIDE_API_KEY": "secret_key_123",
        "CYGUIDE_API_BASE": "https://api.openai.com",
        "GROQ_API_KEY": "gsk_test123",
        "OPENAI_API_KEY": "sk-test456",
        "ANTHROPIC_API_KEY": "ant-test789",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "GITHUB_TOKEN": "ghp_token",
    }
    cleaned = sanitize_subprocess_env(raw_env)
    assert cleaned["PATH"] == "/usr/bin:/bin"
    assert cleaned["USER"] == "analyst"
    assert "CYGUIDE_API_KEY" not in cleaned
    assert "CYGUIDE_API_BASE" not in cleaned
    assert "GROQ_API_KEY" not in cleaned
    assert "OPENAI_API_KEY" not in cleaned
    assert "ANTHROPIC_API_KEY" not in cleaned
    assert "AWS_SECRET_ACCESS_KEY" not in cleaned
    assert "GITHUB_TOKEN" not in cleaned


def test_adapter_flag_injection_prevention():
    # 1. Gobuster adapter with malicious URL containing spaces/flags
    gobuster = GobusterAdapter()
    malicious_url = "http://target.com/ -o /tmp/pwned.txt"
    target = WebEndpoint.create(url=malicious_url)
    cmd = gobuster.build_command(target, {"raw_flags": "dir -u {url} -w {wordlist}"})

    # -u should be followed by the single URL argument, NOT separate flags
    u_idx = cmd.index("-u")
    assert cmd[u_idx + 1] == malicious_url
    assert "-o" not in cmd  # -o must not be parsed as a separate argument

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
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_flag)

    # 2. Blocked via tool_name
    action_name = ActionRequest(
        session_id=uuid4(),
        tool_name="curl 169.254.169.254",
        is_explicit_shell=True,
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_name)

    # 3. Blocked via Google metadata domain
    action_gcp = ActionRequest(
        session_id=uuid4(),
        tool_name="curl metadata.google.internal",
        is_explicit_shell=True,
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_gcp)

    await store.close()


def test_reporter_html_escaping():
    nodes = [{
        "id": "abc123456789",
        "schema_type": "web.endpoint",
        "pik_json": '{"url": "<script>alert(1)</script>"}',
        "data_json": '{"title": "<b>Dashboard</b>"}',
        "status": "confirmed"
    }]
    lines = build_markdown_table_for_type("web.endpoint", nodes)
    report_text = "\n".join(lines)
    assert "<script>" not in report_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in report_text
    assert "<b>" not in report_text
    assert "&lt;b&gt;Dashboard&lt;/b&gt;" in report_text


@pytest.mark.asyncio
async def test_store_trusted_schema_and_permissions(tmp_path):
    db_file = str(tmp_path / "test_store.db")
    store = GraphStore(db_file)
    await store.initialize()

    # Check trusted_schema PRAGMA
    async with store._get_conn() as db:
        cursor = await db.execute("PRAGMA trusted_schema")
        row = await cursor.fetchone()
        assert row[0] == 0  # OFF

    # Check file permissions on DB
    mode = oct(os.stat(db_file).st_mode)[-3:]
    assert mode == "600"

    await store.close()


def test_sanitize_subprocess_env_extended():
    raw_env = {
        "PATH": "/usr/bin:/bin",
        "DEEPSEEK_API_KEY": "sk-deepseek",
        "PERPLEXITY_API_KEY": "pplx-secret",
        "PPLX_TOKEN": "token123",
        "HUGGINGFACE_TOKEN": "hf_abc",
        "HF_TOKEN": "hf_xyz",
        "VAULT_TOKEN": "s.vaulttoken",
        "SSH_PRIVATE_KEY": "-----BEGIN OPENSSH PRIVATE KEY-----",
    }
    cleaned = sanitize_subprocess_env(raw_env)
    assert cleaned["PATH"] == "/usr/bin:/bin"
    assert "DEEPSEEK_API_KEY" not in cleaned
    assert "PERPLEXITY_API_KEY" not in cleaned
    assert "PPLX_TOKEN" not in cleaned
    assert "HUGGINGFACE_TOKEN" not in cleaned
    assert "HF_TOKEN" not in cleaned
    assert "VAULT_TOKEN" not in cleaned
    assert "SSH_PRIVATE_KEY" not in cleaned


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
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_azure)

    # 2. AWS IPv6 metadata
    action_ipv6 = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://[fd00:ec2::254]/latest/meta-data/"},
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_ipv6)

    # 3. Decimal IP notation
    action_dec = ActionRequest(
        session_id=uuid4(),
        tool_name="curl",
        params={"raw_flags": "http://2852039166/"},
        triggered_by=ActionSource.USER
    )
    with pytest.raises(ActionValidationError, match="Access to cloud metadata endpoints is strictly prohibited"):
        await gateway.validate_action(action_dec)

    await store.close()


@pytest.mark.asyncio
async def test_reporter_backtick_command_escaping():
    from cyguide.engine.reporter import generate_markdown_report
    from cyguide.schemas.power import ActionRequest, ActionSource
    store = GraphStore(":memory:")
    await store.initialize()

    ws_id = await store.create_workspace("Test WS")
    sess_id = await store.create_session(ws_id, "Test Sess")

    action = ActionRequest(
        session_id=uuid4(),
        tool_name="!echo",
        params={"raw_flags": "`whoami`"},
        triggered_by=ActionSource.USER,
        is_explicit_shell=True
    )
    await store.append_event(
        sess_id,
        action,
        {"output": "root\n"},
        "Ran echo"
    )

    report = await generate_markdown_report(store, sess_id)
    assert "`` !echo `whoami` ``" in report
    await store.close()


def test_gateway_imds_canonicalization_direct():
    from cyguide.engine.gateway import is_blocked_destination

    # Obfuscated and standard representations of 169.254.169.254
    assert is_blocked_destination("169.254.169.254") is True
    assert is_blocked_destination("0251.0376.0251.0376") is True
    assert is_blocked_destination("0xa9.0xfe.0xa9.0xfe") is True
    assert is_blocked_destination("2852039166") is True
    assert is_blocked_destination("::ffff:169.254.169.254") is True
    assert is_blocked_destination("::ffff:a9fe:a9fe") is True

    # Cloud metadata IPv6 / Link-local
    assert is_blocked_destination("fd00:ec2::254") is True
    assert is_blocked_destination("fe80::1") is True
    assert is_blocked_destination("metadata.google.internal") is True

    # Legitimate non-metadata IPs & networks should NOT be blocked
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


@pytest.mark.asyncio
async def test_cli_report_atomic_permissions(tmp_path):
    import asyncio
    import io
    import sys
    from unittest.mock import patch

    from cyguide.main import main

    db_path = tmp_path / "test.db"
    store = GraphStore(str(db_path))
    await store.initialize()
    _ws_id, sess_id = await store.get_or_create_learning_sandbox()
    await store.close()

    export_db = tmp_path / "exported.db"
    report_file = tmp_path / "export_report.md"

    def _run_cli(args_list):
        old_stdout = sys.stdout
        captured = io.StringIO()
        try:
            sys.stdout = captured
            with patch.object(sys, "argv", args_list):
                main()
        except SystemExit:
            pass
        finally:
            sys.stdout = old_stdout
        return captured.getvalue()

    # Even with loose ambient umask 0o000, atomic descriptor creation enforces 0o600
    old_umask = os.umask(0o000)
    try:
        args_list = [
            "cyg",
            "--db", str(db_path),
            "export",
            str(sess_id),
            str(export_db),
            "--report", str(report_file),
        ]
        await asyncio.to_thread(_run_cli, args_list)
    finally:
        os.umask(old_umask)

    assert report_file.exists()
    st_mode = os.stat(report_file).st_mode & 0o777
    assert oct(st_mode) == "0o600"


def test_ui_markup_escaping():
    from rich.errors import MarkupError
    from rich.markup import escape
    from rich.text import Text

    # Strings with unmatched closing tags that cause rich MarkupError if interpolated unescaped
    crashing_inputs = [
        "Unmatched closing tag [/red] in compiler output",
        "Multiple tags [/bold][/italic][/blink]",
        "Syntax error: <module> [/unknown_tag]",
        "Arbitrary [/] root close tag",
        "nested [/foo][bar][/bar]",
    ]

    for raw in crashing_inputs:
        # Unescaped interpolation raises MarkupError
        with pytest.raises(MarkupError):
            Text.from_markup(f"[bold #f85149]Error:[/] [red]{raw}[/]")

    # All inputs, including non-crashing arbitrary markup, render cleanly when escaped
    all_inputs = crashing_inputs + [
        "[bold]Open tag without close",
        "[link=http://evil.com]clickme[/link]",
        "[#ff0000]custom color[/#ff0000]",
    ]
    for raw in all_inputs:
        escaped_text = Text.from_markup(f"[bold #f85149]Error:[/] [red]{escape(raw)}[/]")
        assert escaped_text is not None
        assert raw in escaped_text.plain
