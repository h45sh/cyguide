"""Entry point script for CyGuide."""

import argparse
import sys

from dotenv import load_dotenv

from cyguide import __version__
from cyguide.paths import get_default_data_dir, get_default_db_path


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="CyGuide: TUI-based guided cybersecurity learning platform.")
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"CyGuide {__version__}"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to the CyGuide unified data directory (default: ~/.cyguide or $CYGUIDE_DATA_DIR)"
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite database (default: ~/.cyguide/cyguide.db)"
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Enable local LLM explanations via Ollama"
    )
    parser.add_argument(
        "--model",
        default="gemma",
        help="Ollama model to use (default: gemma)"
    )
    parser.add_argument(
        "--tools",
        default=None,
        help="Path to the tools directory (default: bundled tools/)"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands (optional)")

    # export subcommand
    export_parser = subparsers.add_parser("export", help="Export a session's findings/logs")
    export_parser.add_argument("session_id", help="UUID of the session to export")
    export_parser.add_argument("output_path", help="Path to save the portable SQLite .db file")
    export_parser.add_argument("--report", help="Path to save the structured Markdown report")

    # import subcommand
    import_parser = subparsers.add_parser("import", help="Import a portable session SQLite .db file")
    import_parser.add_argument("input_path", help="Path to the portable SQLite .db file")
    import_parser.add_argument("--workspace-id", help="ID of the workspace to import the session into (optional)")

    # check subcommand
    check_parser = subparsers.add_parser("check", help="Verify environment dependencies, database health, and tool installations")
    check_parser.add_argument("--json", action="store_true", help="Output diagnostics in JSON format")

    args = parser.parse_args()

    data_dir = args.data_dir or get_default_data_dir()
    db_path = args.db or get_default_db_path(data_dir)

    if args.subcommand == "export":
        import asyncio
        import os

        from cyguide.engine.reporter import generate_markdown_report
        from cyguide.engine.store import GraphStore

        async def run_export() -> int:
            store = GraphStore(db_path)
            await store.initialize()
            exit_code = 0

            # Export DB
            print(f"[*] Exporting session {args.session_id} to database {args.output_path}...")
            out_dir = os.path.dirname(os.path.abspath(args.output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            try:
                await store.export_session(args.session_id, args.output_path)
                if os.path.exists(args.output_path):
                    try:
                        os.chmod(args.output_path, 0o600)
                    except OSError:
                        pass
                print(f"[+] Session database exported successfully to {args.output_path}")
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
                    with open(fd, "w", encoding="utf-8", closefd=True) as f:
                        f.write(report_content)
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
            store = GraphStore(db_path)
            await store.initialize()
            print(f"[*] Importing session from {args.input_path}...")
            exit_code = 0
            try:
                new_sess_id = await store.import_session(args.input_path, target_workspace_id=args.workspace_id)
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
            report = await run_diagnostics(db_path=db_path, tools_dir=args.tools)
            if getattr(args, "json", False):
                print(json.dumps(report.to_dict(), indent=2))
            else:
                print(format_terminal_report(report))
            return 0 if report.healthy else 1

        sys.exit(asyncio.run(run_check()))

    from cyguide.app import CyGuideApp

    app = CyGuideApp(
        db_path=args.db,
        data_dir=args.data_dir,
        use_ollama=args.ollama,
        ollama_model=args.model,
        tools_dir=args.tools
    )
    try:
        app.run()
    except KeyboardInterrupt:
        # i case the user hits Ctrl+C at the exact moment of shutdown.
        print("\n[!] CyGuide terminated by user.")

if __name__ == "__main__":
    main()
