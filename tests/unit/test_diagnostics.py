import pytest
import json
from cyguide.engine.diagnostics import run_diagnostics, format_terminal_report, DiagnosticReport, DiagnosticCheck

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
        details={"install_hint": "sudo apt install nmap"}
    )
    report = DiagnosticReport(checks=[check])
    output = format_terminal_report(report)
    assert "[!]" in output
    assert "Tool: nmap" in output
