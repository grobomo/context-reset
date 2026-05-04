#!/usr/bin/env bash
# Check network connectivity and security group for an EC2 instance.
set -euo pipefail

INSTANCE_ID="${1:-i-005561c2e16240c67}"
IP="52.14.168.89"

echo "=== Network check for $INSTANCE_ID ($IP) ==="

# Check security group rules
echo "--- Security group inbound rules ---"
SG_IDS=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].SecurityGroups[*].GroupId' --output text)
echo "Security groups: $SG_IDS"

for sg in $SG_IDS; do
    echo "  Rules for $sg:"
    aws ec2 describe-security-groups --group-ids "$sg" \
        --query 'SecurityGroups[0].IpPermissions[*].{Port:FromPort,Proto:IpProtocol,CIDRs:IpRanges[*].CidrIp}' \
        --output table 2>&1
done

# Check instance console output (shows boot progress)
echo ""
echo "--- Instance console output (last 50 lines) ---"
aws ec2 get-console-output --instance-id "$INSTANCE_ID" \
    --query 'Output' --output text 2>&1 | tail -50 || echo "No console output yet"

# Port scan
echo ""
echo "--- Port connectivity ---"
echo -n "Port 22 (SSH): "
timeout 5 bash -c "echo >/dev/tcp/$IP/22" 2>/dev/null && echo "OPEN" || echo "CLOSED/TIMEOUT"
echo -n "Port 3389 (RDP): "
timeout 5 bash -c "echo >/dev/tcp/$IP/3389" 2>/dev/null && echo "OPEN" || echo "CLOSED/TIMEOUT"
