"""Unit tests for LearningSession and RecipeBinding deep modules."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from cyguide.engine.learning import (
    BriefingChunkEvent,
    BriefingCompletedEvent,
    BriefingStartedEvent,
    LearningSession,
    RecipeBinding,
    ScanCompletedEvent,
    ScanOutputChunkEvent,
    ScanStartedEvent,
)
from cyguide.engine.manifest import Manifest
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkService


def _create_sample_registry() -> ToolRegistry:
    registry = ToolRegistry()
    manifest_data = {
        "meta": {
            "name": "nmap",
            "description": "Network discovery and vulnerability scanner",
            "version": "7.93",
            "categories": ["portscanner"],
            "binary": "nmap",
            "one_line_summary": "Network exploration tool and security / port scanner.",
        },
        "modes": {"learning": True, "power": True},
        "learning": {
            "recipes": [
                {
                    "name": "Fast Top-100 Port Scan",
                    "description": "Scans the top 100 most common ports quickly without pinging.",
                    "flags": ["-F", "-Pn", "{target}"],
                },
                {
                    "name": "Full Version & Service Detection",
                    "description": "Probes open ports to determine service and version info.",
                    "flags": ["-sV", "-sC", "{target}"],
                },
            ]
        },
        "input": {"accepts": ["network.host"]},
        "output": {"produces": ["network.service", "network.host"]},
    }
    registry.tools["nmap"] = {"manifest": Manifest(**manifest_data), "adapter": None}
    return registry


def test_recipe_binding_resolution():
    registry = _create_sample_registry()
    manifest = registry.get_tool("nmap")["manifest"]

    # 1. Resolve selected recipe
    inv_recipe = RecipeBinding.resolve(
        manifest=manifest,
        target="192.168.1.1",
        recipe_idx=0,
    )
    assert inv_recipe.recipe_idx == 0
    assert "-F -Pn 192.168.1.1" in inv_recipe.cmd_str
    assert inv_recipe.target == "192.168.1.1"

    # 2. Resolve custom flags
    inv_custom = RecipeBinding.resolve(
        manifest=manifest,
        target="example.com",
        flags_used="-sS -p 80,443 {target}",
    )
    assert inv_custom.recipe_idx is None
    assert "-sS -p 80,443 example.com" in inv_custom.cmd_str

    # 3. Resolve matched recipe by flags
    inv_matched = RecipeBinding.resolve(
        manifest=manifest,
        target="10.0.0.1",
        selected_flags={"-F", "-Pn", "{target}"},
    )
    assert inv_matched.recipe_idx == 0


def test_learning_session_tool_selection():
    registry = _create_sample_registry()
    session = LearningSession(
        store=MagicMock(),
        registry=registry,
        execution=MagicMock(),
    )

    ctx = session.select_tool("nmap")
    assert ctx is not None
    assert ctx.name == "nmap"
    assert session.active_tool == "nmap"
    assert len(ctx.recipes) == 2
    assert "Quick Start Guide" in ctx.welcome_md


def test_learning_session_slash_commands():
    registry = _create_sample_registry()
    session = LearningSession(
        store=MagicMock(),
        registry=registry,
        execution=MagicMock(),
    )
    session.select_tool("nmap")

    # /help
    res_help = session.evaluate_slash_command("/help")
    assert res_help is not None
    assert res_help.handled is True
    assert "Commands" in res_help.message

    # /model
    res_model = session.evaluate_slash_command("/model")
    assert res_model is not None
    assert res_model.handled is True
    assert "nmap" in res_model.message

    # /recipes
    res_recipes = session.evaluate_slash_command("/recipes")
    assert res_recipes is not None
    assert res_recipes.handled is True
    assert "Fast Top-100 Port Scan" in res_recipes.message

    # /ai toggle
    assert session.ai_enabled is True
    res_ai_off = session.evaluate_slash_command("/ai off")
    assert res_ai_off.handled is True
    assert session.ai_enabled is False
    res_ai_on = session.evaluate_slash_command("/ai on")
    assert res_ai_on.handled is True
    assert session.ai_enabled is True

    # /summary
    res_sum = session.evaluate_slash_command("/summary")
    assert res_sum is not None
    assert res_sum.handled is False
    assert "educational summary" in res_sum.message

    # /flags
    res_flags = session.evaluate_slash_command("/flags", active_flags_str="-sV -p 80")
    assert res_flags is not None
    assert res_flags.handled is False
    assert "-sV -p 80" in res_flags.message

    # /clear, /copy, /quit
    assert session.evaluate_slash_command("/clear").action == "clear"
    assert session.evaluate_slash_command("/copy").action == "copy"
    assert session.evaluate_slash_command("/quit").action == "exit"

    # Unknown command
    res_unk = session.evaluate_slash_command("/bogus")
    assert res_unk.handled is True
    assert "Unknown command: `/bogus`" in res_unk.message


@pytest.mark.asyncio
async def test_learning_session_run_scan_lifecycle():
    registry = _create_sample_registry()
    mock_execution = MagicMock()
    job_id = uuid4()
    mock_execution.dispatch = AsyncMock(return_value=job_id)
    mock_execution.get_running_task = MagicMock(return_value=None)

    mock_explainer = MagicMock()

    async def _mock_briefing(*args, **kwargs):
        yield "## Briefing Analysis\n"
        yield "Target scanned successfully."

    mock_explainer.generate_scan_briefing = _mock_briefing

    session = LearningSession(
        store=MagicMock(),
        registry=registry,
        execution=mock_execution,
        explainer=mock_explainer,
    )
    session.select_tool("nmap")

    events = []
    chunks = []
    async for event in session.run_scan(
        target="127.0.0.1",
        flags_used="-F",
        on_raw_chunk=lambda chunk: chunks.append(chunk),
    ):
        events.append(event)

    assert any(isinstance(e, ScanStartedEvent) for e in events)
    assert any(isinstance(e, ScanCompletedEvent) for e in events)
    assert any(isinstance(e, BriefingStartedEvent) for e in events)
    assert any(isinstance(e, BriefingChunkEvent) for e in events)
    assert any(isinstance(e, BriefingCompletedEvent) for e in events)
    assert session.run_count == 1
    assert session.scan_in_progress is False


@pytest.mark.asyncio
async def test_learning_session_extract_structured_findings():
    store = GraphStore(":memory:")
    await store.initialize()
    _, session_id = await store.get_or_create_learning_sandbox()

    svc = NetworkService.create(
        host_ip="10.10.10.10",
        port=443,
        protocol="tcp",
        service_name="https",
    )
    await store.upsert_finding(session_id, svc)

    session = LearningSession(
        store=store,
        registry=ToolRegistry(),
        execution=MagicMock(),
        session_id=session_id,
    )

    ui_text, llm_text = await session.extract_structured_findings()
    assert "443/tcp" in ui_text
    assert "https" in ui_text
    assert "443/tcp" in llm_text

    await store.close()


@pytest.mark.asyncio
async def test_stream_tutor_response():
    mock_explainer = MagicMock()

    async def _mock_explain_scan(*args, **kwargs):
        yield "First chunk "
        yield "second chunk "
        yield "third chunk."

    mock_explainer.explain_scan = _mock_explain_scan

    session = LearningSession(
        store=MagicMock(),
        registry=MagicMock(),
        execution=MagicMock(),
        explainer=mock_explainer,
    )

    chunks = []
    async for item in session.stream_tutor_response("How does nmap work?", update_interval=0.0):
        chunks.append(item)

    assert len(chunks) >= 3
    assert "First chunk" in chunks[0].accumulated
    assert "third chunk." in chunks[-1].accumulated
    assert chunks[-1].is_error is False

    # Test fallback when explainer is None
    session_no_ai = LearningSession(
        store=MagicMock(),
        registry=MagicMock(),
        execution=MagicMock(),
        explainer=None,
    )
    fallback_chunks = [c async for c in session_no_ai.stream_tutor_response("Hi")]
    assert len(fallback_chunks) == 1
    assert fallback_chunks[0].is_fallback is True
    assert "CyGuide cybersecurity tutor" in fallback_chunks[0].accumulated


@pytest.mark.asyncio
async def test_learning_session_get_database_targets():
    from cyguide.schemas.dns import DomainInfo
    from cyguide.schemas.network import NetworkHost
    from cyguide.schemas.web import WebEndpoint

    store = GraphStore(":memory:")
    await store.initialize()
    _, session_id = await store.get_or_create_learning_sandbox()

    # Insert host, domain, and web endpoint
    host = NetworkHost.create(ip="192.168.1.100", hostname="gateway.local")
    domain = DomainInfo.create(domain="target.corp")
    endpoint = WebEndpoint.create(url="https://target.corp/api", host_ip="192.168.1.100")

    await store.upsert_finding(session_id, host)
    await store.upsert_finding(session_id, domain)
    await store.upsert_finding(session_id, endpoint)

    session = LearningSession(
        store=store,
        registry=ToolRegistry(),
        execution=MagicMock(),
        session_id=session_id,
    )

    targets = await session.get_database_targets()
    assert "192.168.1.100" in targets
    assert "target.corp" in targets
    assert "https://target.corp/api" in targets

    await store.close()


@pytest.mark.asyncio
async def test_learning_session_sweep_targets():
    registry = _create_sample_registry()
    session = LearningSession(
        store=MagicMock(),
        registry=registry,
        execution=MagicMock(),
    )
    session.select_tool("nmap")

    swept_targets = []

    async def _mock_run_scan(target, **kwargs):
        swept_targets.append(target)
        yield ScanStartedEvent(
            cmd_str=f"nmap {target}", run_count=len(swept_targets), timestamp="now"
        )
        yield ScanCompletedEvent(duration_seconds=1.2, footer_text="done")

    session.run_scan = _mock_run_scan

    targets = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    events = [e async for e in session.sweep_targets(targets=targets, flags_used="-F")]

    assert swept_targets == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    assert len([e for e in events if isinstance(e, ScanStartedEvent)]) == 3


@pytest.mark.asyncio
async def test_learning_session_execution_event_stream():
    """Verify that execute/run_scan yields typed events and streams output chunks directly."""
    store = GraphStore(":memory:")
    await store.initialize()
    reg = ToolRegistry()
    reg.load_tools()

    session = LearningSession(store=store, registry=reg, execution=None)
    session.active_tool = "whois"

    # Execution with simulated runner (no ExecutionSession)
    events = []
    async for event in session.execute(
        target="example.com",
        flags_used="",
        skip_preflight=True,
    ):
        events.append(event)

    types = [type(e) for e in events]
    assert ScanStartedEvent in types
    assert ScanOutputChunkEvent in types
    assert ScanCompletedEvent in types

    start_ev = next(e for e in events if isinstance(e, ScanStartedEvent))
    assert start_ev.run_count == 1
    assert "whois example.com" in start_ev.cmd_str

    chunk_ev = next(e for e in events if isinstance(e, ScanOutputChunkEvent))
    assert "Simulated execution for whois" in chunk_ev.chunk

    assert session.primary_target == "example.com"
    assert "whois" in session.tools_used
    assert session.tool_configs["whois"]["target"] == "example.com"

    await store.close()
