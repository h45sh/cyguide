import pytest

from cyguide.engine.executor import Executor
from cyguide.schemas.network import NetworkHost
from tests.fixtures.mock_tools import MockNmapAdapter


@pytest.mark.asyncio
async def test_executor_run_tool():
    executor = Executor()
    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockNmapAdapter()

    findings = []
    async for f in executor.run_tool(adapter, target, {}):
        findings.append(f)

    assert len(findings) == 1
    assert findings[0].schema_type == "network.service"
    assert findings[0].pik["host_ip"] == "127.0.0.1"


class MockHangingAdapter(MockNmapAdapter):
    def build_command(self, target, params):
        return ["sleep", "5"]

    async def parse_output(self, raw_stdout, target, context=None):
        if False:
            yield


@pytest.mark.asyncio
async def test_executor_timeout():
    executor = Executor()
    target = NetworkHost.create(ip="127.0.0.1")
    adapter = MockHangingAdapter()

    output_lines = []
    async def record_output(text):
        output_lines.append(text)

    with pytest.raises(TimeoutError):
        async for _ in executor.run_tool(
            adapter, target, {},
            timeout_seconds=0.2,
            on_output=record_output
        ):
            pass

    assert any("TIMEOUT" in line for line in output_lines)
