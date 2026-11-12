"""Entry point script for CyGuide."""

import argparse
import os
import sys

from dotenv import load_dotenv

from cyguide import __version__
from cyguide.cli_format import RichArgumentParser
from cyguide.paths import get_default_data_dir, get_default_db_path


def main():
    load_dotenv()

    # Common options inherited across root and subcommands so ordering is flexible:
    # e.g. `cyg --db custom.db check` and `cyg check --db custom.db` both work!
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
        description="CyGuide: TUI-based guided cybersecurity learning & operations platform.\n"
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

    # export subcommand
    export_parser = subparsers.add_parser(
        "export",
        parents=[common_options],
        help="Export a session's finding graph (.db) and/or Markdown report",
    )
    export_parser.add_argument(
        "session_id", metavar="SESSION_ID", help="UUID of the session to export"
    )
    export_parser.add_argument(
        "output_path",
        metavar="OUTPUT_FILE",
        nargs="?",
        default=None,
        help="Path to save the portable SQLite .db file (optional if --report is provided, default: ./<SESSION_ID>.db)",
    )
    export_parser.add_argument(
        "-o",
        "--output",
        dest="output_opt",
        metavar="OUTPUT_FILE",
        default=None,
        help="Alternative flag to specify output database path",
    )
    export_parser.add_argument(
        "-r",
        "--report",
        metavar="REPORT_FILE",
        help="Path to save the structured Markdown report",
    )

    # import subcommand
    import_parser = subparsers.add_parser(
        "import",
        parents=[common_options],
        help="Import a portable session SQLite .db file into a workspace",
    )
    import_parser.add_argument(
        "input_path",
        metavar="INPUT_FILE",
        help="Path to the portable session SQLite .db file",
    )
    import_parser.add_argument(
        "-w",
        "--workspace-id",
        dest="workspace_id",
        metavar="ID",
        help="ID of the workspace to import the session into (optional)",
    )

    # check subcommand
    check_parser = subparsers.add_parser(
        "check",
        parents=[common_options],
        help="Verify environment dependencies, database health, and tool installations",
    )
    check_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output diagnostics in JSON format",
    )

    args = parser.parse_args()

    data_dir_arg = getattr(args, "data_dir", None)
    db_arg = getattr(args, "db", None)
    tools_arg = getattr(args, "tools", None)

    data_dir = data_dir_arg or get_default_data_dir()
    db_path = db_arg or get_default_db_path(data_dir)

    selected_model = args.model_alias or getattr(args, "ollama_model", "gemma")

    if getattr(args, "no_ai", False):
        os.environ["CYGUIDE_OFFLINE"] = "1"
        os.environ["CYGUIDE_NO_AI"] = "1"
        use_ollama = False
    else:
        use_ollama = getattr(args, "ollama", False)

    if args.subcommand == "export":
        import asyncio

        from cyguide.engine.reporter import generate_markdown_report
        from cyguide.engine.store import GraphStore

        async def run_export() -> int:
            store = GraphStore(db_path)
            await store.initialize()
            exit_code = 0

            # Determine export target DB
            output_db = args.output_path or getattr(args, "output_opt", None)
            if not output_db and not args.report:
                output_db = f"{args.session_id}.db"

            # Export DB if requested or defaulted
            if output_db:
                print(f"[*] Exporting session {args.session_id} to database {output_db}...")
                out_dir = os.path.dirname(os.path.abspath(output_db))
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                try:
                    await store.export_session(args.session_id, output_db)
                    if os.path.exists(output_db):
                        try:
                            os.chmod(output_db, 0o600)
                        except OSError:
                            pass
                    print(f"[+] Session database exported successfully to {output_db}")
                except Exception as e:
                    print(f"[!] Database export failed: {e!s}")
                    exit_code = 1

            # Export Report if requested
            if args.report:
                print(f"[*] Generating Markdown report to {args.report}...")
                rep_dir = os.path.dirname(os.path.abspath(args.report))
                if rep_dir:
                    os.makedirs(rep_dir, exist_ok=True)
                try:
                    report_content = await generate_markdown_report(store, args.session_id)
                    fd = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    try:
                        with open(fd, "w", encoding="utf-8", closefd=False) as f:
                            f.write(report_content)
                    finally:
                        os.close(fd)
                    try:
                        os.chmod(args.report, 0o600)
                    except OSError:
                        pass
                    print(f"[+] Markdown report exported successfully to {args.report}")
                except Exception as e:
                    print(f"[!] Report generation failed: {e!s}")
                    exit_code = 1

            await store.close()
            return exit_code

        sys.exit(asyncio.run(run_export()))

    elif args.subcommand == "import":
        import asyncio

        from cyguide.engine.store import GraphStore

        async def run_import() -> int:
            if not os.path.exists(args.input_path):
                print(f"[!] Import failed: File not found: {args.input_path}")
                return 1

            store = GraphStore(db_path)
            await store.initialize()
            print(f"[*] Importing session from {args.input_path}...")
            exit_code = 0
            try:
                new_sess_id = await store.import_session(
                    args.input_path, target_workspace_id=getattr(args, "workspace_id", None)
                )
                print("[+] Session imported successfully!")
                print(f"[+] New Session ID: {new_sess_id}")
            except Exception as e:
                print(f"[!] Import failed: {e!s}")
                exit_code = 1
            await store.close()
            return exit_code

        sys.exit(asyncio.run(run_import()))

    elif args.subcommand == "check":
        import asyncio
        import json

        from cyguide.engine.diagnostics import format_terminal_report, run_diagnostics

        async def run_check():
            report = await run_diagnostics(db_path=db_path, tools_dir=tools_arg)
            if getattr(args, "json", False):
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(format_terminal_report(report))
            return 0 if report.healthy else 1

        sys.exit(asyncio.run(run_check()))

    from cyguide.app import CyGuideApp
    from cyguide.ui.compat import setup_textual_compat

    setup_textual_compat()

    app = CyGuideApp(
        db_path=db_arg,
        data_dir=data_dir_arg,
        use_ollama=use_ollama,
        ollama_model=selected_model,
        tools_dir=tools_arg,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[!] CyGuide terminated by user.")


if __name__ == "__main__":
    main()
