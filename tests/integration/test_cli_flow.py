import asyncio
import io
import json
import os
import sys
from unittest.mock import patch

import pytest

from cyguide.cli import main
from cyguide.cli.context import EXIT_SUCCESS
from cyguide.engine.store import GraphStore
from cyguide.schemas.network import NetworkHost


def _run_cli_in_thread(args):
    """Executes main() with given sys.argv in a fresh thread to support asyncio.run()."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    exit_code = 0
    try:
        sys.stdout = captured_out
        sys.stderr = captured_err
        with patch.object(sys, "argv", args):
            code = main()
            if isinstance(code, int):
                exit_code = code
    except SystemExit as se:
        exit_code = se.code if isinstance(se.code, int) else 0
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    return captured_out.getvalue(), captured_err.getvalue(), exit_code


@pytest.mark.asyncio
async def test_cli_doctor_command(tmp_path):
    """Integration test: Running `cyg doctor` via CLI entrypoint."""
    test_args = ["cyg", "--db", str(tmp_path / "diag.db"), "doctor"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in stdout
    assert "SYSTEM" in stdout
    assert "DATABASE" in stdout
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_doctor_json_command(tmp_path):
    """Integration test: Running `cyg doctor --json` via CLI entrypoint."""
    test_args = ["cyg", "--db", str(tmp_path / "diag.db"), "doctor", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    data = json.loads(stdout)
    assert "checks" in data
    assert "system_info" in data
    assert "tool_counts" in data
    assert "healthy" in data
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_session_export_and_import_command(tmp_path):
    """Integration test: Running `cyg session export` and `cyg session import`."""
    # 1. Setup initial database with data
    src_db = tmp_path / "source.db"
    store = GraphStore(str(src_db))
    await store.initialize()
    ws_id, sess_id = await store.get_or_create_learning_sandbox()
    host = NetworkHost.create(ip="10.10.10.10", hostname="target-box")
    await store.upsert_finding(sess_id, host)
    await store.close()

    export_db = tmp_path / "exported.db"
    export_md = tmp_path / "exported.md"

    # 2. Test session export subcommand
    export_args = [
        "cyg",
        "--db",
        str(src_db),
        "session",
        "export",
        str(sess_id),
        str(export_db),
        "--report",
        str(export_md),
    ]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, export_args)

    assert "[+] Session database exported successfully" in stdout
    assert "[+] Markdown report exported successfully" in stdout
    assert export_db.exists()
    assert export_md.exists()
    assert oct(os.stat(export_md).st_mode & 0o777) == "0o600"
    assert code == EXIT_SUCCESS

    # 3. Test session import subcommand into a destination database
    dst_db = tmp_path / "destination.db"
    import_args = ["cyg", "--db", str(dst_db), "session", "import", str(export_db)]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, import_args)

    assert "imported successfully!" in stdout
    assert code == EXIT_SUCCESS

    # 4. Verify data in destination DB
    dst_store = GraphStore(str(dst_db))
    await dst_store.initialize()
    hosts = await dst_store.query("network.host", session_id=sess_id)
    assert len(hosts) == 1
    pik = json.loads(hosts[0]["pik_json"])
    assert "ip" in pik
    await dst_store.close()


@pytest.mark.asyncio
async def test_cli_session_list_and_delete(tmp_path):
    """Integration test: `cyg session list` and `cyg session delete`."""
    db_path = tmp_path / "sessions.db"
    store = GraphStore(str(db_path))
    await store.initialize()
    ws_id, sess_id = await store.get_or_create_learning_sandbox()
    await store.close()

    # List sessions in JSON
    list_args = ["cyg", "--db", str(db_path), "session", "list", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, list_args)
    assert code == EXIT_SUCCESS
    data = json.loads(stdout)
    assert any(s["id"] == str(sess_id) for s in data)

    # Delete session
    del_args = ["cyg", "--db", str(db_path), "session", "delete", str(sess_id), "--force"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, del_args)
    assert code == EXIT_SUCCESS
    assert "[+] Session" in stdout and "deleted successfully" in stdout


@pytest.mark.asyncio
async def test_cli_workspace_crud(tmp_path):
    """Integration test: `cyg workspace create`, `list`, and `delete`."""
    db_path = tmp_path / "ws.db"

    # Create workspace
    create_args = ["cyg", "--db", str(db_path), "workspace", "create", "Engagement-Alpha", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, create_args)
    assert code == EXIT_SUCCESS
    created_ws = json.loads(stdout)
    assert created_ws["name"] == "Engagement-Alpha"
    ws_id = created_ws["id"]

    # List workspaces
    list_args = ["cyg", "--db", str(db_path), "workspace", "list", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, list_args)
    assert code == EXIT_SUCCESS
    workspaces = json.loads(stdout)
    assert any(w["name"] == "Engagement-Alpha" for w in workspaces)

    # Delete workspace by Name
    del_args = ["cyg", "--db", str(db_path), "workspace", "delete", "Engagement-Alpha", "--force"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, del_args)
    assert code == EXIT_SUCCESS
    assert "[+] Workspace 'Engagement-Alpha'" in stdout


@pytest.mark.asyncio
async def test_cli_bare_subcommand_shows_help():
    """Integration test: `cyg session` without an action automatically displays help."""
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, ["cyg", "session"])
    assert "Usage: cyg session [OPTIONS] [COMMAND]" in stdout
    assert "Quick Examples" in stdout
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_tool_commands(tmp_path):
    """Integration test: `cyg tool list`, `check`, and `info`."""
    # Tool list
    list_args = ["cyg", "tool", "list", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, list_args)
    assert code == EXIT_SUCCESS
    tools = json.loads(stdout)
    assert any(t["name"] == "nmap" for t in tools)
    assert any(t["name"] == "dnspython" for t in tools)

    # Tool info
    info_args = ["cyg", "tool", "info", "nmap", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, info_args)
    assert code == EXIT_SUCCESS
    nmap_info = json.loads(stdout)
    assert nmap_info["name"] == "nmap"
    assert "recipes" in nmap_info

    # Tool check for dnspython (built-in python tool, always installed)
    check_args = ["cyg", "tool", "check", "dnspython", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, check_args)
    assert code == EXIT_SUCCESS
    check_data = json.loads(stdout)
    assert check_data["all_installed"] is True


@pytest.mark.asyncio
async def test_cli_lab_commands(tmp_path, monkeypatch):
    """Integration test: `cyg lab list`, `save`, and `load`."""
    test_dir = str(tmp_path / "lab_data")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", test_dir)

    # 1. Save lab checkpoint
    save_args = [
        "cyg",
        "--data-dir",
        test_dir,
        "lab",
        "save",
        "checkpoint_test",
        "--target",
        "10.10.10.50",
        "--notes",
        "Test Notes Content",
    ]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, save_args)
    assert code == EXIT_SUCCESS
    assert "checkpoint saved to:" in stdout

    # 2. List checkpoints
    list_args = ["cyg", "--data-dir", test_dir, "lab", "list", "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, list_args)
    assert code == EXIT_SUCCESS
    checkpoints = json.loads(stdout)
    assert len(checkpoints) >= 1
    assert checkpoints[0]["primary_target"] == "10.10.10.50"

    # 3. Load checkpoint
    cp_path = checkpoints[0]["path"]
    load_args = ["cyg", "--data-dir", test_dir, "lab", "load", cp_path, "--json"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, load_args)
    assert code == EXIT_SUCCESS
    meta = json.loads(stdout)
    assert meta["target"] == "10.10.10.50"
    assert meta["notes"] == "Test Notes Content"

    # 4. Reset sandbox
    reset_args = ["cyg", "--data-dir", test_dir, "lab", "reset", "--force"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, reset_args)
    assert code == EXIT_SUCCESS
    assert "Learning sandbox reset successfully" in stdout


@pytest.mark.asyncio
async def test_cli_doctor_default_uniform_db(tmp_path, monkeypatch):
    """Integration test: Running `cyg doctor` without --db defaults to uniform data directory."""
    test_dir = str(tmp_path / "cli_uniform")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", test_dir)

    test_args = ["cyg", "doctor"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in stdout
    assert "DATABASE" in stdout
    assert os.path.exists(os.path.join(test_dir, "cyguide.db"))
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_data_dir_flag(tmp_path):
    """Integration test: Running `cyg --data-dir <path> doctor` sets custom uniform directory."""
    custom_dir = str(tmp_path / "explicit_data_dir")
    test_args = ["cyg", "--data-dir", custom_dir, "doctor"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in stdout
    assert os.path.exists(os.path.join(custom_dir, "cyguide.db"))
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_version_flag():
    """Integration test: Running `cyg --version` outputs version string."""
    from cyguide import __version__

    test_args = ["cyg", "--version"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)
    assert f"CyGuide {__version__}" in stdout


@pytest.mark.asyncio
async def test_cli_rich_help_output():
    """Integration test: Running `cyg --help` renders Rich panels and usage."""
    test_args = ["cyg", "--help"]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "Usage: cyg [OPTIONS] [COMMAND]" in stdout
    assert "Options" in stdout
    assert "Commands" in stdout
    assert "session" in stdout
    assert "workspace" in stdout
    assert "tool" in stdout
    assert "doctor" in stdout
    assert "lab" in stdout


@pytest.mark.asyncio
async def test_cli_subcommand_flag_after_subcommand(tmp_path):
    """Integration test: Subcommand inherits global options placed AFTER subcommand."""
    custom_db = str(tmp_path / "after_subcommand.db")
    test_args = ["cyg", "doctor", "--db", custom_db]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in stdout
    assert os.path.exists(custom_db)
    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_cli_session_export_report_only(tmp_path):
    """Integration test: `cyg session export <session_id> --report <path>` works without output DB."""
    src_db = tmp_path / "export_src.db"
    store = GraphStore(str(src_db))
    await store.initialize()
    _ws_id, sess_id = await store.get_or_create_learning_sandbox()
    host = NetworkHost.create(ip="10.10.10.20", hostname="report-target")
    await store.upsert_finding(sess_id, host)
    await store.close()

    report_md = tmp_path / "report_only.md"
    test_args = [
        "cyg",
        "--db",
        str(src_db),
        "session",
        "export",
        str(sess_id),
        "--report",
        str(report_md),
    ]
    stdout, stderr, code = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "[+] Markdown report exported successfully" in stdout
    assert report_md.exists()
    assert code == EXIT_SUCCESS
