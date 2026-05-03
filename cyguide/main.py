"""Entry point script for CyGuide."""

import argparse
from cyguide.app import CyGuideApp

def main():
    parser = argparse.ArgumentParser(description="CyGuide: TUI-based guided cybersecurity learning platform.")
    parser.add_argument(
        "--db", 
        default="data/cyguide.db", 
        help="Path to the SQLite database (default: data/cyguide.db)"
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
    args = parser.parse_args()

    app = CyGuideApp(
        db_path=args.db, 
        use_ollama=args.ollama, 
        ollama_model=args.model,
        tools_dir=args.tools
    )
    try:
        app.run()
    except KeyboardInterrupt:
        # Textual handles most cleanup, but this prevents the raw traceback
        # if the user hits Ctrl+C at the exact moment of shutdown.
        print("\n[!] CyGuide terminated by user.")

if __name__ == "__main__":
    main()
