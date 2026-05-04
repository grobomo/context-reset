#!/usr/bin/env bash
# Add SSH public key to Windows OpenSSH administrators_authorized_keys via SSM.
# Usage: scripts/ec2-win-add-sshkey.sh <instance-id> [key-file]
set -euo pipefail

IID="${1:?Usage: $0 <instance-id> [key-file]}"
KEY_FILE="${2:-$HOME/.ssh/cpp-keys/jumpbox.pem}"

# Extract public key
PUBKEY=$(ssh-keygen -y -f "$KEY_FILE" 2>&1)
echo "Public key: ${PUBKEY:0:40}..."

echo "Adding key to administrators_authorized_keys on $IID..."

CMD="Set-Content -Path 'C:\\ProgramData\\ssh\\administrators_authorized_keys' -Value '$PUBKEY'; icacls.exe 'C:\\ProgramData\\ssh\\administrators_authorized_keys' /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F'; Write-Output 'Key added and ACLs set'"

CMD_ID=$(aws ssm send-command \
    --instance-ids "$IID" \
    --document-name "AWS-RunPowerShellScript" \
    --parameters "commands=[\"$CMD\"]" \
    --query 'Command.CommandId' --output text 2>&1)

echo "Command: $CMD_ID"
for i in $(seq 1 6); do
    sleep 5
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$CMD_ID" --instance-id "$IID" \
        --query 'Status' --output text 2>&1) || true
    if [[ "$STATUS" == "Success" || "$STATUS" == "Failed" ]]; then
        aws ssm get-command-invocation \
            --command-id "$CMD_ID" --instance-id "$IID" \
            --query '{Output:StandardOutputContent,Error:StandardErrorContent}' \
            --output text 2>&1
        echo "[$STATUS]"
        exit 0
    fi
    echo -n "."
done
echo "[timeout]"
