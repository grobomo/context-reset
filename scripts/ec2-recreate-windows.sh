#!/usr/bin/env bash
# Terminate old Windows test instance and create new one with SSH + firewall.
set -euo pipefail

OLD_ID="i-005561c2e16240c67"
KEY_NAME="jumpbox-key"
INSTANCE_TYPE="t3.medium"
SG_ID="sg-032e0f946606cfbb4"

echo "Terminating old instance $OLD_ID..."
aws ec2 terminate-instances --instance-ids "$OLD_ID" \
    --query 'TerminatingInstances[0].CurrentState.Name' --output text

# Find latest Windows Server 2022 AMI
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=Windows_Server-2022-English-Full-Base-*" "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)
echo "AMI: $AMI_ID"

# User-data with firewall rule included
USERDATA=$(cat <<'UDEOF'
<powershell>
# Log to file for debugging
$log = "C:\setup-log.txt"
"$(Get-Date) Starting setup" | Out-File $log

# Install OpenSSH Server
"$(Get-Date) Installing OpenSSH..." | Out-File $log -Append
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
"$(Get-Date) OpenSSH installed" | Out-File $log -Append

# Start and enable sshd
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
"$(Get-Date) sshd started" | Out-File $log -Append

# Open firewall for SSH
New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue
"$(Get-Date) Firewall rule added" | Out-File $log -Append

# Set default shell to PowerShell
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
"$(Get-Date) Default shell set to PowerShell" | Out-File $log -Append

# Install Python
$pythonUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$installer = "$env:TEMP\python-installer.exe"
"$(Get-Date) Downloading Python..." | Out-File $log -Append
Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing
"$(Get-Date) Installing Python..." | Out-File $log -Append
Start-Process -Wait -FilePath $installer -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1'
Remove-Item $installer -ErrorAction SilentlyContinue
"$(Get-Date) Python installed" | Out-File $log -Append

# Restart sshd so it picks up PATH changes
Restart-Service sshd
"$(Get-Date) SETUP COMPLETE" | Out-File $log -Append
</powershell>
UDEOF
)

USERDATA_B64=$(echo "$USERDATA" | base64 -w 0)

echo "Launching new instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data "$USERDATA_B64" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=ctx-reset-win-test}]" \
    --query 'Instances[0].InstanceId' --output text)

echo "Instance: $INSTANCE_ID"
echo "Waiting for running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo ""
echo "=== New Windows instance ==="
echo "Instance: $INSTANCE_ID"
echo "IP: $IP"
echo "User-data includes: OpenSSH + firewall rule + Python"
echo "Wait ~10 min for setup, then: scripts/ec2-test-windows.sh setup"
echo ""
echo "Update CTX_RESET_WIN_IP=$IP or edit scripts."
