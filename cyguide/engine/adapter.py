"""Abstract base class for all tool plugins."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any
from cyguide.schemas.base import BaseFinding


class ToolAdapter(ABC):
    """
    Contract for tool contributors. 
    Every tool in tools/ must implement this in adapter.py.
    """

    @abstractmethod
    def validate_install(self) -> bool:
        """Check if the tool binary is available on the system."""
        pass

    @abstractmethod
    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """
        Build the command line arguments for the tool.
        
        Args:
            target: The finding being scanned (e.g. a network.host)
            params: User-provided flags or options from the TUI
        """
        pass

    @abstractmethod
    async def parse_output(self, raw_stdout: str, target: BaseFinding) -> AsyncIterator[BaseFinding]:
        """
        Parse tool output and yield standardized findings.
        
        Args:
            raw_stdout: The raw output string from the tool
            target: The original target finding (for context/parenting)
        """
        pass
