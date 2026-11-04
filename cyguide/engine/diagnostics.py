"""Environment and dependency diagnostic checks for CyGuide."""

import os
import sys
import shutil
import platform
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC

import httpx
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore


INSTALLATION_HINTS: Dict[str, str] = {
    "nmap": "sudo apt install nmap  (or: brew install nmap)",
    "gobuster": "sudo apt install gobuster  (or: go install github.com/OJ/gobuster/v3@v3.6.0)",
    "nikto": "sudo apt install nikto  (or: brew install nikto)",
    "subfinder": "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.6.6",
    "whois": "sudo apt install whois  (or: brew install whois)",
}


@dataclass
class DiagnosticCheck:
    name: str
    category: str
    status: str  # "ok", "warning", "error", "info"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class DiagnosticReport:
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    system_info: Dict[str, Any] = field(default_factory=dict)
    checks: List[DiagnosticCheck] = field(default_factory=list)
    healthy: bool = True
    tool_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "system_info": self.system_info,
            "healthy": self.healthy,
            "tool_counts": self.tool_counts,
            "checks": [asdict(c) for c in self.checks]
        }


async def run_diagnostics(
    db_path: str = "data/cyguide.db", 
    tools_dir: Optional[str] = None
) -> DiagnosticReport:
    """Run all system, database, tool dependency, and explainer checks."""
    report = DiagnosticReport()
    
    # 1. System Environment
    py_version = sys.version_info
    py_version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    report.system_info = {
        "python_version": py_version_str,
        "platform": platform.platform(),
        "executable": sys.executable,
    }
    
    if py_version >= (3, 11):
        report.checks.append(DiagnosticCheck(
            name="Python Version",
            category="System",
            status="ok",
            message=f"Python {py_version_str} (>= 3.11 requirement satisfied)"
        ))
    else:
        report.checks.append(DiagnosticCheck(
            name="Python Version",
            category="System",
            status="error",
            message=f"Python {py_version_str} is below minimum requirement 3.11"
        ))
        report.healthy = False

    # Textual dependency check
    try:
        import textual
        report.checks.append(DiagnosticCheck(
            name="Textual TUI Framework",
            category="System",
            status="ok",
            message=f"Textual v{textual.__version__} installed"
        ))
    except Exception as e:
        report.checks.append(DiagnosticCheck(
            name="Textual TUI Framework",
            category="System",
            status="error",
            message=f"Failed to import textual: {str(e)}"
        ))
        report.healthy = False

    # 2. Storage & SQLite Database Health
    db_dir = os.path.dirname(os.path.abspath(db_path)) if db_path != ":memory:" else None
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        is_writable = os.access(db_dir, os.W_OK)
        if is_writable:
            report.checks.append(DiagnosticCheck(
                name="Storage Directory",
                category="Database",
                status="ok",
                message=f"Directory '{db_dir}' is writable"
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="Storage Directory",
                category="Database",
                status="error",
                message=f"Directory '{db_dir}' is not writable"
            ))
            report.healthy = False

    try:
        store = GraphStore(db_path)
        await store.initialize()
        
        async with store._get_conn() as db:
            cursor = await db.execute("PRAGMA integrity_check")
            row = await cursor.fetchone()
            integrity_status = row[0] if row else "unknown"

            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in await cursor.fetchall()]

        await store.close()

        if integrity_status == "ok":
            report.checks.append(DiagnosticCheck(
                name="SQLite Integrity",
                category="Database",
                status="ok",
                message=f"Database '{db_path}' integrity verified ({len(tables)} tables present)",
                details={"tables": tables}
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="SQLite Integrity",
                category="Database",
                status="error",
                message=f"Database integrity check failed: {integrity_status}"
            ))
            report.healthy = False
    except Exception as e:
        report.checks.append(DiagnosticCheck(
            name="SQLite Database",
            category="Database",
            status="error",
            message=f"Failed to connect to database '{db_path}': {str(e)}"
        ))
        report.healthy = False

    # 3. Security Tool Dependencies
    registry = ToolRegistry(tools_dir=tools_dir)
    registry.load_tools()
    tool_names = registry.list_tools()
    
    installed_count = 0
    total_tools = len(tool_names)

    for name in tool_names:
        tool_data = registry.get_tool(name)
        adapter = tool_data.get("adapter") if tool_data else None
        manifest = tool_data.get("manifest") if tool_data else None
        description = manifest.meta.description if manifest else ""
        
        is_installed = False
        binary_path = None

        if adapter:
            try:
                is_installed = adapter.validate_install()
            except Exception:
                is_installed = False

        binary_path = shutil.which(name)

        if is_installed:
            installed_count += 1
            report.checks.append(DiagnosticCheck(
                name=f"Tool: {name}",
                category="Tools",
                status="ok",
                message=f"Installed at {binary_path or 'PATH'}",
                details={"description": description, "binary": binary_path}
            ))
        else:
            hint = INSTALLATION_HINTS.get(name, f"Install '{name}' using your system package manager.")
            report.checks.append(DiagnosticCheck(
                name=f"Tool: {name}",
                category="Tools",
                status="warning",
                message=f"Not found in PATH. Install hint: {hint}",
                details={"description": description, "install_hint": hint}
            ))

    report.tool_counts = {
        "installed": installed_count,
        "total": total_tools,
        "missing": total_tools - installed_count
    }

    # 4. Explainer & AI Backends
    # Ollama check
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                report.checks.append(DiagnosticCheck(
                    name="Ollama Local LLM",
                    category="Explainer",
                    status="ok",
                    message=f"Connected to local Ollama ({len(models)} models available: {', '.join(models[:3])})",
                    details={"models": models}
                ))
            else:
                report.checks.append(DiagnosticCheck(
                    name="Ollama Local LLM",
                    category="Explainer",
                    status="info",
                    message="Ollama returned non-200 status (optional backend)"
                ))
    except Exception:
        report.checks.append(DiagnosticCheck(
            name="Ollama Local LLM",
            category="Explainer",
            status="info",
            message="Ollama service is not running on http://localhost:11434 (optional backend)"
        ))

    # Cloud API Keys check
    if os.getenv("CYGUIDE_API_KEY"):
        report.checks.append(DiagnosticCheck(
            name="Cloud LLM Keys",
            category="Explainer",
            status="ok",
            message=(
                f"CYGUIDE_API_KEY set (type="
                f"{os.getenv('CYGUIDE_API_TYPE', 'openai')}, "
                f"model={os.getenv('CYGUIDE_API_MODEL', 'gpt-4o')})"
            )
        ))
    else:
        cloud_keys = [
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "OPENROUTER_API_KEY",
            "GROK_API_KEY",
            "GEMINI_API_KEY",
        ]
        configured_keys = [k for k in cloud_keys if os.getenv(k)]
        if configured_keys:
            report.checks.append(DiagnosticCheck(
                name="Cloud LLM Keys",
                category="Explainer",
                status="ok",
                message=f"Configured API keys: {', '.join(configured_keys)}"
            ))
        else:
            report.checks.append(DiagnosticCheck(
                name="Cloud LLM Keys",
                category="Explainer",
                status="info",
                message="CYGUIDE_API_KEY is not set (optional backend)"
            ))

    return report


def format_terminal_report(report: DiagnosticReport) -> str:
    """Format the diagnostic report for terminal display."""
    lines = []
    lines.append("=" * 68)
    lines.append("  🩺  CYGUIDE SYSTEM & ENVIRONMENT DIAGNOSTICS")
    lines.append("=" * 68)
    lines.append(f"  Timestamp : {report.timestamp}")
    lines.append(f"  Platform  : {report.system_info.get('platform', 'unknown')}")
    lines.append(f"  Python    : {report.system_info.get('python_version', 'unknown')} ({report.system_info.get('executable', '')})")
    lines.append("-" * 68)

    # Group by category
    categories = ["System", "Database", "Tools", "Explainer"]
    for cat in categories:
        cat_checks = [c for c in report.checks if c.category == cat]
        if not cat_checks:
            continue

        header_icon = {
            "System": "🖥️ ",
            "Database": "💾",
            "Tools": "🛠️ ",
            "Explainer": "🤖"
        }.get(cat, "🔍")

        lines.append(f"\n{header_icon} {cat.upper()}")
        for c in cat_checks:
            if c.status == "ok":
                badge = "[✓]"
            elif c.status == "warning":
                badge = "[!]"
            elif c.status == "error":
                badge = "[✗]"
            else:
                badge = "[-]"
            lines.append(f"  {badge:<4} {c.name:<24} : {c.message}")

    lines.append("\n" + "=" * 68)
    tool_stat = f"{report.tool_counts.get('installed', 0)}/{report.tool_counts.get('total', 0)} security tools installed"
    if report.healthy:
        lines.append(f"  STATUS: HEALTHY ({tool_stat})")
    else:
        lines.append(f"  STATUS: ATTENTION REQUIRED ({tool_stat})")
    lines.append("=" * 68)

    return "\n".join(lines)
