"""Unit tests for CyGuide centralized path resolution."""

import os

from cyguide.app import CyGuideApp
from cyguide.paths import (
    get_action_log_path,
    get_default_data_dir,
    get_default_db_path,
    get_default_exports_dir,
    get_default_logs_dir,
    get_default_reports_dir,
    get_default_scratchpad_path,
    get_default_settings_path,
)


def test_get_default_data_dir_env_override(tmp_path, monkeypatch):
    """Verify CYGUIDE_DATA_DIR environment variable overrides default location."""
    custom_dir = str(tmp_path / "custom_data_dir")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", custom_dir)

    resolved = get_default_data_dir()
    assert resolved == os.path.abspath(custom_dir)
    assert os.path.isdir(resolved)


def test_get_default_data_dir_default(monkeypatch):
    """Verify fallback to ~/.cyguide when environment variable is not set."""
    monkeypatch.delenv("CYGUIDE_DATA_DIR", raising=False)
    resolved = get_default_data_dir()
    expected = os.path.abspath(os.path.expanduser("~/.cyguide"))
    assert resolved == expected


def test_subpaths_resolution(tmp_path):
    """Verify standard filenames for db, settings, scratchpad, exports, and reports."""
    data_dir = str(tmp_path / "app_data")

    db_path = get_default_db_path(data_dir)
    assert db_path == os.path.join(data_dir, "cyguide.db")

    settings_path = get_default_settings_path(data_dir)
    assert settings_path == os.path.join(data_dir, "settings.json")

    scratchpad_path = get_default_scratchpad_path(data_dir)
    assert scratchpad_path == os.path.join(data_dir, "scratchpad.md")

    exports_dir = get_default_exports_dir(data_dir)
    assert exports_dir == os.path.join(data_dir, "exports")
    assert os.path.isdir(exports_dir)

    reports_dir = get_default_reports_dir(data_dir)
    assert reports_dir == os.path.join(data_dir, "reports")
    assert os.path.isdir(reports_dir)

    logs_dir = get_default_logs_dir(data_dir)
    assert logs_dir == os.path.join(data_dir, "logs")
    assert os.path.isdir(logs_dir)

    log_path = get_action_log_path("act-1234", data_dir)
    assert log_path == os.path.join(logs_dir, "act-1234.log")


def test_app_uses_uniform_paths(tmp_path):
    """Verify CyGuideApp initializes uniform database, scratchpad, exports, and reports paths."""
    data_dir = str(tmp_path / "uniform_dir")
    app = CyGuideApp(data_dir=data_dir)

    assert app.db_path == os.path.join(data_dir, "cyguide.db")
    assert app.get_scratchpad_path() == os.path.join(data_dir, "scratchpad.md")
    assert app.get_exports_dir() == os.path.join(data_dir, "exports")
    assert app.get_reports_dir() == os.path.join(data_dir, "reports")


def test_app_custom_db_path_scopes_subpaths(tmp_path):
    """Verify custom db_path scopes scratchpad, exports, and reports to custom folder."""
    custom_dir = tmp_path / "custom_engagement"
    custom_dir.mkdir()
    custom_db = str(custom_dir / "engagement.db")

    app = CyGuideApp(db_path=custom_db)
    assert app.db_path == custom_db
    assert app.get_scratchpad_path() == str(custom_dir / "scratchpad.md")
    assert app.get_exports_dir() == str(custom_dir / "exports")
    assert app.get_reports_dir() == str(custom_dir / "reports")


def test_app_memory_db_handling(tmp_path):
    """Verify :memory: database handles paths gracefully and scopes to data_dir."""
    app = CyGuideApp(db_path=":memory:", data_dir=str(tmp_path))
    assert app.db_path == ":memory:"
    assert app.get_scratchpad_path() == ":memory:"
    assert app._get_settings_path() is None
    assert app.get_exports_dir() == str(tmp_path / "exports")
    assert app.get_reports_dir() == str(tmp_path / "reports")


def test_get_git_branch_standard_repo(tmp_path):
    """Verify get_git_branch resolves branch name from .git/HEAD."""
    from cyguide.paths import get_git_branch

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/feat/test-branch\n")

    branch = get_git_branch(str(tmp_path))
    assert branch == "feat/test-branch"


def test_get_git_branch_worktree(tmp_path):
    """Verify get_git_branch resolves branch name from worktree gitdir pointer."""
    from cyguide.paths import get_git_branch

    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    actual_git_dir = tmp_path / "main_repo" / ".git" / "worktrees" / "wt1"
    actual_git_dir.mkdir(parents=True)
    (actual_git_dir / "HEAD").write_text("ref: refs/heads/worktree-branch\n")

    (worktree_dir / ".git").write_text(f"gitdir: {actual_git_dir}\n")

    branch = get_git_branch(str(worktree_dir))
    assert branch == "worktree-branch"


def test_get_git_branch_no_repo(tmp_path):
    """Verify get_git_branch returns empty string when not in a git repo."""
    from cyguide.paths import get_git_branch

    empty_dir = tmp_path / "no_git"
    empty_dir.mkdir()

    branch = get_git_branch(str(empty_dir))
    assert branch == ""
