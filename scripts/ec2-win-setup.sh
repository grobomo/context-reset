#!/usr/bin/env bash
# Create a Windows EC2 instance with SSM + SSH for testing context-reset.
# SSM lets us run commands without SSH as fallback.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY_NAME="jumpbox-key"
INSTANCE_TYPE="t3.medium"
SG_ID="sg-032e0f946606cfbb4"
PROFILE_NAME="ctx-reset-ssm-profile"
ROLE_NAME="ctx-reset-ssm-role"
ACTION="${1:-create}"

# --- Helpers ---
ensure_iam_role() {
    # Check if role exists
    if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
        echo "IAM role $ROLE_NAME already exists"
    else
        echo "Creating IAM role $ROLE_NAME..."
        aws iam create-role --role-name "$ROLE_NAME" \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }' --query 'Role.Arn' --output text
        aws iam attach-role-policy --role-name "$ROLE_NAME" \
            --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    fi

    # Check if instance profile exists
    if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" &>/dev/null; then
        echo "Instance profile $PROFILE_NAME already exists"
    else
        echo "Creating instance profile $PROFILE_NAME..."
        aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME"
        aws iam add-role-to-instance-profile \
            --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME"
        echo "Waiting 10s for IAM propagation..."
        sleep 10
    fi
}

create_instance() {
    ensure_iam_role

    # Find latest Windows Server 2022 AMI
    AMI_ID=$(aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=Windows_Server-2022-English-Full-Base-*" "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)
    echo "AMI: $AMI_ID"

    # User-data: install OpenSSH + Python + firewall
    USERDATA=$(cat <<'UDEOF'
<powershell>
$log = "C:\setup-log.txt"
"$(Get-Date) Starting setup" | Out-File $log

# Install OpenSSH
"$(Get-Date) Installing OpenSSH..." | Out-File $log -Append
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 2>&1 | Out-File $log -Append
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
"$(Get-Date) sshd started" | Out-File $log -Append

# Firewall rule
New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH SSH" `
    -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 `
    -ErrorAction SilentlyContinue
"$(Get-Date) Firewall rule added" | Out-File $log -Append

# Default shell = PowerShell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
    -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -PropertyType String -Force

# Install Python 3.12
$url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$installer = "$env:TEMP\python-installer.exe"
"$(Get-Date) Downloading Python..." | Out-File $log -Append
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
"$(Get-Date) Installing Python..." | Out-File $log -Append
Start-Process -Wait -FilePath $installer -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1'
Remove-Item $installer -ErrorAction SilentlyContinue
"$(Get-Date) Python installed" | Out-File $log -Append

# Add Python to system PATH for SSH sessions
$pythonPath = "C:\Program Files\Python312"
$currentPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
if ($currentPath -notlike "*Python312*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$pythonPath;$pythonPath\Scripts", "Machine")
}

# Restart sshd to pick up PATH
Restart-Service sshd
"$(Get-Date) SETUP COMPLETE" | Out-File $log -Append
</powershell>
UDEOF
)

    USERDATA_B64=$(echo "$USERDATA" | base64 -w 0)

    echo "Launching instance..."
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id "$AMI_ID" \
        --instance-type "$INSTANCE_TYPE" \
        --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" \
        --iam-instance-profile "Name=$PROFILE_NAME" \
        --user-data "$USERDATA_B64" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ctx-reset-win-test}]" \
        --query 'Instances[0].InstanceId' --output text)

    echo "Instance: $INSTANCE_ID"
    echo "Waiting for running state..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

    IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

    echo ""
    echo "=== Windows test instance ==="
    echo "Instance: $INSTANCE_ID"
    echo "IP: $IP"
    echo "SSM + SSH enabled. Wait ~10 min, then:"
    echo "  scripts/ec2-win-setup.sh check $INSTANCE_ID"
}

check_instance() {
    local iid="${2:-}"
    if [[ -z "$iid" ]]; then
        echo "Usage: $0 check <instance-id>"
        exit 1
    fi

    echo "=== Checking $iid ==="

    # Check SSM agent
    echo "--- SSM agent status ---"
    aws ssm describe-instance-information \
        --filters "Key=InstanceIds,Values=$iid" \
        --query 'InstanceInformationList[0].{Agent:AgentVersion,Status:PingStatus,Platform:PlatformName}' \
        --output table 2>&1 || echo "SSM agent not reporting yet"

    # Try SSM command to read setup log
    echo ""
    echo "--- Setup log (via SSM) ---"
    CMD_ID=$(aws ssm send-command \
        --instance-ids "$iid" \
        --document-name "AWS-RunPowerShellScript" \
        --parameters 'commands=["Get-Content C:\\setup-log.txt -ErrorAction SilentlyContinue; python --version 2>&1; Get-Service sshd 2>&1"]' \
        --query 'Command.CommandId' --output text 2>&1) || { echo "SSM command failed: $CMD_ID"; return 1; }

    echo "Command: $CMD_ID"
    echo "Waiting for result..."
    for i in $(seq 1 6); do
        sleep 5
        RESULT=$(aws ssm get-command-invocation \
            --command-id "$CMD_ID" --instance-id "$iid" \
            --query 'Status' --output text 2>&1) || true
        if [[ "$RESULT" == "Success" || "$RESULT" == "Failed" ]]; then
            aws ssm get-command-invocation \
                --command-id "$CMD_ID" --instance-id "$iid" \
                --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
                --output text 2>&1
            return
        fi
        echo "  attempt $i: $RESULT"
    done
    echo "Command still running after 30s. Try again later."
}

run_tests() {
    local iid="${2:-}"
    if [[ -z "$iid" ]]; then
        echo "Usage: $0 test <instance-id>"
        exit 1
    fi

    local project_dir="$SCRIPT_DIR/.."

    echo "=== Running tests on $iid via SSM ==="

    # Upload test files via SSM (base64 encode each file)
    echo "Uploading test files..."
    for f in new_session.py context_reset.py task_claims.py scripts/test.py scripts/test_task_claims.py; do
        if [[ -f "$project_dir/$f" ]]; then
            local b64=$(base64 -w 0 < "$project_dir/$f")
            local remote_path="C:\\temp\\context-reset-test\\$f"
            local remote_dir=$(dirname "$remote_path" | sed 's|/|\\|g')
            aws ssm send-command \
                --instance-ids "$iid" \
                --document-name "AWS-RunPowerShellScript" \
                --parameters "commands=[\"New-Item -ItemType Directory -Path '$remote_dir' -Force | Out-Null; [IO.File]::WriteAllBytes('$remote_path', [Convert]::FromBase64String('$b64'))\"]" \
                --query 'Command.CommandId' --output text > /dev/null 2>&1
            echo "  uploaded: $f"
        fi
    done

    sleep 3

    # Run tests
    echo ""
    echo "--- Running test suite ---"
    CMD_ID=$(aws ssm send-command \
        --instance-ids "$iid" \
        --document-name "AWS-RunPowerShellScript" \
        --parameters 'commands=["cd C:\\temp\\context-reset-test; python scripts\\test.py 2>&1"]' \
        --timeout-seconds 120 \
        --query 'Command.CommandId' --output text)

    echo "Command: $CMD_ID"
    echo "Waiting for results..."
    sleep 15

    aws ssm get-command-invocation \
        --command-id "$CMD_ID" --instance-id "$iid" \
        --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
        --output text 2>&1

    # Dry-run
    echo ""
    echo "--- Running dry-run ---"
    CMD_ID=$(aws ssm send-command \
        --instance-ids "$iid" \
        --document-name "AWS-RunPowerShellScript" \
        --parameters 'commands=["cd C:\\temp\\context-reset-test; python new_session.py --project-dir C:\\temp\\context-reset-test --dry-run 2>&1"]' \
        --timeout-seconds 60 \
        --query 'Command.CommandId' --output text)

    sleep 10
    aws ssm get-command-invocation \
        --command-id "$CMD_ID" --instance-id "$iid" \
        --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' \
        --output text 2>&1
}

cleanup() {
    local iid="${2:-}"
    if [[ -z "$iid" ]]; then
        echo "Usage: $0 cleanup <instance-id>"
        exit 1
    fi
    echo "Terminating $iid..."
    aws ec2 terminate-instances --instance-ids "$iid" \
        --query 'TerminatingInstances[0].CurrentState.Name' --output text
}

case "$ACTION" in
    create) create_instance ;;
    check) check_instance "$@" ;;
    test) run_tests "$@" ;;
    cleanup) cleanup "$@" ;;
    *) echo "Usage: $0 {create|check <id>|test <id>|cleanup <id>}" ;;
esac
