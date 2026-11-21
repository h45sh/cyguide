"""Rich terminal styling and machine-readable JSON formatting for CyGuide CLI."""

import argparse
import json
import shutil
import sys
from typing import Any, List, Optional, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class RichArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser that formats help screens using Rich panels and styled tables."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.examples: List[Tuple[str, str]] = kwargs.pop("examples", [])
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
        has_subcommands = any(
            isinstance(a, argparse._SubParsersAction) for a in self._actions
        )  # codeguard: ignore[PRIVATE_STATE_LEAK,PRIVATE_STATE_LEAK_REGEX]
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

            if isinstance(
                action, argparse._SubParsersAction
            ):  # codeguard: ignore[PRIVATE_STATE_LEAK,PRIVATE_STATE_LEAK_REGEX]
                for choice_action in getattr(action, "_choices_actions", []):
                    if choice_action.help != argparse.SUPPRESS:
                        cmd_display = choice_action.dest
                        child_parser = action.choices.get(choice_action.dest)
                        if child_parser:
                            child_verbs = []
                            for ca in getattr(child_parser, "_actions", []):
                                if isinstance(ca, argparse._SubParsersAction):
                                    child_verbs.extend(list(ca.choices.keys()))
                            if child_verbs:
                                cmd_display = (
                                    f"{choice_action.dest} [dim]<{'|'.join(child_verbs)}>[/dim]"
                                )
                        subcommands.append((cmd_display, choice_action.help or ""))
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

        if getattr(self, "examples", None):
            ex_table = Table.grid(padding=(0, 2))
            ex_table.add_column("cmd", style="bold cyan", no_wrap=True)
            ex_table.add_column("desc", style="default")
            for ex_cmd, ex_desc in self.examples:
                ex_table.add_row(ex_cmd, ex_desc)
            console.print(
                Panel(
                    ex_table,
                    title="[bold]Quick Examples[/bold]",
                    title_align="left",
                    border_style="dim",
                    box=box.ROUNDED,
                )
            )


def print_json(data: Any) -> None:
    """Print pure machine-readable JSON to stdout."""
    print(json.dumps(data, indent=2, default=str), file=sys.stdout)


_CONSOLE: Optional[Console] = None


def _get_console() -> Console:
    """Return a cached Rich console instance for stdout rendering."""
    global _CONSOLE
    if _CONSOLE is None:
        _CONSOLE = Console(highlight=False)
    return _CONSOLE


def print_table(
    title: str,
    columns: List[Tuple[str, Optional[str]]],
    rows: List[List[str]],
    caption: Optional[str] = None,
) -> None:
    """Render a clean Rich table to current stdout."""
    table = Table(
        title=f"[bold cyan]{title}[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold green",
        title_justify="left",
        caption=caption,
    )
    for col_name, style in columns:
        table.add_column(col_name, style=style or "none")

    for row in rows:
        table.add_row(*row)

    _get_console().print(table)


def print_success(msg: str) -> None:
    """Print a success notification to stdout."""
    print(f"[+] {msg}", file=sys.stdout)


def print_info(msg: str) -> None:
    """Print an informational notification to stdout."""
    print(f"[*] {msg}", file=sys.stdout)


def print_warning(msg: str) -> None:
    """Print a warning notification to stderr."""
    print(f"[!] {msg}", file=sys.stderr)


def print_error(msg: str) -> None:
    """Print an error notification to stderr."""
    print(f"[!] {msg}", file=sys.stderr)
