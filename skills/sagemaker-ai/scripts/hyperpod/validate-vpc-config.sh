#!/bin/bash
# validate-vpc-config.sh
# Validates VPC configuration for HyperPod clusters

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
REGION="${AWS_DEFAULT_REGION:-us-west-2}"
VPC_ID=""
ORCHESTRATOR="eks"
INSTANCE_COUNT=4

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --vpc-id)
            VPC_ID="$2"
            shift 2
            ;;
        --orchestrator)
            ORCHESTRATOR="$2"
            shift 2
            ;;
        --instance-count)
            INSTANCE_COUNT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --vpc-id VPC_ID [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --vpc-id VPC_ID          VPC ID to validate"
            echo ""
            echo "Options:"
            echo "  --region REGION          AWS region (default: us-west-2)"
            echo "  --orchestrator TYPE      eks or slurm (default: eks)"
            echo "  --instance-count N       Number of instances (default: 4)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$VPC_ID" ]]; then
    echo "Error: --vpc-id is required"
    exit 1
fi

echo "=========================================="
echo "VPC Configuration Validation"
echo "=========================================="
echo "VPC ID: $VPC_ID"
echo "Region: $REGION"
echo "Orchestrator: $ORCHESTRATOR"
echo "Instance Count: $INSTANCE_COUNT"
echo ""

ERRORS=0
WARNINGS=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

check_warn() {
    echo -e "${YELLOW}!${NC} $1"
    ((WARNINGS++))
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# ==========================================
# 1. VPC Basic Configuration
# ==========================================
echo "--- VPC Basic Configuration ---"

# Check VPC exists
VPC_INFO=$(aws ec2 describe-vpcs \
    --vpc-ids "$VPC_ID" \
    --region "$REGION" \
    --query "Vpcs[0]" \
    --output json 2>/dev/null || echo "{}")

if [[ "$VPC_INFO" == "{}" ]]; then
    check_fail "VPC $VPC_ID not found"
    exit 1
fi

VPC_STATE=$(echo "$VPC_INFO" | jq -r '.State')
VPC_CIDR=$(echo "$VPC_INFO" | jq -r '.CidrBlock')

if [[ "$VPC_STATE" == "available" ]]; then
    check_pass "VPC is available"
    check_info "VPC CIDR: $VPC_CIDR"
else
    check_fail "VPC state is $VPC_STATE (expected: available)"
fi

# Check DNS settings
DNS_HOSTNAMES=$(aws ec2 describe-vpc-attribute \
    --vpc-id "$VPC_ID" \
    --attribute enableDnsHostnames \
    --region "$REGION" \
    --query "EnableDnsHostnames.Value" \
    --output text)

DNS_SUPPORT=$(aws ec2 describe-vpc-attribute \
    --vpc-id "$VPC_ID" \
    --attribute enableDnsSupport \
    --region "$REGION" \
    --query "EnableDnsSupport.Value" \
    --output text)

if [[ "$DNS_HOSTNAMES" == "true" ]]; then
    check_pass "DNS hostnames enabled"
else
    check_fail "DNS hostnames not enabled"
fi

if [[ "$DNS_SUPPORT" == "true" ]]; then
    check_pass "DNS support enabled"
else
    check_fail "DNS support not enabled"
fi

# ==========================================
# 2. Subnet Analysis
# ==========================================
echo ""
echo "--- Subnet Analysis ---"

# Calculate required IPs
if [[ "$ORCHESTRATOR" == "eks" ]]; then
    IPS_PER_NODE=81
else
    IPS_PER_NODE=32
fi
REQUIRED_IPS=$((INSTANCE_COUNT * IPS_PER_NODE))

echo "Required IPs per node ($ORCHESTRATOR): $IPS_PER_NODE"
echo "Total required IPs: $REQUIRED_IPS"
echo ""

# Get all subnets
SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query "Subnets[*].[SubnetId,CidrBlock,AvailabilityZone,AvailableIpAddressCount,MapPublicIpOnLaunch]" \
    --output json)

echo "Subnets in VPC:"
echo "---------------------------------------------"
printf "%-25s %-18s %-15s %-8s %s\n" "Subnet ID" "CIDR" "AZ" "Avail IPs" "Public"
echo "---------------------------------------------"

SUITABLE_SUBNETS=0
PRIVATE_SUBNETS=0

echo "$SUBNETS" | jq -r '.[] | @tsv' | while IFS=$'\t' read -r subnet_id cidr az available_ips public; do
    if [[ "$public" == "false" ]]; then
        PUBLIC_STR="No"
        ((PRIVATE_SUBNETS++)) || true
    else
        PUBLIC_STR="Yes"
    fi

    if [[ "$available_ips" -ge "$REQUIRED_IPS" ]]; then
        SUFFIX=" ✓"
        ((SUITABLE_SUBNETS++)) || true
    else
        SUFFIX=""
    fi

    printf "%-25s %-18s %-15s %-8s %s%s\n" "$subnet_id" "$cidr" "$az" "$available_ips" "$PUBLIC_STR" "$SUFFIX"
done

echo ""

# Check for suitable subnets
SUITABLE_COUNT=$(echo "$SUBNETS" | jq "[.[] | select(.[3] >= $REQUIRED_IPS)] | length")
PRIVATE_COUNT=$(echo "$SUBNETS" | jq "[.[] | select(.[4] == false)] | length")

if [[ "$SUITABLE_COUNT" -gt 0 ]]; then
    check_pass "$SUITABLE_COUNT subnet(s) have sufficient IP capacity"
else
    check_fail "No subnets have sufficient IP capacity ($REQUIRED_IPS IPs needed)"
fi

if [[ "$PRIVATE_COUNT" -gt 0 ]]; then
    check_pass "$PRIVATE_COUNT private subnet(s) available"
else
    check_warn "No private subnets found (recommended for HyperPod)"
fi

# ==========================================
# 3. Internet Connectivity
# ==========================================
echo ""
echo "--- Internet Connectivity ---"

# Check Internet Gateway
IGW=$(aws ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query "InternetGateways[0].InternetGatewayId" \
    --output text 2>/dev/null || echo "None")

if [[ "$IGW" != "None" && -n "$IGW" ]]; then
    check_pass "Internet Gateway attached: $IGW"
else
    check_warn "No Internet Gateway found"
fi

# Check NAT Gateway
NAT_GWS=$(aws ec2 describe-nat-gateways \
    --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available" \
    --region "$REGION" \
    --query "NatGateways[*].[NatGatewayId,SubnetId]" \
    --output json 2>/dev/null || echo "[]")

NAT_COUNT=$(echo "$NAT_GWS" | jq 'length')

if [[ "$NAT_COUNT" -gt 0 ]]; then
    check_pass "$NAT_COUNT NAT Gateway(s) found"
    echo "$NAT_GWS" | jq -r '.[] | "  - " + .[0] + " in " + .[1]'
else
    check_warn "No NAT Gateway found (may need VPC endpoints instead)"
fi

# ==========================================
# 4. VPC Endpoints
# ==========================================
echo ""
echo "--- VPC Endpoints ---"

ENDPOINTS=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query "VpcEndpoints[*].[ServiceName,VpcEndpointType,State]" \
    --output json 2>/dev/null || echo "[]")

echo "Current VPC Endpoints:"
if [[ $(echo "$ENDPOINTS" | jq 'length') -gt 0 ]]; then
    printf "%-50s %-12s %s\n" "Service" "Type" "State"
    echo "---------------------------------------------"
    echo "$ENDPOINTS" | jq -r '.[] | [.[0], .[1], .[2]] | @tsv' | while IFS=$'\t' read -r service type state; do
        printf "%-50s %-12s %s\n" "$service" "$type" "$state"
    done
else
    echo "  None configured"
fi

echo ""

# Check required endpoints
S3_ENDPOINT=$(echo "$ENDPOINTS" | jq -r ".[] | select(.[0] | contains(\"s3\")) | .[2]" | head -1)
if [[ "$S3_ENDPOINT" == "available" ]]; then
    check_pass "S3 endpoint available (required for lifecycle scripts)"
else
    check_fail "S3 endpoint not found (required for lifecycle scripts)"
fi

# Check recommended endpoints
SSM_ENDPOINT=$(echo "$ENDPOINTS" | jq -r ".[] | select(.[0] | contains(\"ssm\") and (contains(\"ssmmessages\") | not)) | .[2]" | head -1)
if [[ "$SSM_ENDPOINT" == "available" ]]; then
    check_pass "SSM endpoint available"
else
    check_warn "SSM endpoint not found (recommended for node access)"
fi

ECR_ENDPOINT=$(echo "$ENDPOINTS" | jq -r ".[] | select(.[0] | contains(\"ecr.api\")) | .[2]" | head -1)
if [[ "$ECR_ENDPOINT" == "available" ]]; then
    check_pass "ECR API endpoint available"
else
    check_warn "ECR endpoint not found (recommended if using containers)"
fi

# ==========================================
# 5. Security Groups
# ==========================================
echo ""
echo "--- Security Groups ---"

SECURITY_GROUPS=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query "SecurityGroups[*].[GroupId,GroupName]" \
    --output json 2>/dev/null || echo "[]")

echo "Security Groups in VPC:"
echo "$SECURITY_GROUPS" | jq -r '.[] | "  - " + .[0] + " (" + .[1] + ")"'

echo ""

# Look for HyperPod-suitable security group
echo "Checking for self-referencing security groups (required for EFA):"

echo "$SECURITY_GROUPS" | jq -r '.[0][0]' | while read -r sg_id; do
    if [[ -z "$sg_id" || "$sg_id" == "null" ]]; then
        continue
    fi

    SELF_REF=$(aws ec2 describe-security-groups \
        --group-ids "$sg_id" \
        --region "$REGION" \
        --query "SecurityGroups[0].IpPermissions[?UserIdGroupPairs[?GroupId=='$sg_id']]" \
        --output json 2>/dev/null || echo "[]")

    if [[ $(echo "$SELF_REF" | jq 'length') -gt 0 ]]; then
        check_pass "Security group $sg_id has self-referencing rules"
    fi
done

# ==========================================
# 6. Route Tables
# ==========================================
echo ""
echo "--- Route Tables ---"

ROUTE_TABLES=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --region "$REGION" \
    --query "RouteTables[*].[RouteTableId,Associations[0].Main]" \
    --output json 2>/dev/null || echo "[]")

echo "Route Tables:"
echo "$ROUTE_TABLES" | jq -r '.[] | "  - " + .[0] + (if .[1] == true then " (Main)" else "" end)'

# ==========================================
# Summary
# ==========================================
echo ""
echo "=========================================="
echo "Validation Summary"
echo "=========================================="

if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}Passed with $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}Failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    exit 1
fi
