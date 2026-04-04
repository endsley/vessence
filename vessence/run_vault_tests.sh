#!/usr/bin/env bash
# run_vault_tests.sh — Run all vault_web tests
# Usage: ./run_vault_tests.sh [--live]
#   --live  also run live-server integration tests (requires vault_web server)

set -e

PYTHON=/home/chieh/google-adk-env/adk-venv/bin/python
TESTDIR=/home/chieh/vessence/test_code
VAULTDIR=/home/chieh/vessence/vault_web

cd "$VAULTDIR"

echo "============================================"
echo "  Vault Web Unit Tests (no server required)"
echo "============================================"
$PYTHON -m pytest "$TESTDIR/test_vault_unit.py" -v --tb=short
UNIT_EXIT=$?

if [[ "$1" == "--live" ]]; then
    echo ""
    echo "============================================"
    echo "  Vault Web Integration Tests (live server)"
    echo "============================================"
    $PYTHON -m pytest "$TESTDIR/test_vault_web.py" -v --tb=short
    LIVE_EXIT=$?
    if [[ $UNIT_EXIT -ne 0 || $LIVE_EXIT -ne 0 ]]; then
        echo "FAIL: one or more test suites failed"
        exit 1
    fi
else
    if [[ $UNIT_EXIT -ne 0 ]]; then
        echo "FAIL: unit tests failed"
        exit 1
    fi
fi

echo ""
echo "All tests passed."
