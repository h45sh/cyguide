import pytest
import os
import sys
import io
import json
import asyncio
from unittest.mock import patch
from cyguide.main import main
from cyguide.engine.store import GraphStore
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
        "--db", str(src_db),
        "export",
        str(sess_id),
        str(export_db),
        "--report", str(export_md)
    ]
    export_out = await asyncio.to_thread(_run_cli_in_thread, export_args)

    assert "[+] Session database exported successfully" in export_out
    assert "[+] Markdown report exported successfully" in export_out
    assert export_db.exists()
    assert export_md.exists()

    # 3. Test import subcommand into a destination database
    dst_db = tmp_path / "destination.db"
    import_args = [
        "cyg",
        "--db", str(dst_db),
        "import",
        str(export_db)
    ]
    import_out = await asyncio.to_thread(_run_cli_in_thread, import_args)

    assert "[+] Session imported successfully!" in import_out

    # 4. Verify data in destination DB
    dst_store = GraphStore(str(dst_db))
    await dst_store.initialize()
    hosts = await dst_store.query("network.host", session_id=sess_id)
    assert len(hosts) == 1
    pik = json.loads(hosts[0]["pik_json"])
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
