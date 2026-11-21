"""Centralized diagnostic logs inspection CLI command handler."""

import os
from typing import Any

from cyguide.cli.context import EXIT_SUCCESS, CliContext
from cyguide.cli.formatters import print_error, print_info, print_json, print_success
from cyguide.common.logging import get_recent_crash_summary
from cyguide.paths import get_system_log_path


def handle_logs(args: Any, context: CliContext) -> int:
    """Inspect, filter, or clear centralized application logs (~/.cyguide/logs/cyguide.log)."""
    log_path = get_system_log_path(context.data_dir)

    # 1. Clear action
    if getattr(args, "clear", False):
        if os.path.exists(log_path):
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
                print_success(f"System log cleared: {log_path}")
            except OSError as exc:
                print_error(f"Failed to clear system log: {exc}")
                return 1
        else:
            print_info(f"Log file does not exist: {log_path}")
        return EXIT_SUCCESS

    if not os.path.exists(log_path):
        if context.is_json:
            print_json({"log_path": log_path, "exists": False, "lines": []})
        else:
            print_info(f"No system log file found at: {log_path}")
        return EXIT_SUCCESS

    # 2. Crashes only filter
    if getattr(args, "crashes", False):
        crash = get_recent_crash_summary(context.data_dir)
        if context.is_json:
            print_json({"log_path": log_path, "crash": crash})
        else:
            if crash:
                print_info(f"Recent crash detected [{crash['timestamp']}]:")
                print(crash["block"])
            else:
                print_success("No crash signatures or fatal exceptions found in system log.")
        return EXIT_SUCCESS

    # 3. Read last N lines
    lines_count = getattr(args, "lines", 50) or 50
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines_count:] if lines_count > 0 else all_lines
    except OSError as exc:
        print_error(f"Failed to read system log: {exc}")
        return 1

    if context.is_json:
        print_json({
            "log_path": log_path,
            "total_lines": len(all_lines),
            "lines": [l.rstrip("\r\n") for l in tail_lines],
        })
    else:
        print_info(f"=== Last {len(tail_lines)} lines from {log_path} ===")
        for line in tail_lines:
            print(line, end="")
        if not tail_lines:
            print("[Empty log file]")

    return EXIT_SUCCESS
