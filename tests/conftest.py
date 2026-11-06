"""Pytest configuration and global fixtures for CyGuide."""

import pytest


@pytest.fixture(autouse=True)
def isolate_cyguide_data_dir(tmp_path, monkeypatch):
    """Automatically isolate all tests to an isolated temporary CYGUIDE_DATA_DIR.

    This ensures test runs never alter or pollute the user's real ~/.cyguide directory.
    """
    test_data_dir = str(tmp_path / ".cyguide_test")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", test_data_dir)
    return test_data_dir
