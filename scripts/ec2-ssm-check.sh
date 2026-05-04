#!/usr/bin/env bash
# Check SSM agent status on EC2 instances.
# SSM allows remote command execution without SSH/port 22.
set -euo pipefail

INSTANCE_ID="${1:-i-0c3eebd2cfbd2ff88}"  # ctx-reset-windows default

echo "=== SSM connectivity check for $INSTANCE_ID ==="

# Check if instance is SSM-managed
echo "Checking SSM agent status..."
aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[].{Id:InstanceId,Status:PingStatus,Platform:PlatformType,Version:PlatformVersion,Agent:AgentVersion}' \
    --output table 2>&1

# Quick test: run a command
echo ""
echo "Testing command execution..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunPowerShellScript" \
    --parameters 'commands=["echo SUCCESS; python --version; where wt"]' \
    --query 'Command.CommandId' \
    --output text 2>&1)

if [[ "$COMMAND_ID" == *"error"* ]] || [[ -z "$COMMAND_ID" ]]; then
    echo "ERROR: SSM send-command failed: $COMMAND_ID"
    echo "Instance may not have SSM agent or IAM role."
    exit 1
fi

echo "Command ID: $COMMAND_ID"
echo "Waiting for result..."
sleep 3

aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
    --output table 2>&1
