#!/bin/bash
# diagnose-cluster.sh
# Diagnoses issues with HyperPod clusters

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
REGION="${AWS_DEFAULT_REGION:-us-west-2}"
CLUSTER_NAME=""
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 --cluster-name NAME [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --cluster-name NAME      HyperPod cluster name"
            echo ""
            echo "Options:"
            echo "  --region REGION          AWS region (default: us-west-2)"
            echo "  --verbose                Show detailed output"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$CLUSTER_NAME" ]]; then
    echo "Error: --cluster-name is required"
    exit 1
fi

echo "=========================================="
echo "HyperPod Cluster Diagnostics"
echo "=========================================="
echo "Cluster: $CLUSTER_NAME"
echo "Region: $REGION"
echo "Time: $(date)"
echo ""

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}!${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# ==========================================
# 1. Cluster Status
# ==========================================
echo "--- Cluster Status ---"

CLUSTER_INFO=$(aws sagemaker describe-cluster \
    --cluster-name "$CLUSTER_NAME" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "{}")

if [[ "$CLUSTER_INFO" == "{}" ]]; then
    error "Cluster $CLUSTER_NAME not found in region $REGION"
    exit 1
fi

CLUSTER_STATUS=$(echo "$CLUSTER_INFO" | jq -r '.ClusterStatus')
CLUSTER_ARN=$(echo "$CLUSTER_INFO" | jq -r '.ClusterArn')
CREATION_TIME=$(echo "$CLUSTER_INFO" | jq -r '.CreationTime')
FAILURE_MESSAGE=$(echo "$CLUSTER_INFO" | jq -r '.FailureMessage // empty')

echo "Cluster ARN: $CLUSTER_ARN"
echo "Status: $CLUSTER_STATUS"
echo "Created: $CREATION_TIME"

if [[ "$CLUSTER_STATUS" == "InService" ]]; then
    success "Cluster is InService"
elif [[ "$CLUSTER_STATUS" == "Creating" ]]; then
    info "Cluster is still being created"
elif [[ "$CLUSTER_STATUS" == "Failed" ]]; then
    error "Cluster is in Failed state"
    if [[ -n "$FAILURE_MESSAGE" ]]; then
        error "Failure message: $FAILURE_MESSAGE"
    fi
else
    warning "Cluster status: $CLUSTER_STATUS"
fi

# ==========================================
# 2. Instance Groups
# ==========================================
echo ""
echo "--- Instance Groups ---"

INSTANCE_GROUPS=$(echo "$CLUSTER_INFO" | jq -r '.InstanceGroups')

echo "Instance Groups:"
echo "$INSTANCE_GROUPS" | jq -r '.[] | "  - " + .InstanceGroupName + " (" + .InstanceType + "): " + (.CurrentCount|tostring) + "/" + (.TargetCount|tostring)'

echo ""

# ==========================================
# 3. Node Status
# ==========================================
echo "--- Node Status ---"

NODES=$(aws sagemaker list-cluster-nodes \
    --cluster-name "$CLUSTER_NAME" \
    --region "$REGION" \
    --query "ClusterNodeSummaries" \
    --output json 2>/dev/null || echo "[]")

NODE_COUNT=$(echo "$NODES" | jq 'length')
echo "Total nodes: $NODE_COUNT"
echo ""

if [[ "$NODE_COUNT" -gt 0 ]]; then
    printf "%-20s %-25s %-15s %s\n" "Instance Group" "Node ID" "Status" "Instance ID"
    echo "---------------------------------------------------------------------"

    HEALTHY=0
    UNHEALTHY=0

    echo "$NODES" | jq -r '.[] | [.InstanceGroupName, .NodeId, .InstanceStatus.Status, .InstanceId] | @tsv' | while IFS=$'\t' read -r group node_id status instance_id; do
        if [[ "$status" == "Running" ]]; then
            STATUS_ICON="${GREEN}●${NC}"
            ((HEALTHY++)) || true
        elif [[ "$status" == "Pending" ]]; then
            STATUS_ICON="${YELLOW}●${NC}"
        else
            STATUS_ICON="${RED}●${NC}"
            ((UNHEALTHY++)) || true
        fi
        printf "%-20s %-25s %-15b %s\n" "$group" "$node_id" "$STATUS_ICON $status" "$instance_id"
    done

    echo ""
    echo "Node health summary:"
    RUNNING=$(echo "$NODES" | jq '[.[] | select(.InstanceStatus.Status == "Running")] | length')
    PENDING=$(echo "$NODES" | jq '[.[] | select(.InstanceStatus.Status == "Pending")] | length')
    FAILED=$(echo "$NODES" | jq '[.[] | select(.InstanceStatus.Status != "Running" and .InstanceStatus.Status != "Pending")] | length')

    success "Running: $RUNNING"
    if [[ "$PENDING" -gt 0 ]]; then
        info "Pending: $PENDING"
    fi
    if [[ "$FAILED" -gt 0 ]]; then
        error "Failed/Other: $FAILED"
    fi
fi

# ==========================================
# 4. VPC Configuration
# ==========================================
echo ""
echo "--- VPC Configuration ---"

VPC_CONFIG=$(echo "$CLUSTER_INFO" | jq -r '.VpcConfig')
VPC_ID=$(echo "$VPC_CONFIG" | jq -r '.VpcId // empty')
SUBNETS=$(echo "$VPC_CONFIG" | jq -r '.Subnets[]? // empty')
SECURITY_GROUPS=$(echo "$VPC_CONFIG" | jq -r '.SecurityGroupIds[]? // empty')

if [[ -n "$VPC_ID" ]]; then
    echo "VPC ID: $VPC_ID"
    echo "Subnets: $(echo $SUBNETS | tr '\n' ', ' | sed 's/,$//')"
    echo "Security Groups: $(echo $SECURITY_GROUPS | tr '\n' ', ' | sed 's/,$//')"
else
    warning "VPC configuration not available"
fi

# ==========================================
# 5. Recent CloudWatch Logs
# ==========================================
echo ""
echo "--- Recent CloudWatch Logs ---"

LOG_GROUP="/aws/sagemaker/Clusters/$CLUSTER_NAME"

# Check if log group exists
LOG_EXISTS=$(aws logs describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP" \
    --region "$REGION" \
    --query "logGroups[0].logGroupName" \
    --output text 2>/dev/null || echo "None")

if [[ "$LOG_EXISTS" != "None" && -n "$LOG_EXISTS" ]]; then
    success "Log group exists: $LOG_GROUP"

    # Get recent log streams
    LOG_STREAMS=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --limit 5 \
        --region "$REGION" \
        --query "logStreams[*].logStreamName" \
        --output json 2>/dev/null || echo "[]")

    echo "Recent log streams:"
    echo "$LOG_STREAMS" | jq -r '.[] | "  - " + .'

    if [[ "$VERBOSE" == true ]]; then
        echo ""
        echo "Recent log events:"
        aws logs tail "$LOG_GROUP" \
            --since 1h \
            --region "$REGION" \
            --format short 2>/dev/null | head -20 || true
    else
        echo ""
        info "Use --verbose to see recent log events"
    fi
else
    warning "Log group not found: $LOG_GROUP"
fi

# ==========================================
# 6. SSM Connectivity Check
# ==========================================
echo ""
echo "--- SSM Connectivity ---"

if [[ "$NODE_COUNT" -gt 0 ]]; then
    FIRST_INSTANCE=$(echo "$NODES" | jq -r '.[0].InstanceId // empty')

    if [[ -n "$FIRST_INSTANCE" ]]; then
        SSM_STATUS=$(aws ssm describe-instance-information \
            --filters "Key=InstanceIds,Values=$FIRST_INSTANCE" \
            --region "$REGION" \
            --query "InstanceInformationList[0].PingStatus" \
            --output text 2>/dev/null || echo "Unknown")

        if [[ "$SSM_STATUS" == "Online" ]]; then
            success "SSM agent online for $FIRST_INSTANCE"
            echo "Connect with: aws ssm start-session --target $FIRST_INSTANCE --region $REGION"
        elif [[ "$SSM_STATUS" == "Unknown" ]]; then
            warning "SSM status unknown for $FIRST_INSTANCE"
        else
            error "SSM agent not online for $FIRST_INSTANCE (status: $SSM_STATUS)"
        fi
    fi
else
    info "No nodes to check SSM connectivity"
fi

# ==========================================
# 7. Orchestrator-Specific Checks
# ==========================================
echo ""
echo "--- Orchestrator Status ---"

# Detect orchestrator from cluster info
ORCHESTRATOR=$(echo "$CLUSTER_INFO" | jq -r '.Orchestrator.Eks // empty')

if [[ -n "$ORCHESTRATOR" && "$ORCHESTRATOR" != "null" ]]; then
    echo "Orchestrator: EKS"
    EKS_CLUSTER=$(echo "$ORCHESTRATOR" | jq -r '.ClusterArn // empty')
    if [[ -n "$EKS_CLUSTER" ]]; then
        echo "EKS Cluster ARN: $EKS_CLUSTER"

        # Check EKS cluster status
        EKS_NAME=$(echo "$EKS_CLUSTER" | grep -oP 'cluster/\K[^/]+')
        EKS_STATUS=$(aws eks describe-cluster \
            --name "$EKS_NAME" \
            --region "$REGION" \
            --query "cluster.status" \
            --output text 2>/dev/null || echo "Unknown")

        if [[ "$EKS_STATUS" == "ACTIVE" ]]; then
            success "EKS cluster is ACTIVE"
        else
            warning "EKS cluster status: $EKS_STATUS"
        fi
    fi
else
    echo "Orchestrator: Slurm"
    info "Connect to controller node to check Slurm status"
fi

# ==========================================
# 8. Recommendations
# ==========================================
echo ""
echo "--- Recommendations ---"

if [[ "$CLUSTER_STATUS" == "Failed" ]]; then
    echo "1. Check the failure message above"
    echo "2. Review CloudWatch logs for detailed errors"
    echo "3. Verify prerequisites: ./validate-prerequisites.sh"
    echo "4. Check service quotas: ./check-quotas.sh"
fi

if [[ "$FAILED" -gt 0 ]] 2>/dev/null; then
    echo "1. Check failed node details:"
    echo "   aws sagemaker describe-cluster-node --cluster-name $CLUSTER_NAME --node-id <node-id>"
    echo "2. Review lifecycle script logs on the node"
    echo "3. Consider replacing unhealthy nodes"
fi

if [[ "$CLUSTER_STATUS" == "Creating" ]]; then
    echo "1. Wait for cluster creation to complete"
    echo "2. Monitor progress in CloudWatch logs"
    echo "3. Typical creation time: 15-30 minutes"
fi

if [[ "$CLUSTER_STATUS" == "InService" ]]; then
    success "Cluster appears healthy"
    echo "Next steps:"
    echo "1. Connect to cluster:"
    if [[ -n "$ORCHESTRATOR" && "$ORCHESTRATOR" != "null" ]]; then
        echo "   hyp get kubeconfig"
        echo "   kubectl get nodes"
    else
        echo "   aws ssm start-session --target <instance-id> --region $REGION"
        echo "   sinfo"
    fi
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="
echo "Cluster: $CLUSTER_NAME"
echo "Status: $CLUSTER_STATUS"
echo "Nodes: $NODE_COUNT"
echo ""
echo "For detailed logs:"
echo "  aws logs tail $LOG_GROUP --follow --region $REGION"
