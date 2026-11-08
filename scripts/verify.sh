#!/bin/bash
# CyGuide Project Verification Script
# Runs logic tests, ensures schema documentation sync, and checks code style.

set -e

echo "--- 1. Running Logic Tests (pytest) ---"
export PYTHONPATH=.
pytest

echo -e "\n--- 2. Validating & Generating Schema Registry ---"
PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi
$PYTHON_BIN scripts/generate_schema_registry.py

if command -v ruff &> /dev/null; then
    echo -e "\n--- 3. Running Lint Checks (ruff) ---"
    ruff check .
elif [ -f ".venv/bin/ruff" ]; then
    echo -e "\n--- 3. Running Lint Checks (venv ruff) ---"
    .venv/bin/ruff check .
fi

echo -e "\n[SUCCESS] All checks passed! The codebase is stable and documentation is in sync."
