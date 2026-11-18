"""Universal adapter parser fuzzing test suite (Syzkaller-inspired).

Enforces crash-resilience across ALL registered security tool adapters in tools/:
1. Dynamic Discovery: Automatically discovers all tool plugins via ToolRegistry.
2. Crash Resilience Invariant:
   - parse_output() must NEVER raise an uncaught exception on malformed stdout/stderr.
   - parse_output() must either yield valid BaseFinding instances or cleanly drop input.
3. Sanitization Invariant:
   - sanitize_output() must NEVER raise an uncaught exception on hostile streams.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.fuzz

from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.dns import DnsRecord
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.web import WebEndpoint
from tests.fixtures.fuzz_streams import generate_fuzz_streams


def _build_dummy_target(accepts_list: list[str]) -> BaseFinding:
    """Create a minimal valid target finding matching the tool manifest's accepts schema."""
    for schema in accepts_list:
        if schema == "network.host":
            return NetworkHost.create(ip="10.0.0.1", hostname="target.local")
        elif schema == "network.service":
            return NetworkService.create(
                host_ip="10.0.0.1", port=80, protocol="tcp", service_name="http"
            )
        elif schema == "web.endpoint":
            return WebEndpoint.create(url="http://10.0.0.1:80/api")
        elif schema == "dns.record":
            return DnsRecord.create(domain="target.local", record_type="A", value="10.0.0.1")

    # Default fallback
    return NetworkHost.create(ip="10.0.0.1", hostname="target.local")


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REGISTRY = ToolRegistry(str(REPO_ROOT / "tools"))
REGISTRY.load_tools()
LOADED_TOOLS = sorted(list(REGISTRY.tools.items()), key=lambda x: x[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name, tool_data", LOADED_TOOLS)
async def test_all_adapters_fuzz_stream_resilience(tool_name, tool_data):
    """Crash-Resilience Invariant: Adapter parsers must never raise unhandled exceptions on hostile streams."""
    adapter = tool_data["adapter"]
    manifest = tool_data["manifest"]

    # Contract Invariant: validate_install() must return a boolean without throwing
    assert isinstance(adapter.validate_install(), bool)

    input_cfg = manifest.input if manifest else None
    if isinstance(input_cfg, dict):
        accepts = input_cfg.get("accepts", ["network.host"])
    else:
        accepts = getattr(input_cfg, "accepts", ["network.host"]) if input_cfg else ["network.host"]
    target = _build_dummy_target(accepts)

    store = GraphStore(":memory:")
    fuzz_samples = generate_fuzz_streams()

    for sample in fuzz_samples:
        # 1. Output Sanitization must never crash
        sanitized = adapter.sanitize_output(sample)
        assert isinstance(sanitized, str)

        # 2. Output Parser must never crash and must yield valid BaseFindings
        context = {}
        try:
            async for finding in adapter.parse_output(sample, target, context):
                assert isinstance(finding, BaseFinding)
                assert finding.schema_type is not None
                assert isinstance(finding.pik, dict)
                # Ensure finding produces a valid deterministic node ID
                node_id = store.generate_node_id(finding.schema_type, finding.pik)
                assert isinstance(node_id, str) and len(node_id) == 64
        except Exception as e:
            pytest.fail(
                f"Tool adapter '{tool_name}' crashed during fuzzing on input {sample!r}: {e}"
            )


@pytest.mark.parametrize("tool_name, tool_data", LOADED_TOOLS)
def test_all_adapters_build_command_invariants(tool_name, tool_data):
    """Safety Invariant: build_command must always return a list[str] of discrete arguments."""
    adapter = tool_data["adapter"]
    manifest = tool_data["manifest"]
    input_cfg = manifest.input if manifest else None
    accepts = (
        input_cfg.get("accepts", ["network.host"])
        if isinstance(input_cfg, dict)
        else getattr(input_cfg, "accepts", ["network.host"])
    )
    target = _build_dummy_target(accepts)

    adversarial_params = [
        {},
        {"raw_flags": ""},
        {"raw_flags": "   "},
        {"raw_flags": "-p 80,443 -v --script 'default,vuln'"},
        {"raw_flags": "; rm -rf /; echo $(id) && whoami | grep root"},
        {"raw_flags": "null\x00byte\x00injection"},
        {"raw_flags": "-H 'Authorization: Bearer test' -u 'https://example.com?id=1'"},
        {"raw_flags": "A" * 5000},
    ]

    for params in adversarial_params:
        cmd = adapter.build_command(target, params)
        assert isinstance(cmd, list), f"{tool_name}.build_command must return a list"
        assert len(cmd) > 0, f"{tool_name}.build_command returned empty list"
        for arg in cmd:
            assert isinstance(arg, str), f"Command argument in {tool_name} is not str: {arg!r}"

