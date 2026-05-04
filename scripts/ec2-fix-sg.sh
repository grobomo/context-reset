#!/usr/bin/env bash
# Add RDP port to the security group and verify both ports.
set -euo pipefail

SG_ID="sg-032e0f946606cfbb4"

echo "Adding port 3389 (RDP) to $SG_ID..."
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port 3389 --cidr 0.0.0.0/0 2>&1 || echo "(already exists)"

echo ""
echo "Current inbound rules:"
aws ec2 describe-security-groups --group-ids "$SG_ID" \
    --query 'SecurityGroups[0].IpPermissions[*].{Port:FromPort,Proto:IpProtocol,CIDRs:IpRanges[*].CidrIp}' \
    --output table
