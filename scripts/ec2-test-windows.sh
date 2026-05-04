#!/usr/bin/env bash
# EC2 Windows test runner for context-reset.
# Uses SSH (OpenSSH server on Windows) to sync code and run tests.
#
# Usage:
#   scripts/ec2-test-windows.sh           # Run tests
#   scripts/ec2-test-windows.sh connect   # SSH in
#   scripts/ec2-test-windows.sh setup     # Check deps only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

IP="${CTX_RESET_WIN_IP:-52.14.168.89}"
USER="Administrator"
KEY="${CTX_RESET_SSH_KEY:-$HOME/.ssh/cpp-keys/jumpbox.pem}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"
SSH_CMD="ssh $SSH_OPTS -i $KEY $USER@$IP"
SCP_CMD="scp $SSH_OPTS -i $KEY"

ACTION="${1:-test}"

echo "=== ctx-reset EC2 test: Windows ($IP) ==="

if [[ "$ACTION" == "connect" ]]; then
    exec $SSH_CMD
fi

if [[ "$ACTION" == "debug" ]]; then
    echo "--- Verbose SSH debug ---"
    ssh -v $SSH_OPTS -i "$KEY" "$USER@$IP" "echo SUCCESS" 2>&1 || true
    exit 0
fi

# Check connectivity
echo "Testing SSH connectivity..."
if ! $SSH_CMD "echo ok" 2>/dev/null; then
    echo "ERROR: Cannot SSH to Windows at $IP"
    echo "Check: RDP port 3389 open? OpenSSH installed? Key pair matches?"
    echo "Debug with: scripts/ec2-test-windows.sh debug"
    exit 1
fi

# Check environment
echo "Checking Windows environment..."
$SSH_CMD "systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\"" 2>&1 || true
$SSH_CMD "python --version 2>&1 || python3 --version 2>&1 || echo 'Python not found'" 2>&1
$SSH_CMD "where wt 2>nul || echo 'Windows Terminal not found'" 2>&1

if [[ "$ACTION" == "setup" ]]; then
    echo "Setup check complete."
    exit 0
fi

# Sync project files
echo "Syncing project files..."
REMOTE_DIR="C:/temp/context-reset-test"
$SSH_CMD "if not exist $REMOTE_DIR\\scripts mkdir $REMOTE_DIR\\scripts" 2>&1 || true

for f in new_session.py context_reset.py task_claims.py; do
    $SCP_CMD "$PROJECT_DIR/$f" "$USER@$IP:$REMOTE_DIR/$f"
done
for f in scripts/test.py scripts/test_task_claims.py; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        $SCP_CMD "$PROJECT_DIR/$f" "$USER@$IP:$REMOTE_DIR/$f"
    fi
done

# Run tests
echo ""
echo "=== Running test suite on Windows ==="
$SSH_CMD "cd /d $REMOTE_DIR && python scripts/test.py 2>&1" || true

# Dry-run
echo ""
echo "=== Running dry-run on Windows ==="
$SSH_CMD "cd /d $REMOTE_DIR && python new_session.py --project-dir $REMOTE_DIR --dry-run 2>&1" || true

echo ""
echo "=== EC2 Windows test complete ==="
