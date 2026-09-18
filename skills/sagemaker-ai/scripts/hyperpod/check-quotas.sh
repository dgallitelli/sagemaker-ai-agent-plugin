#!/bin/bash
# check-quotas.sh
# Checks and displays SageMaker HyperPod service quotas

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-west-2}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--region REGION]"
            echo ""
            echo "Displays SageMaker HyperPod service quotas for the specified region."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "SageMaker HyperPod Service Quotas"
echo "Region: $REGION"
echo "=========================================="
echo ""

# Function to get quota
get_quota() {
    local quota_code=$1
    local quota_name=$2

    local value=$(aws service-quotas get-service-quota \
        --service-code sagemaker \
        --quota-code "$quota_code" \
        --region "$REGION" \
        --query "Quota.Value" \
        --output text 2>/dev/null || echo "N/A")

    printf "%-45s %s\n" "$quota_name" "$value"
}

# Function to check for pending requests
check_pending() {
    local quota_code=$1

    local pending=$(aws service-quotas list-requested-service-quota-change-history-by-quota \
        --service-code sagemaker \
        --quota-code "$quota_code" \
        --region "$REGION" \
        --query "RequestedQuotas[?Status=='PENDING'].DesiredValue" \
        --output text 2>/dev/null || echo "")

    if [[ -n "$pending" ]]; then
        echo " (pending: $pending)"
    fi
}

echo "Instance Type Quotas for HyperPod Clusters:"
echo "---------------------------------------------"
printf "%-45s %s\n" "Instance Type" "Quota"
echo "---------------------------------------------"

# P4d instances
get_quota "L-85E5BF1E" "ml.p4d.24xlarge for cluster usage"

# P4de instances
get_quota "L-4F38DDAA" "ml.p4de.24xlarge for cluster usage"

# P5 instances
get_quota "L-A9F29A4E" "ml.p5.48xlarge for cluster usage"

# Trainium instances
get_quota "L-7EA2A41E" "ml.trn1.32xlarge for cluster usage"
get_quota "L-5F10CB7E" "ml.trn1n.32xlarge for cluster usage"

# G5 instances (if available)
get_quota "L-1A4B6BB5" "ml.g5.48xlarge for cluster usage"

echo ""
echo "---------------------------------------------"
echo ""

# Check EC2 quotas
echo "Related EC2 Quotas:"
echo "---------------------------------------------"
printf "%-45s %s\n" "Quota Name" "Value"
echo "---------------------------------------------"

# P instances
P_QUOTA=$(aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code "L-417A185B" \
    --region "$REGION" \
    --query "Quota.Value" \
    --output text 2>/dev/null || echo "N/A")
printf "%-45s %s\n" "Running On-Demand P instances (vCPUs)" "$P_QUOTA"

# Trainium instances
TRN_QUOTA=$(aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code "L-6B0D517C" \
    --region "$REGION" \
    --query "Quota.Value" \
    --output text 2>/dev/null || echo "N/A")
printf "%-45s %s\n" "Running On-Demand Trn instances (vCPUs)" "$TRN_QUOTA"

echo ""
echo "---------------------------------------------"
echo ""

# Calculate capacity
echo "Capacity Calculator:"
echo "---------------------------------------------"
echo ""
echo "Instance Type         vCPUs/inst  Max Instances (based on EC2 quota)"
echo "---------------------------------------------"

# P4d: 96 vCPUs
if [[ "$P_QUOTA" != "N/A" ]]; then
    P4D_MAX=$((${P_QUOTA%.*} / 96))
    printf "%-20s  %-10s  %s\n" "ml.p4d.24xlarge" "96" "$P4D_MAX"
fi

# P5: 192 vCPUs
if [[ "$P_QUOTA" != "N/A" ]]; then
    P5_MAX=$((${P_QUOTA%.*} / 192))
    printf "%-20s  %-10s  %s\n" "ml.p5.48xlarge" "192" "$P5_MAX"
fi

# Trn1: 128 vCPUs
if [[ "$TRN_QUOTA" != "N/A" ]]; then
    TRN_MAX=$((${TRN_QUOTA%.*} / 128))
    printf "%-20s  %-10s  %s\n" "ml.trn1.32xlarge" "128" "$TRN_MAX"
fi

echo ""
echo "---------------------------------------------"
echo ""

# Check for pending quota requests
echo "Pending Quota Requests:"
echo "---------------------------------------------"

PENDING=$(aws service-quotas list-requested-service-quota-change-history \
    --service-code sagemaker \
    --region "$REGION" \
    --query "RequestedQuotas[?Status=='PENDING'].[QuotaName,DesiredValue,Status]" \
    --output table 2>/dev/null || echo "None")

if [[ "$PENDING" == "None" || -z "$PENDING" ]]; then
    echo "No pending requests"
else
    echo "$PENDING"
fi

echo ""
echo "---------------------------------------------"
echo ""

# Instructions for requesting increases
echo "To request a quota increase:"
echo ""
echo "aws service-quotas request-service-quota-increase \\"
echo "  --service-code sagemaker \\"
echo "  --quota-code <QUOTA_CODE> \\"
echo "  --desired-value <VALUE> \\"
echo "  --region $REGION"
echo ""
echo "Common quota codes:"
echo "  L-85E5BF1E  ml.p4d.24xlarge"
echo "  L-4F38DDAA  ml.p4de.24xlarge"
echo "  L-A9F29A4E  ml.p5.48xlarge"
echo "  L-7EA2A41E  ml.trn1.32xlarge"
echo "  L-5F10CB7E  ml.trn1n.32xlarge"
