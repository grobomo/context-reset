#!/usr/bin/env bash
# Install Python on Windows EC2 via SSM.
# Usage: scripts/ec2-win-install-python.sh <instance-id>
set -euo pipefail

IID="${1:?Usage: $0 <instance-id>}"

ssm_run() {
    local desc="$1"
    local cmd="$2"
    local wait="${3:-60}"

    echo "--- $desc ---"
    CMD_ID=$(aws ssm send-command \
        --instance-ids "$IID" \
        --document-name "AWS-RunPowerShellScript" \
        --parameters "commands=[\"$cmd\"]" \
        --timeout-seconds 300 \
        --query 'Command.CommandId' --output text 2>&1)

    for i in $(seq 1 $((wait / 5))); do
        sleep 5
        STATUS=$(aws ssm get-command-invocation \
            --command-id "$CMD_ID" --instance-id "$IID" \
            --query 'Status' --output text 2>&1) || true
        if [[ "$STATUS" == "Success" || "$STATUS" == "Failed" || "$STATUS" == "TimedOut" ]]; then
            aws ssm get-command-invocation \
                --command-id "$CMD_ID" --instance-id "$IID" \
                --query 'StandardOutputContent' --output text 2>&1
            ERR=$(aws ssm get-command-invocation \
                --command-id "$CMD_ID" --instance-id "$IID" \
                --query 'StandardErrorContent' --output text 2>&1)
            [[ -n "$ERR" && "$ERR" != "None" ]] && echo "  STDERR: $ERR"
            echo "  [$STATUS]"
            return 0
        fi
        echo -n "."
    done
    echo "  [timeout after ${wait}s]"
}

echo "=== Installing Python on $IID ==="

ssm_run "Create temp dir + download Python" \
    'New-Item -ItemType Directory -Path C:\\temp -Force | Out-Null; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri \"https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe\" -OutFile C:\\temp\\python-installer.exe -UseBasicParsing; Write-Output \"Downloaded: $((Get-Item C:\\temp\\python-installer.exe).Length / 1MB) MB\"' \
    90

ssm_run "Install Python (silent)" \
    'Start-Process -Wait -FilePath C:\\temp\\python-installer.exe -ArgumentList \"/quiet\",\"InstallAllUsers=1\",\"PrependPath=1\"; Remove-Item C:\\temp\\python-installer.exe -ErrorAction SilentlyContinue; Write-Output installed' \
    120

ssm_run "Restart sshd (picks up new PATH)" \
    'Restart-Service sshd; Write-Output restarted' \
    15

ssm_run "Verify Python" \
    '$env:Path = [System.Environment]::GetEnvironmentVariable(\"Path\",\"Machine\"); python --version' \
    15

echo "=== Done ==="
