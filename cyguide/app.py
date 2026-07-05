"""Main CyGuide TUI Application."""

import os
from textual.app import App, SystemCommand
from cyguide.ui.screens.home import DashboardScreen
from cyguide.ui.screens.learning import LearningModeScreen
from cyguide.ui.screens.tool_browser import ToolBrowserScreen
from cyguide.ui.screens.power import PowerModeScreen

from typing import Optional, Dict, Any, List
import subprocess

from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.engine.executor import Executor
from cyguide.engine.explainer import LearningExplainer, TemplateBackend, OllamaBackend
from cyguide.modes.learning import LearningModeEngine
from cyguide.modes.power import PowerModeEngine
from cyguide.engine.power_facade import PowerWorkspaceFacade

class CyGuideApp(App):
    """The central orchestrator for the CyGuide TUI."""
    
    CSS_PATH = "ui/style.css"
    TITLE = "CyGuide"
    
    # Register screens so they can be switched by name
    SCREENS = {
        "dashboard": DashboardScreen,
        "tool_browser": ToolBrowserScreen,
        "learning_mode": LearningModeScreen,
        "power_mode": PowerModeScreen,
    }

    def __init__(self, db_path: str = "data/cyguide.db", use_ollama: bool = False, ollama_model: str = "gemma", tools_dir: str = None, **kwargs):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.use_ollama = use_ollama
        self.ollama_model = ollama_model
        self.tools_dir = tools_dir
        self.selected_session_id: Optional[str] = None
        self.selected_workspace_id: Optional[str] = None
        self.user_env: Dict[str, str] = os.environ.copy()
        self.user_shell: str = "/bin/bash"
        # Ensure the directory for the database exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)

    def detect_user_shell(self) -> str:
        """Find the user's default shell."""
        return os.environ.get("SHELL", "/bin/bash")

    def get_shell_environment(self) -> Dict[str, str]:
        """Capture the full login shell environment."""
        shell = self.detect_user_shell()
        try:
            # Run a login shell to capture the fully resolved environment
            result = subprocess.run(
                [shell, "-l", "-c", "env"],
                capture_output=True, text=True, timeout=5
            )
            env = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    key, _, val = line.partition("=")
                    env[key] = val
            return env if env else os.environ.copy()
        except Exception:
            return os.environ.copy()

    async def on_mount(self) -> None:
        """Initialize the app with core components and the dashboard."""
        self.user_shell = self.detect_user_shell()
        self.user_env = self.get_shell_environment()
        
        self.learning_mode_tool = "nmap" # Default
        # 1. Initialize Engines
        self.registry = ToolRegistry(tools_dir=self.tools_dir)
        self.registry.load_tools()
        
        self.store = GraphStore(self.db_path)
        await self.store.initialize()
        
        # Ensure singleton Learning Sandbox exists
        self.learning_ws_id, self.learning_session_id = await self.store.get_or_create_learning_sandbox()

        self.executor = Executor(self.store)
        
        # Setup Explainer
        if self.use_ollama:
            self.explainer_backend = OllamaBackend(model=self.ollama_model)
        else:
            self.explainer_backend = TemplateBackend()
            
        self.explainer = LearningExplainer(self.explainer_backend)
        
        self.learning_engine = LearningModeEngine(self.registry, self.executor, self.explainer)
        self.power_engine = PowerModeEngine(self.registry, self.executor)
        self.power_facade = PowerWorkspaceFacade(self.store, self.executor, self.registry)
        self.power_facade.user_env = self.user_env
        self.power_facade.user_shell = self.user_shell

        # 2. Setup UI
        self.push_screen("dashboard")
        self.animations_enabled = True

    async def on_unmount(self) -> None:
        """Cleanup resources before exit."""
        if hasattr(self, "executor"):
            await self.executor.shutdown()
        if hasattr(self, "store"):
            await self.store.close()

    def action_toggle_animations(self) -> None:
        """Toggle UI animations on or off via the command palette."""
        self.animations_enabled = not self.animations_enabled
        if self.animations_enabled:
            self.remove_class("no-animations")
            self.notify("Animations Enabled")
        else:
            self.add_class("no-animations")
            self.notify("Animations Disabled")

    def get_system_commands(self, screen):
        """Add custom commands to the Command Palette (Ctrl+P)."""
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Toggle Animations", 
            "Turn sidebar animations on or off", 
            self.action_toggle_animations
        )

if __name__ == "__main__":
    app = CyGuideApp()
    app.run()
