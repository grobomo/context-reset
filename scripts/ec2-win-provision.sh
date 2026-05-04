#!/usr/bin/env bash
# Provision a Windows EC2 instance via SSM: install OpenSSH + Python.
# Usage: scripts/ec2-win-provision.sh <instance-id>
set -euo pipefail

IID="${1:?Usage: $0 <instance-id>}"

ssm_run() {
    local desc="$1"
    local cmd="$2"
    local wait="${3:-30}"

    echo "--- $desc ---"
    CMD_ID=$(aws ssm send-command \
        --instance-ids "$IID" \
        --document-name "AWS-RunPowerShellScript" \
        --parameters "commands=[\"$cmd\"]" \
        --timeout-seconds 300 \
        --query 'Command.CommandId' --output text 2>&1)

    if [[ "$CMD_ID" == *"error"* || "$CMD_ID" == *"Error"* ]]; then
        echo "  FAILED to send: $CMD_ID"
        return 1
    fi

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

echo "=== Provisioning $IID ==="

# Step 1: Install OpenSSH Server
ssm_run "Install OpenSSH Server" \
    'Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Format-List' \
    60

# Step 2: Start and enable sshd
ssm_run "Start sshd" \
    'Start-Service sshd; Set-Service -Name sshd -StartupType Automatic; Get-Service sshd | Format-List' \
    30

# Step 3: Firewall rule
ssm_run "Add firewall rule for SSH" \
    'New-NetFirewallRule -Name OpenSSH-Server -DisplayName \"OpenSSH SSH\" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue; Get-NetFirewallRule -Name OpenSSH-Server | Format-List' \
    15

# Step 4: Set default shell to PowerShell
ssm_run "Set default shell" \
    'New-ItemProperty -Path \"HKLM:\\SOFTWARE\\OpenSSH\" -Name DefaultShell -Value \"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\" -PropertyType String -Force' \
    15

# Step 5: Install Python
ssm_run "Download Python installer" \
    '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri \"https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe\" -OutFile C:\\temp\\python-installer.exe -UseBasicParsing; (Get-Item C:\\temp\\python-installer.exe).Length' \
    90

ssm_run "Install Python" \
    'Start-Process -Wait -FilePath C:\\temp\\python-installer.exe -ArgumentList \"/quiet\",\"InstallAllUsers=1\",\"PrependPath=1\"; Remove-Item C:\\temp\\python-installer.exe -ErrorAction SilentlyContinue; Write-Output done' \
    120

# Step 6: Verify
ssm_run "Verify installation" \
    '$env:Path = [System.Environment]::GetEnvironmentVariable(\"Path\",\"Machine\"); python --version; Get-Service sshd | Select-Object Status,Name' \
    15

echo ""
echo "=== Provisioning complete ==="
echo "Test SSH: ssh -i ~/.ssh/cpp-keys/jumpbox.pem Administrator@<ip>"
