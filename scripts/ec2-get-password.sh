#!/usr/bin/env bash
# Get Windows EC2 RDP password.
# Usage: scripts/ec2-get-password.sh [instance-id]
set -euo pipefail

INSTANCE_ID="${1:-i-0c3eebd2cfbd2ff88}"
KEY="${CTX_RESET_SSH_KEY:-$HOME/.ssh/cpp-keys/jumpbox.pem}"

echo "=== Getting RDP password for $INSTANCE_ID ==="
echo "Key: $KEY"

# Get encrypted password
ENCRYPTED=$(aws ec2 get-password-data \
    --instance-id "$INSTANCE_ID" \
    --query 'PasswordData' \
    --output text 2>&1)

if [[ -z "$ENCRYPTED" || "$ENCRYPTED" == "None" ]]; then
    echo "No password data available."
    echo "Instance may use a custom AMI with a preset password."
    echo "Try RDP with: Administrator / (check launch template or AMI docs)"
    exit 1
fi

echo "Encrypted password retrieved. Decrypting..."
echo "$ENCRYPTED" | base64 -d | openssl rsautl -decrypt -inkey "$KEY" 2>&1
