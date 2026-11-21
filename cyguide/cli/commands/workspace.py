"""Workspace management CLI command handler."""

from typing import Any, Optional

from cyguide.cli.context import (
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    CliContext,
)
from cyguide.cli.formatters import (
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)
from cyguide.engine.workspace_repository import WorkspaceRepository


async def _resolve_workspace(identifier: str, repo: WorkspaceRepository) -> Optional[dict]:
    """Resolve a workspace by its UUID or human-readable name."""
    ws = await repo.get_workspace(identifier)
    if ws:
        return ws
    workspaces = await repo.list_workspaces()
    for w in workspaces:
        if w.get("name", "").strip().lower() == identifier.strip().lower():
            return w
        elif str(w.get("id", "")).startswith(identifier):
            return w
    return None


async def handle_workspace(args: Any, context: CliContext) -> int:
    """Route workspace subcommands."""
    subaction = getattr(args, "workspace_action", None)
    if not subaction:
        return EXIT_USAGE_ERROR

    if subaction == "list":
        return await _workspace_list(args, context)
    elif subaction == "create":
        return await _workspace_create(args, context)
    elif subaction == "delete":
        return await _workspace_delete(args, context)
    else:
        print_error(f"Unknown workspace action: {subaction}")
        return EXIT_USAGE_ERROR


async def _workspace_list(args: Any, context: CliContext) -> int:
    """List engagement workspaces with human-readable names and session counts."""
    async with context.open_workspace_repo() as (store, repo):
        workspaces = await repo.list_workspaces()

        if context.is_json:
            print_json(workspaces)
            return EXIT_SUCCESS

        if not workspaces:
            print_info("No workspaces found.")
            return EXIT_SUCCESS

        rows = []
        for ws in workspaces:
            sessions = await repo.list_sessions(ws["id"])
            created_str = str(ws.get("created_at", ""))[:19].replace("T", " ")
            rows.append(
                [
                    str(ws.get("name", "Unnamed Workspace")),
                    str(ws.get("status", "ACTIVE")),
                    str(len(sessions)),
                    created_str,
                    str(ws.get("id", ""))[:8] + "...",
                ]
            )

        print_table(
            title="Engagement Workspaces",
            columns=[
                ("Workspace Name", "bold white"),
                ("Status", "green"),
                ("Sessions", "yellow"),
                ("Created", "dim"),
                ("ID", "dim"),
            ],
            rows=rows,
        )
        return EXIT_SUCCESS


async def _workspace_create(args: Any, context: CliContext) -> int:
    """Create a new workspace."""
    name = args.name.strip()
    if not name:
        print_error("Workspace name cannot be empty.")
        return EXIT_USAGE_ERROR

    async with context.open_workspace_repo() as (store, repo):
        try:
            ws_id = await repo.create_workspace(name)
            if context.is_json:
                print_json({"id": ws_id, "name": name, "status": "ACTIVE"})
            else:
                print_success(f"Workspace '{name}' created successfully (ID: {ws_id[:8]})")
            return EXIT_SUCCESS
        except ValueError as ve:
            print_error(f"Cannot create workspace: {ve}")
            return EXIT_USAGE_ERROR
        except Exception as e:
            print_error(f"Failed to create workspace: {e!s}")
            return EXIT_RUNTIME_ERROR


async def _workspace_delete(args: Any, context: CliContext) -> int:
    """Delete a workspace (resolving by name or ID)."""
    raw_ident = args.workspace_id

    async with context.open_workspace_repo() as (store, repo):
        ws = await _resolve_workspace(raw_ident, repo)
        if not ws:
            print_error(f"Workspace not found: {raw_ident}")
            return EXIT_RUNTIME_ERROR

        if ws.get("status") == "SYSTEM":
            print_error(f"Cannot delete protected system workspace '{ws.get('name')}'.")
            return EXIT_USAGE_ERROR

        workspace_id = ws["id"]
        workspace_name = ws.get("name", "Workspace")

        await repo.delete_workspace(workspace_id)
        print_success(f"Workspace '{workspace_name}' deleted successfully.")
        return EXIT_SUCCESS
