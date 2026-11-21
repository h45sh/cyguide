"""Centralized diagnostic logging, flight recorder breadcrumbs, and crash trap monitoring for CyGuide.

Provides:
1. Secure Rotating File Logging: ~/.cyguide/logs/cyguide.log created atomically with mode 0o600.
2. Sanitizing Formatter: Automatic redaction of operator API keys, passwords, and private keys.
3. In-Memory Flight Recorder: Bounded ring buffer of recent application state breadcrumbs.
4. Triple-Point Exception Traps: Intercepts Python unhandled exceptions, asyncio task errors,
   and Textual App crashes/panics before terminal resets.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import re
import sys
import threading
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from cyguide.paths import get_default_logs_dir, get_system_log_path

logger = logging.getLogger("cyguide")

# Sensitive token redaction regex patterns
REDACT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|auth)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?"), r"\1=***REDACTED***"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{15,}"), "Bearer ***REDACTED***"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-***REDACTED***"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_***REDACTED***"),
    (re.compile(r"://([^:]+):([^@]+)@"), r"://\1:***@"),
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----"), "-----BEGIN PRIVATE KEY----- [***REDACTED***] -----END PRIVATE KEY-----"),
]


class SecureRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that guarantees atomic 0o600 permissions upon file creation

    to prevent TOCTOU permission races and secret leakage.
    """

    def _open(self):
        # Guarantee parent directory exists with 0o700 permissions
        dirname = os.path.dirname(self.baseFilename)
        if dirname:
            try:
                os.makedirs(dirname, mode=0o700, exist_ok=True)
            except OSError:
                pass

        # Open file atomically with restricted permissions (0o600: user read/write only)
        fd = os.open(
            self.baseFilename,
            os.O_CREAT | os.O_WRONLY | os.O_APPEND,
            0o600,
        )
        return open(fd, self.mode, encoding=self.encoding)

    def doRollover(self) -> None:
        """Perform rollover while strictly preserving 0o600 permissions on all rotated log files."""
        super().doRollover()
        # Enforce 0o600 on current file if recreated
        if os.path.exists(self.baseFilename):
            try:
                os.chmod(self.baseFilename, 0o600)
            except OSError:
                pass


class SanitizingLogFormatter(logging.Formatter):
    """Log formatter that automatically scrubs sensitive credentials, tokens, and keys."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        for pattern, replacement in REDACT_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        return formatted


@dataclass
class Breadcrumb:
    """Lightweight operational state breadcrumb recorded in memory."""

    timestamp: str
    category: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def format_line(self) -> str:
        meta_str = f" | {self.metadata}" if self.metadata else ""
        return f"[{self.timestamp}] [{self.category.upper()}] {self.message}{meta_str}"


class FlightRecorder:
    """In-memory bounded ring buffer recording recent UI state transitions, command executions,

    and async lifecycle events for forensic post-mortem analysis during unexpected crashes.
    """

    _instance: Optional[FlightRecorder] = None

    def __init__(self, maxlen: int = 200) -> None:
        self._buffer: deque[Breadcrumb] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> FlightRecorder:
        if cls._instance is None:
            cls._instance = FlightRecorder()
        return cls._instance

    def record(self, category: str, message: str, **metadata: Any) -> None:
        """Record an operational breadcrumb into the bounded buffer."""
        # Sanitize metadata string values to avoid storing plain secrets
        safe_meta = {}
        for k, v in metadata.items():
            if isinstance(v, str):
                for pattern, replacement in REDACT_PATTERNS:
                    v = pattern.sub(replacement, v)
            safe_meta[k] = v

        crumb = Breadcrumb(
            timestamp=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            category=category,
            message=message,
            metadata=safe_meta,
        )
        with self._lock:
            self._buffer.append(crumb)

    def get_breadcrumbs(self, limit: int = 50) -> List[Breadcrumb]:
        """Return the most recent breadcrumbs up to limit."""
        with self._lock:
            crumbs = list(self._buffer)
        return crumbs[-limit:] if limit > 0 else crumbs

    def format_breadcrumbs(self, limit: int = 50) -> str:
        """Format recent breadcrumbs as a clean text block."""
        crumbs = self.get_breadcrumbs(limit=limit)
        if not crumbs:
            return "No recorded flight breadcrumbs."
        lines = [c.format_line() for c in crumbs]
        return "\n".join(lines)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


def record_breadcrumb(category: str, message: str, **metadata: Any) -> None:
    """Global convenience helper to record an operational breadcrumb in memory and log to file."""
    FlightRecorder.get_instance().record(category, message, **metadata)
    meta_str = f" | {metadata}" if metadata else ""
    logger.info("[%s] %s%s", category.upper(), message, meta_str)


_LOGGING_INITIALIZED = False
_ORIGINAL_EXCEPTHOOK: Optional[Callable] = None
_ORIGINAL_THREADING_EXCEPTHOOK: Optional[Callable] = None


def setup_system_logging(
    data_dir: Optional[str] = None,
    verbose: bool = False,
    log_to_stderr: bool = False,
    force: bool = False,
) -> logging.Logger:
    """Configure system-wide centralized application logging to ~/.cyguide/logs/cyguide.log.

    Guarantees atomic 0o600 permissions, log rotation (5MB cap, 3 backups),
    and credential sanitization.
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED and not force:
        return logger

    # Ensure log directory exists
    get_default_logs_dir(data_dir)
    log_file_path = get_system_log_path(data_dir)

    log_level = logging.DEBUG if (verbose or os.environ.get("CYGUIDE_DEBUG")) else logging.INFO
    logger.setLevel(log_level)

    # Avoid duplicate handlers if re-called
    for h in list(logger.handlers):
        h.close()
    logger.handlers.clear()

    formatter = SanitizingLogFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Secure rotating file handler
    file_handler = SecureRotatingFileHandler(
        filename=log_file_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. Optional stderr stream handler (e.g. for CLI verbose mode)
    if log_to_stderr:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(log_level)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)

    # Prevent propagation to root logger unless desired
    logger.propagate = False

    _LOGGING_INITIALIZED = True
    try:
        from cyguide import __version__

        ver_str = f"v{__version__}"
    except Exception:
        ver_str = "unknown"

    logger.info(
        "CyGuide centralized logging initialized (%s, pid=%d, log=%s)",
        ver_str,
        os.getpid(),
        log_file_path,
    )
    record_breadcrumb(
        "system",
        "Flight recorder active",
        log_path=log_file_path,
        level=logging.getLevelName(log_level),
    )
    for h in logger.handlers:
        h.flush()
    return logger


def install_global_exception_traps(loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    """Install global crash hooks into sys.excepthook, threading.excepthook, and asyncio loop."""
    global _ORIGINAL_EXCEPTHOOK, _ORIGINAL_THREADING_EXCEPTHOOK

    def _global_excepthook(exc_type, exc_value, exc_traceback):
        # Ignore normal process exits and keyboard interrupts
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            if _ORIGINAL_EXCEPTHOOK:
                _ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
            else:
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(35)
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        logger.critical(
            "FATAL UNHANDLED EXCEPTION ESCAPED TO PYTHON INTERPRETER:\n"
            "%s\n"
            "=== FLIGHT RECORDER BREADCRUMBS ===\n"
            "%s\n"
            "====================================",
            tb_str.strip(),
            breadcrumbs,
        )

        for handler in logger.handlers:
            handler.flush()

        if _ORIGINAL_EXCEPTHOOK:
            _ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
        else:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    if _ORIGINAL_EXCEPTHOOK is None:
        _ORIGINAL_EXCEPTHOOK = sys.excepthook
        sys.excepthook = _global_excepthook

    def _threading_excepthook(args):
        if issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
            return

        breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(35)
        tb_str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))

        logger.critical(
            "FATAL UNHANDLED EXCEPTION IN BACKGROUND THREAD '%s':\n"
            "%s\n"
            "=== FLIGHT RECORDER BREADCRUMBS ===\n"
            "%s\n"
            "====================================",
            args.thread.name if args.thread else "Unknown",
            tb_str.strip(),
            breadcrumbs,
        )

        for handler in logger.handlers:
            handler.flush()

        if _ORIGINAL_THREADING_EXCEPTHOOK:
            _ORIGINAL_THREADING_EXCEPTHOOK(args)

    if hasattr(threading, "excepthook") and _ORIGINAL_THREADING_EXCEPTHOOK is None:
        _ORIGINAL_THREADING_EXCEPTHOOK = threading.excepthook
        threading.excepthook = _threading_excepthook

    if loop is not None:
        _attach_asyncio_exception_handler(loop)


def _attach_asyncio_exception_handler(loop: asyncio.AbstractEventLoop) -> None:
    """Attach defensive crash logger to asyncio event loop."""
    orig_handler = loop.get_exception_handler()

    def _async_exception_handler(current_loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
        exc = context.get("exception")
        msg = context.get("message", "Unhandled asyncio event loop exception")

        # Suppress noise from expected normal task cancellations during shutdown
        if isinstance(exc, asyncio.CancelledError):
            logger.debug("Asyncio task was cancelled: %s", msg)
            return

        breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(35)
        tb_str = ""
        if exc is not None:
            tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        logger.error(
            "UNHANDLED ASYNCIO EXCEPTION IN EVENT LOOP: %s\n"
            "%s\n"
            "=== FLIGHT RECORDER BREADCRUMBS ===\n"
            "%s\n"
            "====================================",
            msg,
            tb_str.strip() if tb_str else f"Context: {context}",
            breadcrumbs,
        )

        for handler in logger.handlers:
            handler.flush()

        if orig_handler:
            orig_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(_async_exception_handler)


def install_textual_crash_traps(app_class: Any) -> None:
    """Install diagnostic crash recording on Textual App without performing raw disk I/O.

    All recording flows through logger and FlightRecorder.
    """
    orig_handle_exception = getattr(app_class, "_handle_exception", None)
    if orig_handle_exception and not getattr(app_class, "_cyguide_trap_installed", False):

        def logging_handle_exception(self: Any, error: Exception) -> None:
            # Capture UI contextual state
            screen_name = getattr(getattr(self, "screen", None), "__class__", type).__name__
            focused_name = getattr(getattr(self, "focused", None), "__class__", type).__name__
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(35)

            logger.critical(
                "TEXTUAL UI COMPONENT CRASH ENCOUNTERED:\n"
                "Screen: %s | Focused Widget: %s\n"
                "%s\n"
                "=== FLIGHT RECORDER BREADCRUMBS ===\n"
                "%s\n"
                "====================================",
                screen_name,
                focused_name,
                tb_str.strip(),
                breadcrumbs,
            )

            for handler in logger.handlers:
                handler.flush()

            return orig_handle_exception(self, error)

        app_class._handle_exception = logging_handle_exception

        orig_panic = getattr(app_class, "panic", None)
        if orig_panic:

            def logging_panic(self: Any, *renderables: Any) -> None:
                breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(35)
                logger.critical(
                    "TEXTUAL UI PANIC INVOKED:\n"
                    "Renderables: %s\n"
                    "=== FLIGHT RECORDER BREADCRUMBS ===\n"
                    "%s\n"
                    "====================================",
                    renderables,
                    breadcrumbs,
                )
                for handler in logger.handlers:
                    handler.flush()
                return orig_panic(self, *renderables)

            app_class.panic = logging_panic

        orig_exit = getattr(app_class, "exit", None)
        if orig_exit:

            def logging_exit(
                self: Any, result: Any = None, return_code: int = 0, message: Any = None
            ) -> None:
                if return_code != 0:
                    breadcrumbs = FlightRecorder.get_instance().format_breadcrumbs(20)
                    logger.warning(
                        "Textual App exiting with non-zero return code %d (message: %s)\n%s",
                        return_code,
                        message,
                        breadcrumbs,
                    )
                else:
                    record_breadcrumb("system", "Textual App normal exit", return_code=return_code)
                return orig_exit(self, result=result, return_code=return_code, message=message)

            app_class.exit = logging_exit

        app_class._cyguide_trap_installed = True


def get_recent_crash_summary(data_dir: Optional[str] = None, max_lines: int = 150) -> Optional[Dict[str, Any]]:
    """Scan ~/.cyguide/logs/cyguide.log for the most recent critical crash traceback block.

    Returns structured summary if found, or None.
    """
    log_path = get_system_log_path(data_dir)
    if not os.path.exists(log_path):
        return None

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Read last chunk
            f.seek(0, os.SEEK_END)
            size = f.tell()
            chunk_size = min(size, 65536)
            f.seek(size - chunk_size)
            lines = f.readlines()
    except Exception:
        return None

    crash_marker_indices = [
        i
        for i, l in enumerate(lines)
        if "FATAL UNHANDLED EXCEPTION" in l or "TEXTUAL UI COMPONENT CRASH" in l or "TEXTUAL UI PANIC" in l
    ]

    if not crash_marker_indices:
        return None

    latest_idx = crash_marker_indices[-1]
    crash_block = lines[latest_idx : latest_idx + 60]

    # Extract timestamp from the marker line
    marker_line = lines[latest_idx]
    timestamp_match = re.match(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})", marker_line)
    timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"

    return {
        "timestamp": timestamp,
        "summary": marker_line.strip(),
        "block": "".join(crash_block).strip(),
    }
