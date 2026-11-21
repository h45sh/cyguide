"""CLI argument parsing, subcommand routing, and execution dispatch."""

import argparse
import asyncio
import sys
from typing import Any, List, Optional

from dotenv import load_dotenv

from cyguide import __version__
from cyguide.cli.context import (
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    CliContext,
)
from cyguide.cli.formatters import RichArgumentParser, print_error


def run_workbench(context: CliContext) -> int:
    """Initialize Textual compatibility and launch CyGuideApp."""
    from cyguide.app import CyGuideApp
    from cyguide.common.logging import install_textual_crash_traps, record_breadcrumb
    from cyguide.ui.compat import setup_textual_compat

    setup_textual_compat()
    install_textual_crash_traps(CyGuideApp)
    record_breadcrumb("workbench", "Launching interactive Textual TUI")

    app = CyGuideApp(
        db_path=context.db_path,
        data_dir=context.data_dir,
        use_ollama=context.use_ollama,
        ollama_model=context.ollama_model,
        tools_dir=context.tools_dir,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[!] CyGuide terminated by user.", file=sys.stderr)
    return EXIT_SUCCESS


async def handle_doctor(args: Any, context: CliContext) -> int:
    """Run comprehensive system, database, permissions, and tool health diagnostics."""
    from cyguide.cli.formatters import print_json
    from cyguide.engine.diagnostics import DiagnosticEngine, run_diagnostics

    report = await run_diagnostics(db_path=context.db_path, tools_dir=context.tools_dir)

    if context.is_json:
        print_json(report.to_dict())
    else:
        print(DiagnosticEngine.format_terminal_report(report), file=sys.stdout)

    return EXIT_SUCCESS if report.healthy else EXIT_RUNTIME_ERROR


def build_parser() -> RichArgumentParser:
    """Construct the CyGuide CLI argument parser with noun-verb subcommands."""
    # Common options inherited across root and subcommands so ordering is flexible:
    common_options = argparse.ArgumentParser(add_help=False)
    common_options.add_argument(
        "--data-dir",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="Path to the CyGuide unified data directory (default: ~/.cyguide or $CYGUIDE_DATA_DIR)",
    )
    common_options.add_argument(
        "--db",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="Path to the SQLite database (default: ~/.cyguide/cyguide.db)",
    )
    common_options.add_argument(
        "--tools",
        metavar="DIR",
        default=argparse.SUPPRESS,
        help="Path to the tools directory (default: bundled tools/)",
    )

    parser = RichArgumentParser(
        prog="cyg",
        description="CyGuide: Guided cybersecurity learning & operations platform.\n"
        "[dim]Run without commands to launch the interactive TUI workbench.[/dim]",
        parents=[common_options],
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"CyGuide {__version__}",
        help="Show program's version number and exit.",
    )
    parser.add_argument(
        "--ollama", action="store_true", help="Enable local LLM explanations via Ollama"
    )
    parser.add_argument(
        "--ollama-model",
        dest="ollama_model",
        metavar="MODEL",
        default="gemma",
        help="Ollama model to use (default: gemma)",
    )
    parser.add_argument(
        "--model",
        dest="model_alias",
        metavar="MODEL",
        default=None,
        help="(Alias for --ollama-model)",
    )
    parser.add_argument(
        "--no-ai",
        "--offline",
        dest="no_ai",
        action="store_true",
        help="Disable all LLM explanations and AI features",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Enable verbose debug logging to stderr",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        parser_class=RichArgumentParser,
    )

    # 1. session domain
    session_parser = subparsers.add_parser(
        "session",
        parents=[common_options],
        help="Investigation session and finding graph lifecycle",
    )
    session_subs = session_parser.add_subparsers(
        dest="session_action",
        parser_class=RichArgumentParser,
    )

    sess_list = session_subs.add_parser(
        "list", parents=[common_options], help="List investigation sessions"
    )
    sess_list.add_argument(
        "-w", "--workspace-id", dest="workspace_id", help="Filter by workspace ID"
    )
    sess_list.add_argument(
        "-j", "--json", action="store_true", help="Output in machine-readable JSON format"
    )

    sess_export = session_subs.add_parser(
        "export",
        parents=[common_options],
        help="Export a session's finding graph (.db) and/or Markdown report",
    )
    sess_export.add_argument(
        "session_id", metavar="SESSION_ID", help="UUID of the session to export"
    )
    sess_export.add_argument(
        "output_path",
        metavar="OUTPUT_FILE",
        nargs="?",
        default=None,
        help="Path to save the portable SQLite .db file (optional if --report is provided)",
    )
    sess_export.add_argument(
        "-o",
        "--output",
        dest="output_opt",
        metavar="OUTPUT_FILE",
        default=None,
        help="Alternative flag to specify output database path",
    )
    sess_export.add_argument(
        "-r",
        "--report",
        metavar="REPORT_FILE",
        help="Path to save the structured Markdown report",
    )

    sess_import = session_subs.add_parser(
        "import",
        parents=[common_options],
        help="Import a portable session SQLite .db file into a workspace",
    )
    sess_import.add_argument(
        "input_path", metavar="INPUT_FILE", help="Path to portable session SQLite .db file"
    )
    sess_import.add_argument(
        "-w", "--workspace-id", dest="workspace_id", help="Target workspace ID"
    )

    sess_del = session_subs.add_parser(
        "delete", parents=[common_options], help="Delete an investigation session"
    )
    sess_del.add_argument("session_id", metavar="SESSION_ID", help="UUID of the session to delete")
    sess_del.add_argument("-f", "--force", action="store_true", help="Delete without prompt")

    # 2. workspace domain
    ws_parser = subparsers.add_parser(
        "workspace",
        parents=[common_options],
        help="Engagement workspace container management",
    )
    ws_subs = ws_parser.add_subparsers(dest="workspace_action", parser_class=RichArgumentParser)

    ws_list = ws_subs.add_parser(
        "list", parents=[common_options], help="List engagement workspaces"
    )
    ws_list.add_argument("-j", "--json", action="store_true", help="Output in JSON format")

    ws_create = ws_subs.add_parser(
        "create", parents=[common_options], help="Create a new workspace"
    )
    ws_create.add_argument("name", metavar="NAME", help="Name of the new workspace")
    ws_create.add_argument(
        "-j", "--json", action="store_true", help="Output created record in JSON format"
    )

    ws_del = ws_subs.add_parser(
        "delete", parents=[common_options], help="Delete a workspace and all its sessions"
    )
    ws_del.add_argument(
        "workspace_id", metavar="WORKSPACE_ID", help="UUID of the workspace to delete"
    )
    ws_del.add_argument("-f", "--force", action="store_true", help="Delete without confirmation")

    # 3. tool domain
    tool_parser = subparsers.add_parser(
        "tool",
        parents=[common_options],
        help="Security tool ecosystem inspection and verification",
    )
    tool_subs = tool_parser.add_subparsers(dest="tool_action", parser_class=RichArgumentParser)

    t_list = tool_subs.add_parser(
        "list", parents=[common_options], help="List discovered tools and install status"
    )
    t_list.add_argument(
        "-j", "--json", action="store_true", help="Output tool records in JSON format"
    )

    t_check = tool_subs.add_parser(
        "check", parents=[common_options], help="Validate tool binary availability in PATH"
    )
    t_check.add_argument("tool_name", nargs="?", default=None, help="Specific tool to validate")
    t_check.add_argument(
        "-j", "--json", action="store_true", help="Output validation status in JSON format"
    )

    t_info = tool_subs.add_parser(
        "info", parents=[common_options], help="Show deep tool metadata and recipes"
    )
    t_info.add_argument("tool_name", metavar="TOOL_NAME", help="Tool name (e.g. nmap, ffuf)")
    t_info.add_argument(
        "-j", "--json", action="store_true", help="Output tool metadata in JSON format"
    )

    # 4. doctor domain (replaces legacy check)
    doc_parser = subparsers.add_parser(
        "doctor",
        parents=[common_options],
        help="Verify environment, permissions, database, wordlists, and tool health",
    )
    doc_parser.add_argument(
        "-j", "--json", action="store_true", help="Output diagnostics in JSON format"
    )

    # 5. lab domain
    lab_parser = subparsers.add_parser(
        "lab",
        parents=[common_options],
        help="Learning mode sandboxes, .cyglab checkpoints, and mock targets",
    )
    lab_subs = lab_parser.add_subparsers(dest="lab_action", parser_class=RichArgumentParser)

    l_list = lab_subs.add_parser(
        "list", parents=[common_options], help="List saved .cyglab checkpoints"
    )
    l_list.add_argument(
        "-j", "--json", action="store_true", help="Output checkpoints in JSON format"
    )

    l_save = lab_subs.add_parser(
        "save", parents=[common_options], help="Save learning sandbox state to a checkpoint"
    )
    l_save.add_argument(
        "checkpoint_name", metavar="NAME", help="Filename or identifier for the checkpoint"
    )
    l_save.add_argument("--target", default="", help="Primary target associated with checkpoint")
    l_save.add_argument("--notes", default="", help="Student notes to persist with checkpoint")

    l_load = lab_subs.add_parser(
        "load", parents=[common_options], help="Load and restore a .cyglab checkpoint"
    )
    l_load.add_argument(
        "checkpoint_file", metavar="FILE", help="Path to .cyglab checkpoint archive"
    )
    l_load.add_argument(
        "-j", "--json", action="store_true", help="Output loaded state metadata in JSON format"
    )

    l_reset = lab_subs.add_parser(
        "reset", parents=[common_options], help="Reset the learning sandbox graph and state"
    )
    l_reset.add_argument("-f", "--force", action="store_true", help="Reset without confirmation")

    l_start = lab_subs.add_parser(
        "start", parents=[common_options], help="Start embedded mock target web server"
    )
    l_start.add_argument("--host", default="127.0.0.1", help="Bind IP address (default: 127.0.0.1)")
    l_start.add_argument("--port", type=int, default=8888, help="Bind port (default: 8888)")

    # 5. logs domain
    logs_parser = subparsers.add_parser(
        "logs",
        parents=[common_options],
        help="Inspect, filter, or clear centralized diagnostic application logs",
    )
    logs_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        help="Number of recent log lines to display (default: 50)",
    )
    logs_parser.add_argument(
        "-c",
        "--crashes",
        action="store_true",
        help="Extract only fatal crashes, unhandled exceptions, and UI panics",
    )
    logs_parser.add_argument(
        "--clear",
        action="store_true",
        help="Truncate and clear the system log file",
    )

    # Configure helpful real-world examples across all parsers
    parser.examples = [
        ("cyg", "Launch the interactive dual-mode TUI workbench"),
        ("cyg doctor", "Audit environment, database, wordlists, and scanner tools"),
        ("cyg logs", "Inspect recent application and crash logs"),
        ("cyg logs --crashes", "Filter and display recent crash/panic tracebacks"),
        ("cyg tool list", "List installed security tools and recipe counts"),
        ("cyg tool check nmap", "Verify if 'nmap' is installed and available in PATH"),
        ("cyg session list", "List recorded investigation sessions with finding counts"),
        ("cyg session export <name|id> -r report.md", "Export findings to a Markdown report"),
        ("cyg workspace list", "List engagement workspaces and session tallies"),
        ("cyg lab start", "Start offline mock practice target on 127.0.0.1:8888"),
    ]

    session_parser.examples = [
        ("cyg session list", "List all sessions with finding counts & workspaces"),
        (
            "cyg session export 'Default Session' output.db",
            "Export finding graph to portable SQLite .db",
        ),
        (
            "cyg session export 'Default Session' -r report.md",
            "Compile findings into an executive Markdown report",
        ),
        (
            "cyg session import shared.db -w 'Engagement-A'",
            "Import portable session into a workspace",
        ),
        ("cyg session delete 'Default Session'", "Delete session and cascade purge entity graph"),
    ]

    ws_parser.examples = [
        ("cyg workspace list", "List all engagement workspaces"),
        ("cyg workspace create 'Client Engagement'", "Create a new isolated workspace"),
        ("cyg workspace delete 'Client Engagement'", "Delete workspace and contained sessions"),
    ]

    tool_parser.examples = [
        ("cyg tool list", "List discovered tools, versions, and install status"),
        ("cyg tool check", "Verify PATH availability across all tools (exit 127 if missing)"),
        ("cyg tool check ffuf", "Check if 'ffuf' binary is installed"),
        ("cyg tool info nmap", "Display nmap schema capabilities and curriculum recipes"),
    ]

    lab_parser.examples = [
        ("cyg lab list", "List saved .cyglab checkpoints"),
        (
            "cyg lab save lesson1 --target 10.10.10.5",
            "Save active sandbox state to .cyglab archive",
        ),
        ("cyg lab load lesson1.cyglab", "Restore learning sandbox from checkpoint"),
        ("cyg lab reset", "Reset sandbox findings, timeline, and terminal buffers"),
        ("cyg lab start --port 8888", "Start embedded loopback web target server"),
    ]

    logs_parser.examples = [
        ("cyg logs", "Display the last 50 lines of system logs"),
        ("cyg logs -n 100", "Display the last 100 lines of system logs"),
        ("cyg logs --crashes", "Filter and display recent crash and panic traces"),
        ("cyg logs --clear", "Clear ~/.cyguide/logs/cyguide.log"),
    ]

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Execute CyGuide CLI dispatch."""
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    context = CliContext.from_args(args)

    from cyguide.common.logging import (
        install_global_exception_traps,
        logger,
        record_breadcrumb,
        setup_system_logging,
    )

    setup_system_logging(data_dir=context.data_dir, verbose=context.verbose)
    install_global_exception_traps()
    record_breadcrumb("cli", "CLI invoked", subcommand=args.subcommand or "workbench")

    if not args.subcommand:
        # Default fallback: Interactive Textual Workbench
        return run_workbench(context)

    # Auto-display full help on bare command groups without an action
    if args.subcommand in ("session", "workspace", "tool", "lab"):
        action_name = f"{args.subcommand}_action"
        if not getattr(args, action_name, None):
            for a in parser._actions:
                if isinstance(a, argparse._SubParsersAction) and args.subcommand in a.choices:
                    print(a.choices[args.subcommand].format_help(), file=sys.stdout)
                    return EXIT_SUCCESS

    try:
        if args.subcommand == "session":
            from cyguide.cli.commands.session import handle_session

            return asyncio.run(handle_session(args, context))
        elif args.subcommand == "workspace":
            from cyguide.cli.commands.workspace import handle_workspace

            return asyncio.run(handle_workspace(args, context))
        elif args.subcommand == "tool":
            from cyguide.cli.commands.tool import handle_tool

            return handle_tool(args, context)
        elif args.subcommand == "doctor":
            return asyncio.run(handle_doctor(args, context))
        elif args.subcommand == "logs":
            from cyguide.cli.commands.logs import handle_logs

            return handle_logs(args, context)
        elif args.subcommand == "lab":
            from cyguide.cli.commands.lab import handle_lab

            return asyncio.run(handle_lab(args, context))
        else:
            print_error(f"Unknown subcommand: {args.subcommand}")
            return EXIT_USAGE_ERROR
    except KeyboardInterrupt:
        print_error("Operation cancelled by user.")
        return EXIT_RUNTIME_ERROR
    except Exception as exc:
        logger.critical("Command '%s' failed unexpectedly: %s", args.subcommand, exc, exc_info=True)
        print_error(f"Command execution failed: {exc}")
        if context.verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        return EXIT_RUNTIME_ERROR
