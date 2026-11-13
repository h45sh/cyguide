import json

import pytest

from cyguide.engine.diagnostics import (
    DiagnosticCheck,
    DiagnosticReport,
    format_terminal_report,
    run_diagnostics,
)


@pytest.mark.asyncio
async def test_run_diagnostics_healthy():
    report = await run_diagnostics(db_path=":memory:")

    assert isinstance(report, DiagnosticReport)
    assert report.healthy is True
    assert "python_version" in report.system_info
    assert "platform" in report.system_info

    # Check categories
    categories = {c.category for c in report.checks}
    assert "System" in categories
    assert "Database" in categories
    assert "Tools" in categories
    assert "Explainer" in categories

    # Check tool counts
    assert report.tool_counts["total"] >= 5


@pytest.mark.asyncio
async def test_diagnostic_report_serialization():
    report = await run_diagnostics(db_path=":memory:")
    report_dict = report.to_dict()

    # Must be serializable to JSON
    json_str = json.dumps(report_dict)
    assert json_str is not None
    assert "system_info" in report_dict
    assert "checks" in report_dict
    assert "tool_counts" in report_dict


@pytest.mark.asyncio
async def test_format_terminal_report():
    report = await run_diagnostics(db_path=":memory:")
    output = format_terminal_report(report)

    assert "CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS" in output
    assert "SYSTEM" in output
    assert "DATABASE" in output
    assert "TOOLS" in output
    assert "EXPLAINER" in output
    assert "STATUS:" in output


@pytest.mark.asyncio
async def test_diagnostic_database_error(tmp_path):
    # Test a read-only or invalid directory
    bad_db_path = str(tmp_path / "non_existent_subdir" / "cyguide.db")

    # Even if folder does not exist, run_diagnostics will try to create it,
    # let's test a valid SQLite path vs memory
    report = await run_diagnostics(db_path=bad_db_path)
    db_checks = [c for c in report.checks if c.category == "Database"]
    assert len(db_checks) >= 2


def test_missing_tool_installation_hint():
    check = DiagnosticCheck(
        name="Tool: nmap",
        category="Tools",
        status="warning",
        message="Not found in PATH. Install hint: sudo apt install nmap",
        details={"install_hint": "sudo apt install nmap"},
    )
    report = DiagnosticReport(checks=[check])
    output = format_terminal_report(report)
    assert "[!]" in output
    assert "Tool: nmap" in output


from unittest.mock import MagicMock, PropertyMock, patch

from cyguide.app import CyGuideApp, ToolHealthChanged
from cyguide.engine.registry import ToolRegistry
from cyguide.ui.screens.home import DashboardScreen


def test_app_check_and_update_tool_health_broadcasting():
    """Verify check_and_update_tool_health updates cache and emits ToolHealthChanged."""
    app = CyGuideApp(db_path=":memory:")
    app.registry = ToolRegistry()
    app.registry.load_tools()

    received_messages = []
    dummy_screen = MagicMock()
    dummy_screen.post_message = lambda msg: received_messages.append(msg)

    with patch.object(
        CyGuideApp, "screen_stack", new_callable=PropertyMock, return_value=[dummy_screen]
    ):
        # Mock diagnostics to return 1 missing tool
        fake_health_1 = {
            "nmap": {"healthy": False, "status": "missing", "message": "Missing", "binary": None},
            "gobuster": {
                "healthy": True,
                "status": "ok",
                "message": "OK",
                "binary": "/usr/bin/gobuster",
            },
        }
        with patch("cyguide.engine.diagnostics.check_tool_health", return_value=fake_health_1):
            res1 = app.check_and_update_tool_health()
            assert res1 == fake_health_1
            assert app._cached_tool_health == fake_health_1
            assert len(received_messages) == 1
            assert isinstance(received_messages[0], ToolHealthChanged)
            assert received_messages[0].health == fake_health_1

        # Second check with same status should not re-broadcast
        with patch("cyguide.engine.diagnostics.check_tool_health", return_value=fake_health_1):
            res2 = app.check_and_update_tool_health()
            assert res2 == fake_health_1
            assert len(received_messages) == 1

        # Status changes to all healthy -> should broadcast update
        fake_health_2 = {
            "nmap": {"healthy": True, "status": "ok", "message": "OK", "binary": "/usr/bin/nmap"},
            "gobuster": {
                "healthy": True,
                "status": "ok",
                "message": "OK",
                "binary": "/usr/bin/gobuster",
            },
        }
        with patch("cyguide.engine.diagnostics.check_tool_health", return_value=fake_health_2):
            res3 = app.check_and_update_tool_health()
            assert res3 == fake_health_2
            assert len(received_messages) == 2
            assert received_messages[1].health == fake_health_2


def test_command_palette_tool_health_badge_freshness():
    """Verify Command Palette gets fresh tool health directly."""
    app = CyGuideApp(db_path=":memory:")
    app.registry = ToolRegistry()
    app.registry.load_tools()

    mock_screen = MagicMock()
    mock_screen.query.return_value = []

    fake_issues = {
        "nmap": {"healthy": False, "status": "missing", "message": "Missing", "binary": None},
        "gobuster": {
            "healthy": True,
            "status": "ok",
            "message": "OK",
            "binary": "/usr/bin/gobuster",
        },
    }
    with patch("cyguide.engine.diagnostics.check_tool_health", return_value=fake_issues):
        cmds = list(app.get_system_commands(mock_screen))
        tool_cmd = next(c for c in cmds if "Tool Health" in c.title)
        assert "1 Issue" in tool_cmd.title

    fake_healthy = {
        "nmap": {"healthy": True, "status": "ok", "message": "OK", "binary": "/usr/bin/nmap"},
        "gobuster": {
            "healthy": True,
            "status": "ok",
            "message": "OK",
            "binary": "/usr/bin/gobuster",
        },
    }
    with patch("cyguide.engine.diagnostics.check_tool_health", return_value=fake_healthy):
        cmds = list(app.get_system_commands(mock_screen))
        tool_cmd = next(c for c in cmds if "Tool Health" in c.title)
        assert "Healthy (2/2)" in tool_cmd.title


@pytest.mark.asyncio
async def test_dashboard_apply_tool_health_visibility():
    """Verify dashboard hides tool health when clean and shows alerts when tools are missing."""
    dash = DashboardScreen()
    container = MagicMock()
    diag_list = MagicMock()

    async def fake_clear():
        pass

    diag_list.clear = fake_clear
    diag_list.append = MagicMock()

    def fake_query(selector, cls=None):
        if selector == "#tool_health_container":
            return container
        if selector == "#diagnostics_list":
            return diag_list
        raise ValueError(f"Unknown selector {selector}")

    dash.query_one = fake_query

    # 1. Missing tool -> shows alerts container (removes 'hidden') and adds item
    issues_health = {
        "nmap": {"healthy": False, "status": "missing", "message": "Not installed", "binary": None}
    }
    await dash.apply_tool_health(issues_health)
    container.remove_class.assert_called_with("hidden")
    diag_list.append.assert_called_once()

    # 2. All healthy -> hides alerts container (adds 'hidden')
    clean_health = {
        "nmap": {"healthy": True, "status": "ok", "message": "OK", "binary": "/usr/bin/nmap"}
    }
    container.reset_mock()
    diag_list.reset_mock()
    await dash.apply_tool_health(clean_health)
    container.add_class.assert_called_with("hidden")
    diag_list.append.assert_not_called()


@pytest.mark.asyncio
async def test_tool_health_modal_realtime_apply_health():
    """Verify ToolHealthModal updates summary label and rows dynamically."""
    from cyguide.ui.screens.tool_health_modal import ToolHealthModal

    modal = ToolHealthModal()
    summary_label = MagicMock()
    items_list = MagicMock()

    async def fake_clear():
        pass

    items_list.clear = fake_clear
    items_list.append = MagicMock()

    def fake_query(selector, cls=None):
        if selector == "#tool_health_summary_label":
            return summary_label
        if selector == "#tool_health_items":
            return items_list
        raise ValueError(f"Unknown selector {selector}")

    modal.query_one = fake_query

    # 1. With issues
    issues_health = {
        "nmap": {"healthy": False, "status": "missing", "message": "Not installed", "binary": None},
        "gobuster": {
            "healthy": True,
            "status": "ok",
            "message": "OK",
            "binary": "/usr/bin/gobuster",
        },
    }
    await modal.apply_health(issues_health)
    summary_label.update.assert_called_with("▲ 1 issue(s) detected across 2 registered tools.")
    assert items_list.append.call_count == 2

    # 2. All healthy
    clean_health = {
        "nmap": {"healthy": True, "status": "ok", "message": "OK", "binary": "/usr/bin/nmap"},
        "gobuster": {
            "healthy": True,
            "status": "ok",
            "message": "OK",
            "binary": "/usr/bin/gobuster",
        },
    }
    summary_label.reset_mock()
    items_list.reset_mock()
    await modal.apply_health(clean_health)
    summary_label.update.assert_called_with(
        "● All 2 registered tools are operational and available."
    )
    assert items_list.append.call_count == 2
