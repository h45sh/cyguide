"""Session lifecycle and graph export/import CLI command handler."""

import os
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
from cyguide.engine.reporter import SessionReportService
from cyguide.engine.workspace_repository import WorkspaceRepository


async def _resolve_session(identifier: str, repo: WorkspaceRepository) -> Optional[dict]:
    """Resolve a session by its UUID or human-readable name."""
    # 1. Direct lookup by ID
    sess = await repo.get_session(identifier)
    if sess:
        return sess

    # 2. Match by case-insensitive name or ID prefix across all workspaces
    workspaces = await repo.list_workspaces()
    candidates = []
    for ws in workspaces:
        sessions = await repo.list_sessions(ws["id"])
        for s in sessions:
            if s.get("name", "").strip().lower() == identifier.strip().lower():
                candidates.append(s)
            elif str(s.get("id", "")).startswith(identifier):
                candidates.append(s)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        exact = [
            s for s in candidates if s.get("name", "").strip().lower() == identifier.strip().lower()
        ]
        if len(exact) == 1:
            return exact[0]
    return None


async def handle_session(args: Any, context: CliContext) -> int:
    """Route session subcommands."""
    subaction = getattr(args, "session_action", None)
    if not subaction:
        return EXIT_USAGE_ERROR

    if subaction == "list":
        return await _session_list(args, context)
    elif subaction == "export":
        return await _session_export(args, context)
    elif subaction == "import":
        return await _session_import(args, context)
    elif subaction == "delete":
        return await _session_delete(args, context)
    else:
        print_error(f"Unknown session action: {subaction}")
        return EXIT_USAGE_ERROR


async def _session_list(args: Any, context: CliContext) -> int:
    """List investigation sessions with human-readable workspace and finding metrics."""
    workspace_id = getattr(args, "workspace_id", None)

    async with context.open_workspace_repo() as (store, repo):
        workspaces = await repo.list_workspaces()
        ws_name_map = {ws["id"]: ws.get("name", "Default") for ws in workspaces}

        if workspace_id:
            sessions = await repo.list_sessions(workspace_id)
        else:
            sessions = []
            for ws in workspaces:
                ws_sessions = await repo.list_sessions(ws["id"])
                sessions.extend(ws_sessions)

        # Enrich session records with human-readable workspace name and finding counts
        enriched = []
        for s in sessions:
            sid = str(s.get("id", ""))
            ws_id = s.get("workspace_id", "")
            stats = await store.get_stats(session_id=sid)
            node_count = stats.get("total_nodes", 0)
            item = dict(s)
            item["workspace_name"] = ws_name_map.get(ws_id, "Unknown")
            item["finding_count"] = node_count
            enriched.append(item)

        if context.is_json:
            print_json(enriched)
            return EXIT_SUCCESS

        if not enriched:
            print_info("No investigation sessions found.")
            return EXIT_SUCCESS

        rows = []
        for item in enriched:
            created_str = str(item.get("created_at", ""))[:19].replace("T", " ")
            rows.append(
                [
                    str(item.get("name", "Unnamed Session")),
                    str(item.get("workspace_name", "Unknown")),
                    str(item.get("status", "ACTIVE")),
                    str(item.get("finding_count", 0)),
                    created_str,
                    str(item.get("id", ""))[:8] + "...",
                ]
            )

        print_table(
            title="Investigation Sessions",
            columns=[
                ("Session Name", "bold white"),
                ("Workspace", "cyan"),
                ("Status", "green"),
                ("Findings", "yellow"),
                ("Created", "dim"),
                ("ID", "dim"),
            ],
            rows=rows,
        )
        return EXIT_SUCCESS


async def _session_export(args: Any, context: CliContext) -> int:
    """Export session database and/or Markdown report (resolving by name or ID)."""
    raw_ident = args.session_id

    async with context.open_workspace_repo() as (store, repo):
        session = await _resolve_session(raw_ident, repo)
        if not session:
            print_error(f"Session not found: {raw_ident}")
            return EXIT_RUNTIME_ERROR

        session_id = session["id"]
        session_name = session.get("name", "Session")

        output_db = args.output_path or getattr(args, "output_opt", None)
        report_file = getattr(args, "report", None)

        if not output_db and not report_file:
            output_db = f"{session_id}.db"

        exit_code = EXIT_SUCCESS

        if output_db:
            print_info(
                f"Exporting session '{session_name}' ({session_id[:8]}) to database {output_db}..."
            )
            out_dir = os.path.dirname(os.path.abspath(output_db))
            if out_dir:
                os.makedirs(out_dir, mode=0o700, exist_ok=True)
            try:
                # Pre-create file with atomic 0o600 permissions to eliminate TOCTOU window
                if not os.path.exists(output_db):
                    fd = os.open(output_db, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                    os.close(fd)
                await store.export_session(session_id, output_db)
                print_success(f"Session database exported successfully to {output_db}")
            except Exception as e:
                print_error(f"Database export failed: {e!s}")
                exit_code = EXIT_RUNTIME_ERROR

        if report_file:
            print_info(f"Generating Markdown report for '{session_name}' to {report_file}...")
            try:
                await SessionReportService(store).export_markdown_report(session_id, report_file)
                print_success(f"Markdown report exported successfully to {report_file}")
            except Exception as e:
                print_error(f"Report generation failed: {e!s}")
                exit_code = EXIT_RUNTIME_ERROR

        return exit_code


async def _session_import(args: Any, context: CliContext) -> int:
    """Import a portable session database."""
    input_path = args.input_path
    if not os.path.exists(input_path):
        print_error(f"Import failed: File not found: {input_path}")
        return EXIT_RUNTIME_ERROR

    workspace_ident = getattr(args, "workspace_id", None)
    print_info(f"Importing session from {input_path}...")

    async with context.open_workspace_repo() as (store, repo):
        target_ws_id = None
        if workspace_ident:
            # Resolve target workspace by name or ID
            workspaces = await repo.list_workspaces()
            for ws in workspaces:
                if (
                    ws.get("id") == workspace_ident
                    or ws.get("name", "").strip().lower() == workspace_ident.strip().lower()
                ):
                    target_ws_id = ws["id"]
                    break
            if not target_ws_id:
                target_ws_id = workspace_ident

        try:
            new_sess_id = await store.import_session(input_path, target_workspace_id=target_ws_id)
            sess = await repo.get_session(new_sess_id)
            sess_name = sess.get("name", "Imported Session") if sess else "Imported Session"
            print_success(f"Session '{sess_name}' imported successfully!")
            print_success(f"Session ID: {new_sess_id}")
            return EXIT_SUCCESS
        except Exception as e:
            print_error(f"Import failed: {e!s}")
            return EXIT_RUNTIME_ERROR


async def _session_delete(args: Any, context: CliContext) -> int:
    """Delete an investigation session (resolving by name or ID)."""
    raw_ident = args.session_id

    async with context.open_workspace_repo() as (store, repo):
        session = await _resolve_session(raw_ident, repo)
        if not session:
            print_error(f"Session not found: {raw_ident}")
            return EXIT_RUNTIME_ERROR

        session_id = session["id"]
        session_name = session.get("name", "Session")

        await repo.delete_session(session_id)
        print_success(f"Session '{session_name}' deleted successfully.")
        return EXIT_SUCCESS
