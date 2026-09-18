#!/bin/bash
# validate-prerequisites.sh
# Validates all prerequisites before creating a HyperPod cluster

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
REGION="${AWS_DEFAULT_REGION:-us-west-2}"
VPC_ID=""
SUBNET_IDS=""
S3_BUCKET=""
INSTANCE_TYPE="ml.p5.48xlarge"
INSTANCE_COUNT=4
ORCHESTRATOR="eks"

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
        --subnet-ids)
            SUBNET_IDS="$2"
            shift 2
            ;;
        --bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        --instance-type)
            INSTANCE_TYPE="$2"
            shift 2
            ;;
        --instance-count)
            INSTANCE_COUNT="$2"
            shift 2
            ;;
        --orchestrator)
            ORCHESTRATOR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --region REGION          AWS region (default: us-west-2)"
            echo "  --vpc-id VPC_ID          VPC ID to validate"
            echo "  --subnet-ids IDS         Comma-separated subnet IDs"
            echo "  --bucket S3_URI          S3 bucket for lifecycle scripts"
            echo "  --instance-type TYPE     Instance type (default: ml.p5.48xlarge)"
            echo "  --instance-count N       Number of instances (default: 4)"
            echo "  --orchestrator TYPE      eks or slurm (default: eks)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "HyperPod Prerequisites Validation"
echo "=========================================="
echo "Region: $REGION"
echo "Orchestrator: $ORCHESTRATOR"
echo "Instance Type: $INSTANCE_TYPE"
echo "Instance Count: $INSTANCE_COUNT"
echo ""

ERRORS=0
WARNINGS=0

# Helper functions
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

# ==========================================
# 1. AWS Credentials Check
# ==========================================
echo "--- Checking AWS Credentials ---"

if aws sts get-caller-identity --region "$REGION" > /dev/null 2>&1; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    check_pass "AWS credentials valid (Account: $ACCOUNT_ID)"
else
    check_fail "AWS credentials not configured or invalid"
    echo "Run: aws configure"
    exit 1
fi

# ==========================================
# 2. Service Quotas Check
# ==========================================
echo ""
echo "--- Checking Service Quotas ---"

# Get instance quota code based on instance type
get_quota_code() {
    local instance_type=$1
    case $instance_type in
        ml.p4d.24xlarge)  echo "L-85E5BF1E" ;;
        ml.p4de.24xlarge) echo "L-4F38DDAA" ;;
        ml.p5.48xlarge)   echo "L-A9F29A4E" ;;
        ml.trn1.32xlarge) echo "L-7EA2A41E" ;;
        ml.trn1n.32xlarge) echo "L-5F10CB7E" ;;
        *) echo "" ;;
    esac
}

QUOTA_CODE=$(get_quota_code "$INSTANCE_TYPE")
if [[ -n "$QUOTA_CODE" ]]; then
    CURRENT_QUOTA=$(aws service-quotas get-service-quota \
        --service-code sagemaker \
        --quota-code "$QUOTA_CODE" \
        --region "$REGION" \
        --query "Quota.Value" \
        --output text 2>/dev/null || echo "0")

    if [[ $(echo "$CURRENT_QUOTA >= $INSTANCE_COUNT" | bc -l) -eq 1 ]]; then
        check_pass "SageMaker quota for $INSTANCE_TYPE: $CURRENT_QUOTA (need: $INSTANCE_COUNT)"
    else
        check_fail "Insufficient quota for $INSTANCE_TYPE: $CURRENT_QUOTA (need: $INSTANCE_COUNT)"
        echo "  Request increase: aws service-quotas request-service-quota-increase \\"
        echo "    --service-code sagemaker --quota-code $QUOTA_CODE \\"
        echo "    --desired-value $INSTANCE_COUNT --region $REGION"
    fi
else
    check_warn "Unknown instance type quota code for $INSTANCE_TYPE"
fi

# ==========================================
# 3. VPC Configuration Check
# ==========================================
echo ""
echo "--- Checking VPC Configuration ---"

if [[ -n "$VPC_ID" ]]; then
    # Check VPC exists
    VPC_STATE=$(aws ec2 describe-vpcs \
        --vpc-ids "$VPC_ID" \
        --region "$REGION" \
        --query "Vpcs[0].State" \
        --output text 2>/dev/null || echo "not-found")

    if [[ "$VPC_STATE" == "available" ]]; then
        check_pass "VPC $VPC_ID exists and is available"

        # Check DNS hostnames
        DNS_HOSTNAMES=$(aws ec2 describe-vpc-attribute \
            --vpc-id "$VPC_ID" \
            --attribute enableDnsHostnames \
            --region "$REGION" \
            --query "EnableDnsHostnames.Value" \
            --output text)

        if [[ "$DNS_HOSTNAMES" == "true" ]]; then
            check_pass "DNS hostnames enabled"
        else
            check_fail "DNS hostnames not enabled"
            echo "  Fix: aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames"
        fi
    else
        check_fail "VPC $VPC_ID not found or not available"
    fi
else
    check_warn "VPC ID not provided, skipping VPC checks"
fi

# ==========================================
# 4. Subnet Check
# ==========================================
echo ""
echo "--- Checking Subnet Configuration ---"

if [[ -n "$SUBNET_IDS" ]]; then
    IFS=',' read -ra SUBNETS <<< "$SUBNET_IDS"

    # Calculate required IPs based on orchestrator
    if [[ "$ORCHESTRATOR" == "eks" ]]; then
        IPS_PER_NODE=81
    else
        IPS_PER_NODE=32
    fi
    REQUIRED_IPS=$((INSTANCE_COUNT * IPS_PER_NODE))

    for SUBNET in "${SUBNETS[@]}"; do
        AVAILABLE_IPS=$(aws ec2 describe-subnets \
            --subnet-ids "$SUBNET" \
            --region "$REGION" \
            --query "Subnets[0].AvailableIpAddressCount" \
            --output text 2>/dev/null || echo "0")

        if [[ "$AVAILABLE_IPS" -ge "$REQUIRED_IPS" ]]; then
            check_pass "Subnet $SUBNET has $AVAILABLE_IPS IPs (need: $REQUIRED_IPS)"
        else
            check_fail "Subnet $SUBNET has only $AVAILABLE_IPS IPs (need: $REQUIRED_IPS)"
        fi
    done
else
    check_warn "Subnet IDs not provided, skipping subnet checks"
fi

# ==========================================
# 5. S3 VPC Endpoint Check
# ==========================================
echo ""
echo "--- Checking VPC Endpoints ---"

if [[ -n "$VPC_ID" ]]; then
    S3_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$REGION.s3" \
        --region "$REGION" \
        --query "VpcEndpoints[0].VpcEndpointId" \
        --output text 2>/dev/null || echo "None")

    if [[ "$S3_ENDPOINT" != "None" && -n "$S3_ENDPOINT" ]]; then
        check_pass "S3 VPC endpoint exists: $S3_ENDPOINT"
    else
        check_fail "S3 VPC endpoint not found"
        echo "  Create: aws ec2 create-vpc-endpoint --vpc-id $VPC_ID \\"
        echo "    --service-name com.amazonaws.$REGION.s3 --route-table-ids <rtb-id>"
    fi
fi

# ==========================================
# 6. S3 Bucket Check
# ==========================================
echo ""
echo "--- Checking S3 Lifecycle Scripts ---"

if [[ -n "$S3_BUCKET" ]]; then
    # Extract bucket name from s3:// URI
    BUCKET_NAME=$(echo "$S3_BUCKET" | sed 's|s3://||' | cut -d'/' -f1)

    if aws s3 ls "s3://$BUCKET_NAME" --region "$REGION" > /dev/null 2>&1; then
        check_pass "S3 bucket $BUCKET_NAME accessible"

        # Check for lifecycle scripts
        if aws s3 ls "$S3_BUCKET/on_create.sh" --region "$REGION" > /dev/null 2>&1; then
            check_pass "on_create.sh found"
        else
            check_warn "on_create.sh not found at $S3_BUCKET"
        fi

        if aws s3 ls "$S3_BUCKET/provisioning_parameters.json" --region "$REGION" > /dev/null 2>&1; then
            check_pass "provisioning_parameters.json found"
        else
            check_warn "provisioning_parameters.json not found at $S3_BUCKET"
        fi
    else
        check_fail "Cannot access S3 bucket $BUCKET_NAME"
    fi
else
    check_warn "S3 bucket not provided, skipping S3 checks"
fi

# ==========================================
# 7. IAM Role Check
# ==========================================
echo ""
echo "--- Checking IAM Roles ---"

# Check execution role
if aws iam get-role --role-name HyperPodExecutionRole > /dev/null 2>&1; then
    check_pass "HyperPodExecutionRole exists"
else
    check_warn "HyperPodExecutionRole not found (may have different name)"
fi

# Check node role
if aws iam get-role --role-name HyperPodNodeRole > /dev/null 2>&1; then
    check_pass "HyperPodNodeRole exists"
else
    check_warn "HyperPodNodeRole not found (may have different name)"
fi

# ==========================================
# 8. CLI Tools Check
# ==========================================
echo ""
echo "--- Checking CLI Tools ---"

# AWS CLI
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1 | head -1)
    check_pass "AWS CLI installed: $AWS_VERSION"
else
    check_fail "AWS CLI not installed"
fi

# Session Manager Plugin
if command -v session-manager-plugin &> /dev/null; then
    check_pass "Session Manager Plugin installed"
else
    check_warn "Session Manager Plugin not installed (needed for SSM access)"
fi

# HyperPod CLI (for EKS)
if [[ "$ORCHESTRATOR" == "eks" ]]; then
    if command -v hyp &> /dev/null; then
        HYP_VERSION=$(hyp --version 2>&1 || echo "unknown")
        check_pass "HyperPod CLI installed: $HYP_VERSION"
    else
        check_fail "HyperPod CLI not installed"
        echo "  Install: pip install hyperpod"
    fi

    # kubectl
    if command -v kubectl &> /dev/null; then
        KUBECTL_VERSION=$(kubectl version --client -o json 2>/dev/null | jq -r '.clientVersion.gitVersion' || echo "unknown")
        check_pass "kubectl installed: $KUBECTL_VERSION"
    else
        check_fail "kubectl not installed (required for EKS)"
    fi
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo "=========================================="
echo "Validation Summary"
echo "=========================================="

if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
    echo "Ready to create HyperPod cluster."
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}Passed with $WARNINGS warning(s)${NC}"
    echo "Review warnings before proceeding."
    exit 0
else
    echo -e "${RED}Failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo "Fix errors before creating cluster."
    exit 1
fi
