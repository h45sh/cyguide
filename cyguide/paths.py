"""Centralized path resolution and data directory management for CyGuide."""

import os
from typing import Optional

ENV_DATA_DIR = "CYGUIDE_DATA_DIR"
DEFAULT_DATA_DIR_NAME = ".cyguide"


def get_default_data_dir() -> str:
    """Return the absolute path to the CyGuide unified data directory.

    Priority:
    1. CYGUIDE_DATA_DIR environment variable
    2. ~/.cyguide directory in user's home folder
    """
    env_dir = os.environ.get(ENV_DATA_DIR)
    if env_dir:
        base_dir = os.path.abspath(os.path.expanduser(env_dir))
    else:
        base_dir = os.path.abspath(os.path.expanduser(f"~/{DEFAULT_DATA_DIR_NAME}"))

    try:
        os.makedirs(base_dir, mode=0o700, exist_ok=True)
    except OSError:
        pass
    return base_dir


def get_default_db_path(data_dir: Optional[str] = None) -> str:
    """Return the default SQLite database path."""
    base = data_dir if data_dir is not None else get_default_data_dir()
    return os.path.join(base, "cyguide.db")


def get_default_settings_path(data_dir: Optional[str] = None) -> str:
    """Return the default settings.json path."""
    base = data_dir if data_dir is not None else get_default_data_dir()
    return os.path.join(base, "settings.json")


def get_default_scratchpad_path(data_dir: Optional[str] = None) -> str:
    """Return the default scratchpad markdown file path."""
    base = data_dir if data_dir is not None else get_default_data_dir()
    return os.path.join(base, "scratchpad.md")


def get_default_exports_dir(data_dir: Optional[str] = None) -> str:
    """Return the default session database export directory."""
    base = data_dir if data_dir is not None else get_default_data_dir()
    exports_dir = os.path.join(base, "exports")
    try:
        os.makedirs(exports_dir, mode=0o700, exist_ok=True)
    except OSError:
        pass
    return exports_dir


def get_default_reports_dir(data_dir: Optional[str] = None) -> str:
    """Return the default session markdown report export directory."""
    base = data_dir if data_dir is not None else get_default_data_dir()
    reports_dir = os.path.join(base, "reports")
    try:
        os.makedirs(reports_dir, mode=0o700, exist_ok=True)
    except OSError:
        pass
    return reports_dir
