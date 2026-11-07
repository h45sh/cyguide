#!/bin/bash
# CyGuide Project Verification Script
# Runs logic tests, ensures schema documentation sync, and checks code style.

set -e

echo "--- 1. Running Logic Tests (pytest) ---"
export PYTHONPATH=.
pytest

echo -e "\n--- 2. Validating & Generating Schema Registry ---"
python3 scripts/generate_schema_registry.py

if command -v ruff &> /dev/null; then
    echo -e "\n--- 3. Running Lint & Style Checks (ruff) ---"
    ruff check .
    ruff format --check .
elif [ -f ".venv/bin/ruff" ]; then
    echo -e "\n--- 3. Running Lint & Style Checks (venv ruff) ---"
    .venv/bin/ruff check .
    .venv/bin/ruff format --check .
fi

echo -e "\n[SUCCESS] All checks passed! The codebase is stable and documentation is in sync."
