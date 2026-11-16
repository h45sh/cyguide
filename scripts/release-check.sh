#!/usr/bin/env bash
# CyGuide Release Preflight Check
# Verifies codebase health, wheel build, and bundled asset integrity before release.
set -euo pipefail

echo "========================================================"
echo "         CyGuide Release Preflight Sanity Check         "
echo "========================================================"

PYTHON_BIN="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

echo -e "\n[1/6] Code Style & Lint (ruff)..."
if command -v ruff &> /dev/null; then
    ruff check .
elif [ -f ".venv/bin/ruff" ]; then
    .venv/bin/ruff check .
else
    echo "Ruff not found, skipping lint."
fi

echo -e "\n[2/6] Test Suite (pytest)..."
$PYTHON_BIN -m pytest tests/

echo -e "\n[3/6] Schema Documentation Sync..."
$PYTHON_BIN scripts/generate_schema_registry.py --check

echo -e "\n[4/6] Performance Limits & Benchmark Regression Guard..."
$PYTHON_BIN scripts/generate_benchmark_report.py --check

echo -e "\n[5/6] Package Build (sdist & wheel)..."
rm -rf dist/ build/ *.egg-info
$PYTHON_BIN -m pip install --quiet build
$PYTHON_BIN -m build

echo -e "\n[6/6] Package Integrity & Bundled Asset Verification..."
$PYTHON_BIN -c "
import zipfile, glob, sys

wheels = glob.glob('dist/*.whl')
if not wheels:
    print('[-] Error: No wheel found in dist/')
    sys.exit(1)

wheel = wheels[0]
with zipfile.ZipFile(wheel, 'r') as z:
    names = set(z.namelist())
    
required_assets = [
    'cyguide/ui/style.css',
    'cyguide/assets/wordlists/common_dirs.txt.gz',
    'cyguide/assets/wordlists/subdomains_500.txt.gz',
    'cyguide/assets/wordlists/common_params.txt.gz',
    'cyguide/assets/wordlists/common_passwords.txt.gz',
    'cyguide/assets/wordlists/common_usernames.txt.gz',
    'tools/nmap/manifest.toml',
    'tools/gobuster/manifest.toml',
    'tools/ffuf/manifest.toml',
]

missing = [a for a in required_assets if a not in names]
if missing:
    print(f'[-] Error: Built wheel is missing required assets: {missing}')
    sys.exit(1)

print(f'[+] Wheel verification passed: {wheel}')
print(f'[+] All {len(required_assets)} required bundled assets & manifests are present.')
"

echo -e "\n========================================================"
echo " ✓ PREFLIGHT SUCCESS: Codebase is 100% ready for release!"
echo "========================================================"
