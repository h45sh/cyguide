# PROTECTED FILE — See CONTRIBUTING.md before modifying.
# Changes to this file require team agreement.
"""Dynamic tool discovery and loading."""

import os
import importlib.util
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Type

from cyguide.engine.manifest import Manifest
from cyguide.engine.adapter import ToolAdapter


class ToolRegistry:
    """Discovers and loads tool plugins from the tools/ directory."""

    def __init__(self, tools_dir: Optional[str] = None):
        if tools_dir is None:
            # Anchor to the project root (parent of the cyguide/ package)
            # cyguide/engine/registry.py -> engine -> cyguide -> project_root
            project_root = Path(__file__).parent.parent.parent
            self.tools_dir = project_root / "tools"
        else:
            self.tools_dir = Path(tools_dir)
            
        self.tools: Dict[str, Dict] = {}
        self.load_errors: Dict[str, str] = {}

    def load_tools(self):
        """Scan the tools directory and load all valid plugins."""
        self.tools = {}
        self.load_errors = {}
        
        if not self.tools_dir.exists():
            return

        for tool_path in self.tools_dir.iterdir():
            if tool_path.is_dir():
                manifest_path = tool_path / "manifest.toml"
                adapter_path = tool_path / "adapter.py"

                if manifest_path.exists() and adapter_path.exists():
                    try:
                        # 1. Load and validate manifest
                        with open(manifest_path, "rb") as f:
                            data = tomllib.load(f)
                            manifest = Manifest(**data)

                        # 2. Dynamically load the adapter class
                        adapter_instance = self._load_adapter(adapter_path)
                        
                        if adapter_instance:
                            self.tools[manifest.meta.name] = {
                                "manifest": manifest,
                                "adapter": adapter_instance,
                                "path": tool_path
                            }
                        else:
                             self.load_errors[tool_path.name] = "No ToolAdapter subclass found in adapter.py"
                    except Exception as e:
                        self.load_errors[tool_path.name] = str(e)

    def _load_adapter(self, adapter_path: Path) -> Optional[ToolAdapter]:
        """Import the adapter.py module and instantiate the ToolAdapter class."""
        try:
            module_name = f"tools.{adapter_path.parent.name}.adapter"
            spec = importlib.util.spec_from_file_location(module_name, adapter_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for a subclass of ToolAdapter
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ToolAdapter) and 
                        attr is not ToolAdapter):
                        return attr()
            return None
        except Exception as e:
            # Re-raise to let load_tools capture the full context
            raise e

    def get_tool(self, name: str) -> Optional[Dict]:
        """Return the manifest and adapter instance for a named tool."""
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """Return a list of loaded tool names."""
        return list(self.tools.keys())

    def find_tools_for_input(self, schema_type: str) -> List[str]:
        """Find all tools that accept a specific finding type as input."""
        matching = []
        for name, data in self.tools.items():
            if schema_type in data["manifest"].input.get("accepts", []):
                matching.append(name)
        return matching
