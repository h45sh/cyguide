"""CLI runtime execution context and resource lifecycle management."""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.engine.workspace_repository import WorkspaceRepository
from cyguide.paths import get_default_data_dir, get_default_db_path

# Standardized POSIX exit codes for CyGuide CLI
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_MISSING_DEP = 127


@dataclass(frozen=True)
class CliContext:
    """Encapsulates global options and paths resolved from CLI invocation."""

    data_dir: str
    db_path: str
    tools_dir: Optional[str]
    is_json: bool
    verbose: bool
    offline: bool
    use_ollama: bool
    ollama_model: str

    @classmethod
    def from_args(cls, args) -> "CliContext":
        """Resolve CLI arguments into an immutable runtime context."""
        data_dir_arg = getattr(args, "data_dir", None)
        db_arg = getattr(args, "db", None)
        tools_arg = getattr(args, "tools", None)

        data_dir = data_dir_arg or get_default_data_dir()
        db_path = db_arg or get_default_db_path(data_dir)

        is_json = bool(getattr(args, "json", False))
        verbose = bool(getattr(args, "verbose", False))

        if getattr(args, "no_ai", False):
            os.environ["CYGUIDE_OFFLINE"] = "1"
            os.environ["CYGUIDE_NO_AI"] = "1"
            offline = True
            use_ollama = False
        else:
            offline = False
            use_ollama = bool(getattr(args, "ollama", False))

        selected_model = (
            getattr(args, "model_alias", None) or getattr(args, "ollama_model", None) or "gemma"
        )

        return cls(
            data_dir=data_dir,
            db_path=db_path,
            tools_dir=tools_arg,
            is_json=is_json,
            verbose=verbose,
            offline=offline,
            use_ollama=use_ollama,
            ollama_model=selected_model,
        )

    @asynccontextmanager
    async def open_store(self) -> AsyncIterator[GraphStore]:
        """Context manager guaranteeing initialized GraphStore and clean teardown."""
        store = GraphStore(self.db_path)
        await store.initialize()
        try:
            yield store
        finally:
            await store.close()

    @asynccontextmanager
    async def open_workspace_repo(
        self,
    ) -> AsyncIterator[tuple[GraphStore, WorkspaceRepository]]:
        """Context manager yielding initialized store and WorkspaceRepository."""
        async with self.open_store() as store:
            repo = WorkspaceRepository(store=store)
            yield store, repo

    def get_tool_registry(self) -> ToolRegistry:
        """Create and load the tool plugin registry."""
        registry = ToolRegistry(tools_dir=self.tools_dir)
        registry.load_tools()
        return registry
