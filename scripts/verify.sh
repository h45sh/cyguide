#!/bin/bash
# CyGuide Project Verification Script
# Runs logic tests, ensures schema documentation sync, and checks code style.

set -e

PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

PYTEST_BIN="pytest"
if [ -f ".venv/bin/pytest" ]; then
    PYTEST_BIN=".venv/bin/pytest"
fi

echo "--- 1. Running Fast Pre-Flight Invariants (pytest -m tier0) ---"
export PYTHONPATH=.
$PYTEST_BIN -m tier0 -q

echo -e "\n--- 2. Running Complete Test Suite (pytest) ---"
$PYTEST_BIN

echo -e "\n--- 3. Validating & Generating Schema Registry ---"
$PYTHON_BIN scripts/generate_schema_registry.py
$PYTHON_BIN scripts/generate_schema_registry.py --check

if command -v ruff &> /dev/null; then
    echo -e "\n--- 3. Running Lint Checks (ruff) ---"
    ruff check .
elif [ -f ".venv/bin/ruff" ]; then
    echo -e "\n--- 3. Running Lint Checks (venv ruff) ---"
    .venv/bin/ruff check .
else
    echo -e "\n--- 3. Lint Checks Skipped (ruff not found) ---"
fi

if command -v pip-audit &> /dev/null; then
    echo -e "\n--- 4. Running Dependency Vulnerability Audit (pip-audit) ---"
    pip-audit
elif [ -f ".venv/bin/pip-audit" ]; then
    echo -e "\n--- 4. Running Dependency Vulnerability Audit (venv pip-audit) ---"
    .venv/bin/pip-audit
else
    echo -e "\n--- 4. Dependency Audit Skipped (pip-audit not found) ---"
fi

echo -e "\n--- 5. Running Environment Diagnostics (cyg check) ---"
$PYTHON_BIN -m cyguide.main check --json > /dev/null

echo -e "\n[SUCCESS] All checks passed! The codebase is stable and documentation is in sync."
