"""Unit tests for PreferencesStore deep module."""

import os
import stat
import tempfile

from cyguide.common.preferences import PreferencesStore


def test_preferences_store_memory_mode():
    """Verify in-memory preferences and scratchpad operation without disk writes."""
    prefs = PreferencesStore(db_path=":memory:")
    assert prefs.get("nonexistent", "default") == "default"

    prefs.set("editor_mode", "vim")
    assert prefs.get("editor_mode") == "vim"
    assert prefs.all()["editor_mode"] == "vim"

    # Scratchpad in-memory
    assert prefs.read_scratchpad() == ""
    prefs.write_scratchpad("Target IP: 10.10.10.5")
    assert prefs.read_scratchpad() == "Target IP: 10.10.10.5"


def test_preferences_store_disk_atomic_and_permissions():
    """Verify atomic persistence with 0o600 permissions for settings and scratchpad."""
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = os.path.join(tmpdir, "settings.json")
        scratchpad_path = os.path.join(tmpdir, "scratchpad.md")

        prefs = PreferencesStore(
            data_dir=tmpdir,
            settings_path=settings_path,
            scratchpad_path=scratchpad_path,
        )

        # 1. Test settings persistence
        prefs.update({"animations_enabled": False, "editor_mode": "emacs"})
        assert os.path.exists(settings_path)

        # Check permissions: 0o600 (-rw-------)
        mode = stat.S_IMODE(os.stat(settings_path).st_mode)
        assert mode == 0o600

        # Reload from new instance
        prefs2 = PreferencesStore(
            data_dir=tmpdir,
            settings_path=settings_path,
            scratchpad_path=scratchpad_path,
        )
        assert prefs2.get("animations_enabled") is False
        assert prefs2.get("editor_mode") == "emacs"

        # 2. Test scratchpad persistence
        prefs.write_scratchpad("# Operator Notes\nDiscovered open port 8080.")
        assert os.path.exists(scratchpad_path)

        # Check scratchpad permissions: 0o600
        pad_mode = stat.S_IMODE(os.stat(scratchpad_path).st_mode)
        assert pad_mode == 0o600

        assert prefs2.read_scratchpad() == "# Operator Notes\nDiscovered open port 8080."

        # 3. Test automatic backup creation on overwrite
        prefs.write_scratchpad("Updated notes")
        bak_path = f"{scratchpad_path}.bak"
        assert os.path.exists(bak_path)
        bak_mode = stat.S_IMODE(os.stat(bak_path).st_mode)
        assert bak_mode == 0o600
        with open(bak_path, "r", encoding="utf-8") as f:
            assert f.read() == "# Operator Notes\nDiscovered open port 8080."
        assert prefs.read_scratchpad() == "Updated notes"


def test_preferences_store_update_cache_and_flush():
    """Verify in-memory cache update without immediate disk write, followed by explicit flush."""
    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = os.path.join(tmpdir, "settings.json")
        prefs = PreferencesStore(data_dir=tmpdir, settings_path=settings_path)

        # Cache update only - file should not exist yet
        prefs.update_cache({"learning_sidebar_width": 28})
        assert prefs.get("learning_sidebar_width") == 28
        assert not os.path.exists(settings_path)

        # Flush to disk
        prefs.flush()
        assert os.path.exists(settings_path)
        prefs_reloaded = PreferencesStore(data_dir=tmpdir, settings_path=settings_path)
        assert prefs_reloaded.get("learning_sidebar_width") == 28
