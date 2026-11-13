import asyncio
import io
import json
import os
import sys
from unittest.mock import patch

import pytest

from cyguide.engine.store import GraphStore
from cyguide.main import main
from cyguide.schemas.network import NetworkHost


def _run_cli_in_thread(args):
    """Executes main() with given sys.argv in a fresh thread to support asyncio.run()."""
    old_stdout = sys.stdout
    captured_out = io.StringIO()
    try:
        sys.stdout = captured_out
        with patch.object(sys, "argv", args):
            main()
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout
    return captured_out.getvalue()


@pytest.mark.asyncio
async def test_cli_check_command(tmp_path):
    """Integration test: Running `cyg check` via CLI entrypoint."""
    test_args = ["cyg", "--db", str(tmp_path / "diag.db"), "check"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in output
    assert "SYSTEM" in output
    assert "DATABASE" in output


@pytest.mark.asyncio
async def test_cli_check_json_command(tmp_path):
    """Integration test: Running `cyg check --json` via CLI entrypoint."""
    test_args = ["cyg", "--db", str(tmp_path / "diag.db"), "check", "--json"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    data = json.loads(output)
    assert "checks" in data
    assert "system_info" in data
    assert "tool_counts" in data
    assert "healthy" in data


@pytest.mark.asyncio
async def test_cli_export_and_import_command(tmp_path):
    """Integration test: Running `cyg export` and `cyg import` via CLI entrypoint."""
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

    # 2. Test export subcommand
    export_args = [
        "cyg",
        "--db",
        str(src_db),
        "export",
        str(sess_id),
        str(export_db),
        "--report",
        str(export_md),
    ]
    export_out = await asyncio.to_thread(_run_cli_in_thread, export_args)

    assert "[+] Session database exported successfully" in export_out
    assert "[+] Markdown report exported successfully" in export_out
    assert export_db.exists()
    assert export_md.exists()
    assert oct(os.stat(export_md).st_mode & 0o777) == "0o600"

    # 3. Test import subcommand into a destination database
    dst_db = tmp_path / "destination.db"
    import_args = ["cyg", "--db", str(dst_db), "import", str(export_db)]
    import_out = await asyncio.to_thread(_run_cli_in_thread, import_args)

    assert "[+] Session imported successfully!" in import_out

    # 4. Verify data in destination DB
    dst_store = GraphStore(str(dst_db))
    await dst_store.initialize()
    hosts = await dst_store.query("network.host", session_id=sess_id)
    assert len(hosts) == 1
    pik = json.loads(hosts[0]["pik_json"])
    assert "ip" in pik
    await dst_store.close()


@pytest.mark.asyncio
async def test_cli_check_default_uniform_db(tmp_path, monkeypatch):
    """Integration test: Running `cyg check` without --db defaults to uniform data directory."""
    test_dir = str(tmp_path / "cli_uniform")
    monkeypatch.setenv("CYGUIDE_DATA_DIR", test_dir)

    test_args = ["cyg", "check"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in output
    assert "DATABASE" in output
    # Verify the database was created in the uniform directory
    assert os.path.exists(os.path.join(test_dir, "cyguide.db"))


@pytest.mark.asyncio
async def test_cli_data_dir_flag(tmp_path):
    """Integration test: Running `cyg --data-dir <path> check` sets custom uniform directory."""
    custom_dir = str(tmp_path / "explicit_data_dir")
    test_args = ["cyg", "--data-dir", custom_dir, "check"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in output
    assert os.path.exists(os.path.join(custom_dir, "cyguide.db"))


@pytest.mark.asyncio
async def test_cli_version_flag():
    """Integration test: Running `cyg --version` outputs version string."""
    from cyguide import __version__

    test_args = ["cyg", "--version"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)
    assert f"CyGuide {__version__}" in output


@pytest.mark.asyncio
async def test_cli_rich_help_output():
    """Integration test: Running `cyg --help` renders Rich panels and usage."""
    test_args = ["cyg", "--help"]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "Usage: cyg [OPTIONS] [COMMAND]" in output
    assert "Options" in output
    assert "Commands" in output
    assert "--ollama-model" in output
    assert "--offline" in output


@pytest.mark.asyncio
async def test_cli_subcommand_flag_after_subcommand(tmp_path):
    """Integration test: Subcommand inherits global options placed AFTER subcommand."""
    custom_db = str(tmp_path / "after_subcommand.db")
    # Notice --db is placed AFTER check
    test_args = ["cyg", "check", "--db", custom_db]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in output
    assert os.path.exists(custom_db)


@pytest.mark.asyncio
async def test_cli_export_report_only(tmp_path):
    """Integration test: `cyg export <session_id> --report <path>` works without output DB."""
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
        "export",
        str(sess_id),
        "--report",
        str(report_md),
    ]
    output = await asyncio.to_thread(_run_cli_in_thread, test_args)

    assert "[+] Markdown report exported successfully" in output
    assert report_md.exists()
