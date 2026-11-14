"""Deep module managing persistent user settings, active API keys, and operator scratchpad."""

import json
import os
from typing import Any, Dict, Optional

from cyguide.paths import (
    get_default_data_dir,
    get_default_db_path,
    get_default_scratchpad_path,
    get_default_settings_path,
)


class PreferencesStore:
    """The deep module managing persistent settings, API key profiles, and scratchpad note-taking."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        settings_path: Optional[str] = None,
        scratchpad_path: Optional[str] = None,
        db_path: Optional[str] = None,
        initial_settings: Optional[Dict[str, Any]] = None,
    ):
        self.data_dir = data_dir or get_default_data_dir()
        self.db_path = db_path
        self._settings_path = settings_path
        self._scratchpad_path = scratchpad_path

        # In-memory storage cache
        self._cache: Dict[str, Any] = initial_settings.copy() if initial_settings else {}
        self._load()

    def _resolve_settings_path(self) -> Optional[str]:
        if self._settings_path:
            return self._settings_path
        if self.db_path == ":memory:":
            return None
        if self.db_path and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_settings_path(self.data_dir)
            base_dir = os.path.dirname(os.path.abspath(self.db_path))
            return os.path.join(base_dir, "settings.json")
        return get_default_settings_path(self.data_dir)

    def _resolve_scratchpad_path(self) -> str:
        if self._scratchpad_path:
            return self._scratchpad_path
        if self.db_path == ":memory:":
            return ":memory:"
        if self.db_path and self.data_dir:
            default_db = get_default_db_path(self.data_dir)
            if os.path.abspath(self.db_path) == os.path.abspath(default_db):
                return get_default_scratchpad_path(self.data_dir)
            base_dir = os.path.dirname(os.path.abspath(self.db_path))
            return os.path.join(base_dir, "scratchpad.md")
        return get_default_scratchpad_path(self.data_dir)

    def _load(self) -> None:
        path = self._resolve_settings_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache.update(data)
            except Exception:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch a setting value by key."""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a single setting and persist atomically."""
        self.update({key: value})

    def update(self, updates: Dict[str, Any]) -> None:
        """Batch update settings and persist with atomic 0o600 file permissions."""
        self._cache.update(updates)
        path = self._resolve_settings_path()
        if not path or path == ":memory:":
            return

        try:
            base_dir = os.path.dirname(os.path.abspath(path))
            if base_dir:
                os.makedirs(base_dir, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "w", encoding="utf-8", closefd=False) as f:
                    json.dump(self._cache, f, indent=2)
            finally:
                os.close(fd)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            pass

    def all(self) -> Dict[str, Any]:
        """Return a copy of all current settings."""
        return dict(self._cache)

    def read_scratchpad(self) -> str:
        """Read operator scratchpad contents."""
        path = self._resolve_scratchpad_path()
        if not path or path == ":memory:":
            return self._cache.get("_memory_scratchpad", "")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    def write_scratchpad(self, content: str) -> None:
        """Atomically persist operator notes with 0o600 permissions."""
        path = self._resolve_scratchpad_path()
        if not path or path == ":memory:":
            self._cache["_memory_scratchpad"] = content
            return

        try:
            base_dir = os.path.dirname(os.path.abspath(path))
            if base_dir:
                os.makedirs(base_dir, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "w", encoding="utf-8", closefd=False) as f:
                    f.write(content)
            finally:
                os.close(fd)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            pass
