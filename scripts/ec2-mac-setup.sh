#!/usr/bin/env bash
# Add SSH key to macOS EC2 instance via SSM, then run tests.
# mac2.metal doesn't support SSM shell directly, but we can send commands.
set -euo pipefail

INSTANCE_ID="i-03b1aa541596068c9"
IP="18.218.210.27"
SSH_KEY="${CTX_RESET_SSH_KEY:-$HOME/.ssh/cpp-keys/jumpbox.pem}"
PUB_KEY=$(cat "${SSH_KEY%.pem}.pub" 2>/dev/null || ssh-keygen -y -f "$SSH_KEY" 2>/dev/null || echo "")

if [[ -z "$PUB_KEY" ]]; then
    echo "Generating public key from $SSH_KEY..."
    PUB_KEY=$(ssh-keygen -y -f "$SSH_KEY")
fi

echo "=== Adding SSH key to macOS EC2 ($INSTANCE_ID) ==="
echo "Public key: ${PUB_KEY:0:40}..."

# Use SSM send-command to add the key to ec2-user's authorized_keys
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[
        'mkdir -p /Users/ec2-user/.ssh',
        'chmod 700 /Users/ec2-user/.ssh',
        'echo \"$PUB_KEY\" >> /Users/ec2-user/.ssh/authorized_keys',
        'sort -u /Users/ec2-user/.ssh/authorized_keys -o /Users/ec2-user/.ssh/authorized_keys',
        'chmod 600 /Users/ec2-user/.ssh/authorized_keys',
        'chown -R ec2-user:staff /Users/ec2-user/.ssh',
        'echo SSH key added successfully'
    ]" \
    --query "Command.CommandId" \
    --output text)

echo "SSM Command ID: $COMMAND_ID"
echo "Waiting for command to complete..."

aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" 2>/dev/null || true

# Get command output
aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query "{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}" \
    --output table

echo ""
echo "Testing SSH..."
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$SSH_KEY" ec2-user@"$IP" "uname -a && python3 --version" 2>&1 || echo "SSH test failed"
