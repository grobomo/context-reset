#!/usr/bin/env bash
# EC2 cross-platform test runner for context-reset.
# Syncs code to a running EC2 instance, installs deps, runs test suite.
#
# Usage:
#   scripts/ec2-test.sh ubuntu   # Test on ctx-reset-ubuntu
#   scripts/ec2-test.sh windows  # Test on ctx-reset-windows
#   scripts/ec2-test.sh connect ubuntu  # Just SSH into the instance
#   scripts/ec2-test.sh setup ubuntu    # Install deps only (no tests)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Instance config
declare -A INSTANCE_IPS=(
    [ubuntu]="52.15.164.243"
    [windows]="18.219.101.254"
)
declare -A INSTANCE_USERS=(
    [ubuntu]="ubuntu"
    [windows]="Administrator"
)

SSH_KEY="${CTX_RESET_SSH_KEY:-$HOME/.ssh/cpp-keys/jumpbox.pem}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"

# Resolve target
ACTION="${1:-test}"
if [[ "$ACTION" == "connect" || "$ACTION" == "setup" ]]; then
    TARGET="${2:-ubuntu}"
else
    TARGET="${1:-ubuntu}"
fi

IP="${INSTANCE_IPS[$TARGET]:-}"
USER="${INSTANCE_USERS[$TARGET]:-}"

if [[ -z "$IP" ]]; then
    echo "ERROR: Unknown target '$TARGET'. Use: ubuntu, windows"
    exit 1
fi

if [[ ! -f "$SSH_KEY" ]]; then
    echo "ERROR: SSH key not found at $SSH_KEY"
    echo "Check AWS console for the correct key pair."
    exit 1
fi

SSH_CMD="ssh $SSH_OPTS -i $SSH_KEY $USER@$IP"
SCP_CMD="scp $SSH_OPTS -i $SSH_KEY"

echo "=== ctx-reset EC2 test: $TARGET ($IP) ==="

# Connect mode: just open SSH
if [[ "$ACTION" == "connect" ]]; then
    echo "Connecting to $TARGET..."
    exec $SSH_CMD
fi

# Check connectivity
echo "Testing SSH connectivity..."
if ! $SSH_CMD "echo ok" 2>/dev/null; then
    echo "ERROR: Cannot SSH to $TARGET at $IP"
    echo "Instance may be stopped. Start it with:"
    echo "  ~/.claude/skills/aws/aws.sh ec2 start <instance-id>"
    exit 1
fi

# Sync project files (exclude .claude/, __pycache__, .git)
echo "Syncing project files..."
REMOTE_DIR="/tmp/context-reset-test"
$SSH_CMD "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR/scripts"

# Sync main files
for f in new_session.py context_reset.py task_claims.py; do
    $SCP_CMD "$PROJECT_DIR/$f" "$USER@$IP:$REMOTE_DIR/$f"
done
# Sync test files
for f in scripts/test.py scripts/test_task_claims.py; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        $SCP_CMD "$PROJECT_DIR/$f" "$USER@$IP:$REMOTE_DIR/$f"
    fi
done

# Setup mode or test mode: install deps
echo "Checking Python version..."
$SSH_CMD "python3 --version 2>&1 || echo 'Python3 not found'"

if [[ "$ACTION" == "setup" ]]; then
    echo "Setup complete. SSH in with: scripts/ec2-test.sh connect $TARGET"
    exit 0
fi

# Run tests
echo ""
echo "=== Running test suite on $TARGET ==="
$SSH_CMD "cd $REMOTE_DIR && python3 scripts/test.py 2>&1"
TEST_EXIT=$?

echo ""
if [[ $TEST_EXIT -eq 0 ]]; then
    echo "=== PASS: All tests passed on $TARGET ==="
else
    echo "=== FAIL: Tests failed on $TARGET (exit $TEST_EXIT) ==="
fi

# Run dry-run
echo ""
echo "=== Running dry-run on $TARGET ==="
$SSH_CMD "cd $REMOTE_DIR && python3 new_session.py --project-dir /tmp/context-reset-test --dry-run 2>&1" || true

echo ""
echo "=== EC2 test complete: $TARGET ==="
exit $TEST_EXIT
