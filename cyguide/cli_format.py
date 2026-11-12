"""Rich-styled argument parser for CyGuide CLI."""

import argparse
import shutil
from typing import Any, List, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class RichArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser that formats help screens using Rich panels and styled tables."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def format_help(self) -> str:
        """Format the help message using Rich styled panels."""
        term_w = shutil.get_terminal_size((88, 24)).columns
        width = max(60, min(term_w, 96))

        # Respect NO_COLOR standard
        console = Console(width=width, color_system="auto", highlight=False)
        with console.capture() as capture:
            self._print_rich_help(console)
        return capture.get()

    def _print_rich_help(self, console: Console) -> None:
        """Render the structured help message to the provided Rich console."""
        has_subcommands = any(isinstance(a, argparse._SubParsersAction) for a in self._actions)
        usage_sub = " [cyan][COMMAND][/cyan] [dim][ARGS]...[/dim]" if has_subcommands else ""
        console.print(
            f"[bold yellow]Usage:[/bold yellow] [bold white]{self.prog}[/bold white] [dim][OPTIONS][/dim]{usage_sub}\n"
        )

        if self.description:
            console.print(f"{self.description}\n")

        positionals: List[Tuple[str, str]] = []
        options: List[Tuple[str, str, str]] = []
        subcommands: List[Tuple[str, str]] = []

        seen_options = set()

        for action in self._actions:
            if action.help == argparse.SUPPRESS:
                continue

            if isinstance(action, argparse._SubParsersAction):
                for choice_action in getattr(action, "_choices_actions", []):
                    if choice_action.help != argparse.SUPPRESS:
                        subcommands.append((choice_action.dest, choice_action.help or ""))
            elif action.option_strings:
                opts = ", ".join(action.option_strings)
                # Deduplicate if common parent added identical options
                if opts in seen_options:
                    continue
                seen_options.add(opts)

                meta = action.metavar or ""
                if not meta and action.nargs not in (0, None):
                    meta = action.dest.upper()
                options.append((opts, meta, action.help or ""))
            else:
                name = action.metavar or action.dest.upper()
                positionals.append((name, action.help or ""))

        if positionals:
            pos_table = Table.grid(padding=(0, 2))
            pos_table.add_column("arg", style="bold cyan", no_wrap=True)
            pos_table.add_column("desc", style="default")
            for name, desc in positionals:
                pos_table.add_row(name, desc)
            console.print(
                Panel(
                    pos_table,
                    title="[bold]Arguments[/bold]",
                    title_align="left",
                    border_style="dim",
                    box=box.ROUNDED,
                )
            )

        if options:
            opt_table = Table.grid(padding=(0, 2))
            opt_table.add_column("flag", style="bold cyan", no_wrap=True)
            opt_table.add_column("meta", style="dim italic", no_wrap=True)
            opt_table.add_column("desc", style="default")
            for opts, meta, desc in options:
                opt_table.add_row(opts, meta, desc)
            console.print(
                Panel(
                    opt_table,
                    title="[bold]Options[/bold]",
                    title_align="left",
                    border_style="dim",
                    box=box.ROUNDED,
                )
            )

        if subcommands:
            cmd_table = Table.grid(padding=(0, 2))
            cmd_table.add_column("cmd", style="bold cyan", no_wrap=True)
            cmd_table.add_column("desc", style="default")
            for name, desc in subcommands:
                cmd_table.add_row(name, desc)
            console.print(
                Panel(
                    cmd_table,
                    title="[bold]Commands[/bold]",
                    title_align="left",
                    border_style="dim",
                    box=box.ROUNDED,
                )
            )
