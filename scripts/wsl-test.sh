#!/usr/bin/env bash
# Run context-reset tests inside WSL to verify WSL detection and wt.exe routing.
# Run this from Windows (Git Bash): scripts/wsl-test.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -W 2>/dev/null || pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -W 2>/dev/null || pwd)"

echo "=== WSL E2E Test ==="
echo "Project dir: $PROJECT_DIR"

# Convert to WSL path
WSL_DIR=$(wsl wslpath -u "$PROJECT_DIR" 2>/dev/null) || {
    echo "ERROR: WSL not available or wslpath failed"
    exit 1
}
echo "WSL path: $WSL_DIR"

# Check Python in WSL
echo ""
echo "--- WSL Python version ---"
wsl python3 --version 2>&1 || { echo "ERROR: python3 not found in WSL"; exit 1; }

# Run test suite in WSL
echo ""
echo "=== Running test suite in WSL ==="
wsl bash -c "cd '$WSL_DIR' && python3 scripts/test.py 2>&1"
TEST_EXIT=$?

echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "=== PASS: All tests passed in WSL ==="
else
    echo "=== FAIL: Tests failed in WSL (exit $TEST_EXIT) ==="
    exit $TEST_EXIT
fi

# Verify WSL detection
echo ""
echo "=== WSL detection check ==="
wsl bash -c "cd '$WSL_DIR' && python3 -c 'import new_session; print(f\"IS_WSL={new_session.IS_WSL}, IS_WIN={new_session.IS_WIN}, IS_MAC={new_session.IS_MAC}\")'" 2>&1

# Dry-run in WSL
echo ""
echo "=== WSL dry-run ==="
wsl bash -c "cd '$WSL_DIR' && python3 new_session.py --project-dir '$WSL_DIR' --dry-run 2>&1"

echo ""
echo "=== WSL E2E test complete ==="
