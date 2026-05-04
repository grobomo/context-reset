#!/usr/bin/env bash
# Use PowerShell remoting via WinRM to enable SSH on a Windows EC2 instance.
# Alternative: if WinRM is blocked, provides instructions for manual RDP fix.
set -euo pipefail

IP="52.14.168.89"
PASSWORD='K*?GBfP7G3MDp.FTUVG6UT-9eGO.UGCR'

echo "=== Enable SSH on Windows EC2 ($IP) ==="
echo ""
echo "RDP is reachable. SSH port 22 is blocked by Windows Firewall."
echo ""
echo "Option 1: RDP in and run this PowerShell as Administrator:"
echo ""
echo '  # Enable OpenSSH Server'
echo '  Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0'
echo '  Start-Service sshd'
echo '  Set-Service -Name sshd -StartupType Automatic'
echo '  New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH SSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22'
echo '  New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force'
echo ''
echo "RDP connection details:"
echo "  Host: $IP"
echo "  User: Administrator"
echo "  Pass: $PASSWORD"
echo ""
echo "Option 2: Terminate and recreate with updated user-data that includes firewall rule."
