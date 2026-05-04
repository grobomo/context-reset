#!/usr/bin/env bash
# Debug SSH connectivity to EC2 instances for context-reset testing.
# Usage: scripts/ec2-debug-ssh.sh [ubuntu|windows]
set -euo pipefail

TARGET="${1:-ubuntu}"

declare -A IPS=([ubuntu]="52.15.164.243" [windows]="18.219.101.254")
declare -A USERS=([ubuntu]="ec2-user" [windows]="Administrator")
declare -A IDS=([ubuntu]="i-08445bb95ee25fcdb" [windows]="i-0c3eebd2cfbd2ff88")

IP="${IPS[$TARGET]:-}"
USER="${USERS[$TARGET]:-}"
ID="${IDS[$TARGET]:-}"
KEY="$HOME/.ssh/cpp-keys/jumpbox.pem"

echo "=== SSH Debug: $TARGET ==="
echo "IP: $IP"
echo "User: $USER"
echo "Instance: $ID"
echo "Key: $KEY (exists: $(test -f "$KEY" && echo yes || echo NO))"

# Check instance state via aws skill
echo ""
echo "--- Instance state ---"
~/.claude/skills/aws/aws.sh ec2 list 2>&1 | grep "$ID" || echo "Instance not found in list"

# Try SSH with verbose
echo ""
echo "--- SSH verbose test ---"
ssh -v -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$KEY" "$USER@$IP" "echo SUCCESS; uname -a; python3 --version" 2>&1 || true

# Try with ubuntu user (AL2023 uses ec2-user, Ubuntu uses ubuntu)
echo ""
echo "--- Trying 'ubuntu' user ---"
ssh -v -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$KEY" "ubuntu@$IP" "echo SUCCESS" 2>&1 | tail -5 || true
