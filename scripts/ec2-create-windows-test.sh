#!/usr/bin/env bash
# Create a Windows Server 2022 EC2 instance with OpenSSH pre-enabled.
# Uses user-data to install Python and enable OpenSSH on boot.
# Usage: scripts/ec2-create-windows-test.sh
set -euo pipefail

INSTANCE_NAME="ctx-reset-win-test"
KEY_NAME="jumpbox-key"
INSTANCE_TYPE="t3.medium"

# Find Windows Server 2022 AMI (has OpenSSH built-in)
echo "Finding Windows Server 2022 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters \
        "Name=name,Values=Windows_Server-2022-English-Full-Base-*" \
        "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text)

echo "AMI: $AMI_ID"

# Find security group that allows SSH (port 22)
echo "Finding security group with port 22..."
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=ip-permission.from-port,Values=22" \
              "Name=ip-permission.to-port,Values=22" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
    echo "No security group with port 22 found. Creating one..."
    SG_ID=$(aws ec2 create-security-group \
        --group-name ctx-reset-test-sg \
        --description "Context-reset cross-platform testing" \
        --query 'GroupId' --output text)
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
        --protocol tcp --port 22 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
        --protocol tcp --port 3389 --cidr 0.0.0.0/0
    echo "Created security group: $SG_ID"
fi
echo "Security group: $SG_ID"

# User-data script to enable OpenSSH and install Python
USERDATA=$(cat <<'UDEOF'
<powershell>
# Enable OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# Set default shell to PowerShell for SSH
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force

# Install Python via winget (Windows Package Manager)
# Fallback: download from python.org
$pythonUrl = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
$installer = "$env:TEMP\python-installer.exe"
Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing
Start-Process -Wait -FilePath $installer -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1'
Remove-Item $installer

# Signal completion
echo "SETUP COMPLETE" > C:\setup-done.txt
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
    --user-data "$USERDATA_B64" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "Instance launched: $INSTANCE_ID"
echo "Waiting for running state..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo ""
echo "=== Instance ready ==="
echo "Instance ID: $INSTANCE_ID"
echo "Public IP:   $IP"
echo "User:        Administrator"
echo "Key:         $KEY_NAME"
echo ""
echo "OpenSSH + Python installing via user-data (takes ~5-10 min)."
echo "Check with: ssh -i ~/.ssh/cpp-keys/jumpbox.pem Administrator@$IP 'python --version'"
echo ""
echo "Update ec2-test.sh INSTANCE_IPS[windows]=$IP after setup completes."
