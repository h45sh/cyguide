#!/bin/bash
# CyGuide Project Verification Script
# Runs all logic tests and ensures schema documentation is in sync.

set -e

echo "--- 1. Running Logic Tests (pytest) ---"
export PYTHONPATH=.
pytest

echo -e "\n--- 2. Validating & Generating Schema Registry ---"
python3 scripts/generate_schema_registry.py

echo -e "\n✅ All checks passed! The codebase is stable and documentation is in sync."
