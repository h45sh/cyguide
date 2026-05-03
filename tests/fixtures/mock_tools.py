from typing import Dict, Any, AsyncIterator, List
from cyguide.engine.adapter import ToolAdapter
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.network import NetworkService, NetworkHost

class MockNmapAdapter(ToolAdapter):
    """Mocks nmap adapter behavior."""
    def validate_install(self) -> bool:
        return True

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        return ["echo", "service: 80/tcp open http"]

    async def parse_output(self, raw_stdout: str, target: BaseFinding) -> AsyncIterator[BaseFinding]:
        if "80/tcp open" in raw_stdout:
            yield NetworkService.create(
                host_ip=target.pik.get("ip", "unknown"),
                port=80,
                protocol="tcp",
                service_name="http"
            )

class MockSimpleAdapter(ToolAdapter):
    """Mocks a simple adapter behavior."""
    def validate_install(self) -> bool:
        return True

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        return ["echo", "hostname: " + params.get("hostname", "unknown")]

    async def parse_output(self, raw_stdout: str, target: BaseFinding) -> AsyncIterator[BaseFinding]:
        if "hostname: " in raw_stdout:
            hostname = raw_stdout.split("hostname: ")[1].strip()
            yield NetworkHost.create(ip="8.8.8.8", hostname=hostname)
