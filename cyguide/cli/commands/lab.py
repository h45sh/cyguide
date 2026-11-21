"""Learning Mode sandbox and .cyglab checkpoints CLI command handler."""

import asyncio
import os
from typing import Any

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
from cyguide.engine.executor import Executor
from cyguide.engine.lab_server import LabMockServer
from cyguide.engine.learning import LearningSession
from cyguide.engine.power_facade import PowerWorkspaceFacade
from cyguide.paths import get_default_checkpoints_dir


def _create_learning_session(store, context: CliContext, ws_id, sess_id) -> LearningSession:
    """Create wired LearningSession instance for headless CLI operations."""
    registry = context.get_tool_registry()
    executor = Executor(store)
    facade = PowerWorkspaceFacade(store, executor, registry)
    return LearningSession(
        store=store,
        registry=registry,
        execution=facade.execution,
        session_id=sess_id,
        workspace_id=ws_id,
    )


async def handle_lab(args: Any, context: CliContext) -> int:
    """Route lab subcommands."""
    subaction = getattr(args, "lab_action", None)
    if not subaction:
        print_error("Missing lab action. Use: list, save, load, reset, or start.")
        return EXIT_USAGE_ERROR

    if subaction == "list":
        return _lab_list(context)
    elif subaction == "save":
        return await _lab_save(args, context)
    elif subaction == "load":
        return await _lab_load(args, context)
    elif subaction == "reset":
        return await _lab_reset(args, context)
    elif subaction == "start":
        return await _lab_start(args, context)
    else:
        print_error(f"Unknown lab action: {subaction}")
        return EXIT_USAGE_ERROR


def _lab_list(context: CliContext) -> int:
    """List all saved .cyglab checkpoints."""
    checkpoints_dir = get_default_checkpoints_dir(context.data_dir)
    checkpoints = LearningSession.list_checkpoints(checkpoints_dir)

    if context.is_json:
        print_json(checkpoints)
        return EXIT_SUCCESS

    if not checkpoints:
        print_info(f"No .cyglab checkpoints found in {checkpoints_dir}")
        return EXIT_SUCCESS

    rows = []
    for cp in checkpoints:
        fname = os.path.basename(cp.get("path", ""))
        cp_name = fname[:-7] if fname.endswith(".cyglab") else fname
        saved_str = str(cp.get("saved_at", ""))[:19].replace("T", " ")
        rows.append(
            [
                cp_name,
                str(cp.get("primary_target", "N/A")),
                str(cp.get("active_tool", "lab")),
                str(cp.get("nodes_count", 0)),
                f"{cp.get('size_bytes', 0) / 1024:.1f} KB",
                saved_str,
            ]
        )

    print_table(
        title="Saved Learning Mode Checkpoints",
        columns=[
            ("Checkpoint Name", "bold white"),
            ("Target", "cyan"),
            ("Active Tool", "green"),
            ("Findings", "yellow"),
            ("Size", "dim"),
            ("Saved At", "dim"),
        ],
        rows=rows,
    )
    return EXIT_SUCCESS


async def _lab_save(args: Any, context: CliContext) -> int:
    """Save the active sandbox state into a .cyglab checkpoint."""
    name = args.checkpoint_name.strip()
    if not name:
        print_error("Checkpoint name cannot be empty.")
        return EXIT_USAGE_ERROR

    if not name.endswith(".cyglab"):
        name += ".cyglab"

    checkpoints_dir = get_default_checkpoints_dir(context.data_dir)
    out_path = os.path.join(checkpoints_dir, name)

    async with context.open_store() as store:
        ws_id, sess_id = await store.get_or_create_learning_sandbox()
        session = _create_learning_session(store, context, ws_id, sess_id)
        if getattr(args, "notes", None):
            session.notes = args.notes

        target = getattr(args, "target", "") or ""
        try:
            saved_path = await session.save_checkpoint(
                out_path,
                target=target,
            )
            print_success(f"Learning session checkpoint saved to: {saved_path}")
            return EXIT_SUCCESS
        except Exception as e:
            print_error(f"Failed to save checkpoint: {e!s}")
            return EXIT_RUNTIME_ERROR


async def _lab_load(args: Any, context: CliContext) -> int:
    """Inspect and load a .cyglab checkpoint."""
    cp_path = args.checkpoint_file
    if not os.path.exists(cp_path):
        checkpoints_dir = get_default_checkpoints_dir(context.data_dir)
        candidate = os.path.join(checkpoints_dir, cp_path)
        if os.path.exists(candidate):
            cp_path = candidate
        else:
            print_error(f"Checkpoint file not found: {cp_path}")
            return EXIT_RUNTIME_ERROR

    async with context.open_store() as store:
        ws_id, sess_id = await store.get_or_create_learning_sandbox()
        session = _create_learning_session(store, context, ws_id, sess_id)
        try:
            meta = await session.load_checkpoint(cp_path)
            if context.is_json:
                print_json(meta)
            else:
                print_success(f"Checkpoint loaded successfully: {os.path.basename(cp_path)}")
                print_info(f"Target: {meta.get('target', 'N/A')}")
                print_info(f"Active Tool: {meta.get('active_tool', 'N/A')}")
                print_info(f"Saved At: {meta.get('saved_at', 'N/A')}")
                if meta.get("notes"):
                    print_info(f"Notes:\n{meta['notes']}")
            return EXIT_SUCCESS
        except Exception as e:
            print_error(f"Failed to load checkpoint: {e!s}")
            return EXIT_RUNTIME_ERROR


async def _lab_reset(args: Any, context: CliContext) -> int:
    """Reset the learning sandbox graph and session state."""
    async with context.open_store() as store:
        ws_id, sess_id = await store.get_or_create_learning_sandbox()
        session = _create_learning_session(store, context, ws_id, sess_id)
        try:
            await session.reset_session()
            print_success("Learning sandbox reset successfully. Workspace is clean.")
            return EXIT_SUCCESS
        except Exception as e:
            print_error(f"Failed to reset sandbox: {e!s}")
            return EXIT_RUNTIME_ERROR


async def _lab_start(args: Any, context: CliContext) -> int:
    """Start embedded mock target server."""
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8888)

    server = LabMockServer(host=host, port=port)
    await server.start()
    print_success(f"CyGuide Mock Lab Target running at http://{host}:{port}/")
    print_info("Press Ctrl+C to terminate the mock target server.")

    try:
        await server.serve_forever()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await server.stop()
        print_info("Mock Lab Target stopped.")
    return EXIT_SUCCESS
