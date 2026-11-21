# codeguard: disable-file[INJECTION_COMMAND_SHELL]
"""Automated architectural boundary tests.

Enforces system invariants across the codebase:
1. Strict Layer DAG: UI never imports low-level database drivers (sqlite3, aiosqlite).
2. Engine-UI Decoupling: Engine never imports from cyguide.ui.
3. Clean Seams: No external access to ExecutionSession private dictionaries.
4. Centralized Presentation: Schema display helpers reside in cyguide.schemas.presentation.
"""

import ast
from pathlib import Path
from typing import List, Tuple

import pytest

pytestmark = pytest.mark.tier0

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CYGUIDE_DIR = REPO_ROOT / "cyguide"


def _get_python_files(directory: Path) -> List[Path]:
    """Recursively collect all python files under a directory."""
    return [p for p in directory.rglob("*.py") if not p.name.startswith(".")]


def _parse_ast(file_path: Path) -> ast.AST:
    """Parse a Python source file into an AST."""
    with open(file_path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=str(file_path))


def test_ui_layer_never_imports_raw_sql_drivers():
    """Rule: Presentation layer (cyguide/ui and cyguide/cli) must never import raw SQL libraries directly."""
    banned_modules = {"sqlite3", "aiosqlite"}
    violations: List[Tuple[str, int, str]] = []

    presentation_files = _get_python_files(CYGUIDE_DIR / "ui") + _get_python_files(
        CYGUIDE_DIR / "cli"
    )
    for py_file in presentation_files:
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in banned_modules:
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module == b or node.module.startswith(f"{b}.") for b in banned_modules
                ):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Presentation layer directly imported raw SQL driver: {violations}"


def test_engine_layer_never_imports_ui():
    """Rule: cyguide/engine must never import from cyguide/ui (downward-only dependency DAG)."""
    violations: List[Tuple[str, int, str]] = []
    engine_dir = CYGUIDE_DIR / "engine"

    for py_file in _get_python_files(engine_dir):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "cyguide.ui" in alias.name:
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    "cyguide.ui" in node.module or node.module.startswith("cyguide.ui")
                ):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Engine layer inverted dependency by importing UI: {violations}"


def test_no_private_state_penetration_of_execution_session():
    """Rule: Outside execution_session.py and its direct unit tests, no module penetrates private attributes."""
    banned_private_attrs = {
        "_active_jobs",
        "_job_actions",
        "_job_buffers",
        "_session_cwd",
        "_running_tasks",
    }
    violations: List[Tuple[str, int, str]] = []

    # Check all files in cyguide/
    for py_file in _get_python_files(CYGUIDE_DIR):
        # Exclude execution_session.py itself and compat properties
        if py_file.name in ("execution_session.py", "compat.py"):
            continue
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in banned_private_attrs:
                    # Ignore internal self._ references inside execution_session
                    if isinstance(node.value, ast.Name) and node.value.id in ("self", "cls"):
                        continue
                    violations.append((py_file.name, node.lineno, node.attr))

    assert not violations, (
        f"Components penetrated ExecutionSession private attributes: {violations}"
    )


def test_presentation_helpers_are_available():
    """Rule: Presentation schema helpers must be exported and usable."""
    from cyguide.schemas.presentation import (
        SCHEMA_DISPLAY_MAP,
        build_ip_to_name_map,
        format_activity_entry,
        format_node_label,
        get_schema_display_meta,
    )

    assert "network.host" in SCHEMA_DISPLAY_MAP
    assert get_schema_display_meta("network.host")[0] == "●"
    assert format_activity_entry("Session Test", "system.event", "Ran whois") == "[Test] Run: whois"

    # Test format_node_label
    host_node = {
        "id": "node-12345",
        "schema_type": "network.host",
        "pik_json": '{"ip": "192.168.1.1"}',
        "data_json": '{"hostname": "router.local"}',
    }
    label = format_node_label(host_node)
    assert label == "192.168.1.1 (router.local)"

    # Test build_ip_to_name_map
    nodes = [host_node]
    ip_map = build_ip_to_name_map(nodes)
    assert ip_map.get("192.168.1.1") == "router.local"


def test_no_composite_or_catchall_test_files():
    """Rule: Ban dump files (e.g. test_security_fixes.py) and multi-domain composites (e.g. test_foo_and_bar.py).

    Tests must be cleanly organized by domain module.
    """
    tests_dir = REPO_ROOT / "tests"
    banned_substrings = ["_fixes.py", "_and_", "_dump.py", "_misc.py"]
    violations = []

    for test_file in tests_dir.rglob("test_*.py"):
        for banned in banned_substrings:
            if banned in test_file.name:
                violations.append((test_file.name, banned))

    assert not violations, (
        f"Found dump/composite test files. Tests must be split by domain module: {violations}"
    )


def test_schema_registry_docs_in_sync():
    """Rule: docs/developer/SCHEMA_REGISTRY.md must strictly match finding schema definitions."""
    from scripts.generate_schema_registry import generate_registry

    # generate_registry with check_only=True verifies content and exits with 1 on mismatch
    generate_registry(check_only=True)


def test_all_registered_finding_schemas_have_presentation_meta():
    """Rule: Every registered BaseFinding schema must have display icons, titles, and formatting metadata

    in SCHEMA_DISPLAY_MAP to prevent UI rendering fallbacks.
    """
    from cyguide.schemas.presentation import SCHEMA_DISPLAY_MAP
    from scripts.generate_schema_registry import get_all_finding_schemas

    schemas = get_all_finding_schemas()
    missing = []
    for schema_cls in schemas:
        schema_type = (
            schema_cls.model_fields["schema_type"].default
            if "schema_type" in schema_cls.model_fields
            else getattr(schema_cls, "schema_type", None)
        )
        if schema_type and schema_type not in SCHEMA_DISPLAY_MAP:
            missing.append(schema_type)

    assert not missing, f"Schemas missing UI display metadata in presentation.py: {missing}"


def test_no_external_penetration_of_execution_session_private_state_in_tests():
    """Rule: Outside test_execution_session.py, test files must never access private

    dictionaries (_active_jobs, _job_actions, _job_buffers) directly. Tests must use public seams.
    """
    tests_dir = REPO_ROOT / "tests"
    banned_private_attrs = {
        "_active_jobs",
        "_job_actions",
        "_job_buffers",
        "_session_cwd",
        "_running_tasks",
    }
    violations: List[Tuple[str, int, str]] = []

    for py_file in tests_dir.rglob("test_*.py"):
        # Exclude direct unit tests of execution_session internals and this architecture test file
        if py_file.name in ("test_execution_session.py", "test_architecture.py"):
            continue
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in banned_private_attrs:
                    violations.append((py_file.name, node.lineno, node.attr))

    assert not violations, (
        f"Tests bypassed public seams to penetrate private ExecutionSession state: {violations}"
    )


def test_ui_layer_never_imports_subprocess():
    """Rule: Presentation layer (cyguide/ui and cyguide/cli) must never import or spawn subprocesses directly."""
    violations: List[Tuple[str, int, str]] = []
    presentation_files = _get_python_files(CYGUIDE_DIR / "ui") + _get_python_files(
        CYGUIDE_DIR / "cli"
    )

    for py_file in presentation_files:
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess" or alias.name.startswith("subprocess."):
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "subprocess" or node.module.startswith("subprocess.")
                ):
                    violations.append((py_file.name, node.lineno, node.module))
            elif isinstance(node, ast.Attribute):
                if node.attr in ("create_subprocess_exec", "create_subprocess_shell"):
                    violations.append((py_file.name, node.lineno, f"asyncio.{node.attr}"))
                elif (
                    node.attr == "subprocess"
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "asyncio"
                ):
                    violations.append((py_file.name, node.lineno, "asyncio.subprocess"))

    assert not violations, (
        f"Presentation layer directly imported or spawned subprocess: {violations}"
    )


def test_ui_never_penetrates_app_private_state():
    """Rule: cyguide/ui must never penetrate private attributes of CyGuideApp (e.g. _last_shortcuts_toggle_time)."""
    banned_app_private_attrs = {"_last_shortcuts_toggle_time"}
    violations: List[Tuple[str, int, str]] = []
    ui_dir = CYGUIDE_DIR / "ui"

    for py_file in _get_python_files(ui_dir):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr in banned_app_private_attrs:
                    violations.append((py_file.name, node.lineno, node.attr))

    assert not violations, f"UI penetrated CyGuideApp private attributes: {violations}"


def test_ban_shell_true_and_os_system_across_codebase():
    """Rule (Trust Pyramid): Mechanically ban shell=True and os.system across cyguide and tools."""
    violations: List[Tuple[str, int, str]] = []
    scan_dirs = [CYGUIDE_DIR, REPO_ROOT / "tools"]

    for directory in scan_dirs:
        for py_file in _get_python_files(directory):
            tree = _parse_ast(py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check for shell=True keyword argument
                    for kw in node.keywords:
                        if kw.arg == "shell":
                            if isinstance(kw.value, ast.Constant) and bool(kw.value.value):
                                violations.append((py_file.name, node.lineno, "shell=True"))
                    # Check for os.system(...)
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "system"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                    ):
                        violations.append((py_file.name, node.lineno, "os.system()"))

    assert not violations, f"Forbidden command injection vectors found: {violations}"


def test_tool_adapters_never_import_subprocess_directly():
    """Rule (Trust Pyramid): Pluggable tool adapters must never spawn processes directly.

    Process lifecycles, environment scrubbing, and stream parsing are mediated exclusively by the engine.
    """
    violations: List[Tuple[str, int, str]] = []
    tools_dir = REPO_ROOT / "tools"

    for py_file in _get_python_files(tools_dir):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("subprocess", "asyncio.subprocess"):
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module == "subprocess"
                    or node.module.startswith("subprocess.")
                    or "asyncio.subprocess" in node.module
                ):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Tool adapters directly imported subprocess: {violations}"


def test_sql_execution_never_uses_formatted_strings():
    """Rule (Trust Pyramid): Ban raw SQL string interpolation (f-strings, %, .format()) in database execute calls.

    All SQL statements must use parameterized queries with SQLite placeholders (?).
    """
    violations: List[Tuple[str, int, str]] = []
    for py_file in _get_python_files(CYGUIDE_DIR):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in (
                    "execute",
                    "executemany",
                ):
                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.JoinedStr):  # f-string
                            violations.append(
                                (py_file.name, node.lineno, "f-string in sql execute")
                            )
                        elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                            violations.append(
                                (py_file.name, node.lineno, "% formatting in sql execute")
                            )
                        elif (
                            isinstance(first_arg, ast.Call)
                            and isinstance(first_arg.func, ast.Attribute)
                            and first_arg.func.attr == "format"
                        ):
                            violations.append(
                                (py_file.name, node.lineno, ".format() in sql execute")
                            )

    assert not violations, f"Found unparameterized SQL execution calls: {violations}"


def test_ui_palette_visual_ergonomics_safeguard():
    """Rule (Visual Ergonomics & Eye Comfort): Prevent eye fatigue and halation glare.

    Forbids raw piercing neon yellow hex codes (#eab308, #facc15, #fef08a) in UI styles
    and Python UI rendering modules. Mandates calm, low-glare ergonomic tokens.
    """
    import re

    banned_neon_patterns = re.compile(r"#(eab308|facc15|fef08a)", re.IGNORECASE)
    ui_dir = CYGUIDE_DIR / "ui"
    violations: List[Tuple[str, int, str]] = []

    # 1. Audit style.css
    css_file = ui_dir / "style.css"
    if css_file.exists():
        with open(css_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                m = banned_neon_patterns.search(line)
                if m:
                    violations.append(("style.css", idx, m.group(0)))

    # 2. Audit all UI python files
    for py_file in _get_python_files(ui_dir):
        with open(py_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                m = banned_neon_patterns.search(line)
                if m:
                    violations.append((py_file.name, idx, m.group(0)))

    assert not violations, (
        f"Eye fatigue safeguard violation: Piercing neon yellow hex codes found in UI: {violations}. "
        "Use ergonomic tokens ($semantic-gold #c5a059, $semantic-amber #f59e0b, or $accent-primary #38bdf8)."
    )


def test_no_shallow_passthrough_shims_in_presentation():
    """Rule (Deep Modules & Zero Indirection Tax): UI presentation modules must not define

    shallow 1:1 pass-through functions that merely forward to other functions without transformation.
    """
    ui_dir = CYGUIDE_DIR / "ui"
    violations: List[Tuple[str, int, str]] = []

    for py_file in _get_python_files(ui_dir):
        tree = _parse_ast(py_file)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stmts = [
                    s
                    for s in node.body
                    if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                ]
                if len(stmts) == 1 and isinstance(stmts[0], ast.Return):
                    ret_val = stmts[0].value
                    if isinstance(ret_val, ast.Call) and isinstance(ret_val.func, ast.Name):
                        violations.append(
                            (py_file.name, node.lineno, f"{node.name} -> {ret_val.func.id}")
                        )

    assert not violations, (
        f"Found shallow 1:1 pass-through functions in presentation layer: {violations}"
    )


def test_ui_layer_never_performs_raw_file_io():
    """Rule (Pure Core vs Imperative Shell): UI presentation modules must never perform raw disk I/O.

    All file exports, scratchpad loading, and disk persistence must be delegated to
    coordination services (SessionReportService, PreferencesStore, etc.).
    """
    ui_dir = CYGUIDE_DIR / "ui"
    violations: List[Tuple[str, int, str]] = []

    for py_file in _get_python_files(ui_dir):
        # Exclude compat.py if it reads internal assets, though compat does not
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check built-in open()
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    violations.append((py_file.name, node.lineno, "built-in open()"))
                # Check os.open, os.fdopen
                elif (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in ("open", "fdopen")
                ):
                    violations.append((py_file.name, node.lineno, f"os.{node.func.attr}()"))

    assert not violations, (
        f"Presentation layer violated pure boundary by performing raw disk I/O: {violations}"
    )


def test_schemas_layer_has_zero_downward_or_cross_dependencies():
    """Rule (Pure Core): cyguide/schemas must never import from engine, ui, cli, or tools."""
    schemas_dir = CYGUIDE_DIR / "schemas"
    banned_prefixes = ("cyguide.engine", "cyguide.ui", "cyguide.cli", "tools")
    violations: List[Tuple[str, int, str]] = []

    for py_file in _get_python_files(schemas_dir):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(banned_prefixes):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Schemas layer violated pure core isolation: {violations}"


def test_tool_adapters_never_import_ui_or_facades():
    """Rule (Smart Adapter / Stupid Framework): Pluggable tool adapters must never import UI or facades."""
    tools_dir = REPO_ROOT / "tools"
    banned_prefixes = (
        "cyguide.ui",
        "cyguide.engine.power_facade",
        "cyguide.engine.learning",
        "cyguide.main",
    )
    violations: List[Tuple[str, int, str]] = []

    for py_file in tools_dir.glob("*/adapter.py"):
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(banned_prefixes):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Tool adapter violated framework boundary: {violations}"


def test_core_engine_never_imports_coordination_facades():
    """Rule (Layer DAG): Core engine modules must never import coordination facades (downward flow only)."""
    core_modules = {
        "store.py",
        "registry.py",
        "execution_session.py",
        "gateway.py",
        "timeline.py",
        "adapter.py",
    }
    banned_prefixes = (
        "cyguide.engine.power_facade",
        "cyguide.engine.learning",
    )
    violations: List[Tuple[str, int, str]] = []

    for mod_name in core_modules:
        py_file = CYGUIDE_DIR / "engine" / mod_name
        if not py_file.exists():
            continue
        tree = _parse_ast(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(banned_prefixes):
                        violations.append((py_file.name, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(banned_prefixes):
                    violations.append((py_file.name, node.lineno, node.module))

    assert not violations, f"Core engine inverted layer DAG by importing facades: {violations}"
