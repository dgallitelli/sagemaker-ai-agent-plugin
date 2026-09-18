# HyperPod Prerequisites Checklist

Complete all items before creating a HyperPod cluster.

## 1. AWS Account Setup

### Service Quotas

Request quota increases **before** cluster creation. Default quotas are typically insufficient.

| Service | Quota Name | Minimum Required |
|---------|------------|------------------|
| SageMaker | ml.p4d.24xlarge for cluster usage | Number of nodes needed |
| SageMaker | ml.p4de.24xlarge for cluster usage | Number of nodes needed |
| SageMaker | ml.p5.48xlarge for cluster usage | Number of nodes needed |
| SageMaker | ml.trn1.32xlarge for cluster usage | Number of nodes needed |
| SageMaker | ml.trn1n.32xlarge for cluster usage | Number of nodes needed |
| EC2 | Running On-Demand P instances | 8 × number of P4d/P5 nodes |
| EC2 | Running On-Demand Trn instances | 32 × number of Trn1 nodes |
| VPC | VPCs per Region | At least 1 available |
| VPC | Subnets per VPC | At least 2 available |
| VPC | Elastic IPs | 1 per node (if using NAT) |
| EBS | General Purpose SSD (gp3) volume storage | 500GB × number of nodes |

### Check Current Quotas
```bash
# Check SageMaker HyperPod quotas
aws service-quotas list-service-quotas \
  --service-code sagemaker \
  --query "Quotas[?contains(QuotaName, 'cluster')]"

# Check EC2 instance quotas
aws service-quotas list-service-quotas \
  --service-code ec2 \
  --query "Quotas[?contains(QuotaName, 'On-Demand')]"
```

### Request Quota Increase
```bash
aws service-quotas request-service-quota-increase \
  --service-code sagemaker \
  --quota-code <quota-code> \
  --desired-value <value>
```

## 2. IAM Configuration

### Required IAM Roles

1. **HyperPod Execution Role**: Used by SageMaker to manage cluster resources
2. **HyperPod Node Role**: Attached to cluster nodes for AWS API access

See `iam-policies.md` for complete policy documents.

### Verify Roles Exist
```bash
# Check execution role
aws iam get-role --role-name HyperPodExecutionRole

# Check node role
aws iam get-role --role-name HyperPodNodeRole
```

## 3. VPC Configuration

### Subnet Requirements

| Orchestrator | IPs per Node | Example: 4 P5 Nodes |
|--------------|--------------|---------------------|
| Slurm | 32 IPs | /25 subnet (128 IPs) |
| EKS | 81 IPs | /24 subnet (256 IPs) |

**Note**: EKS requires more IPs due to pod networking.

### Required Components

- [ ] VPC with DNS hostnames enabled
- [ ] Private subnets in multiple AZs (recommended)
- [ ] NAT Gateway or VPC endpoints for AWS service access
- [ ] S3 VPC endpoint (Gateway type) - **Required for lifecycle scripts**
- [ ] Security group allowing EFA traffic

### Verify VPC Configuration
```bash
# Check VPC
aws ec2 describe-vpcs --vpc-ids <vpc-id>

# Check subnets
aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=<vpc-id>" \
  --query "Subnets[*].[SubnetId,AvailabilityZone,CidrBlock,AvailableIpAddressCount]"

# Check S3 endpoint
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=<vpc-id>" "Name=service-name,Values=com.amazonaws.*.s3"
```

## 4. Security Group Configuration

### Required Inbound Rules

| Protocol | Port Range | Source | Purpose |
|----------|------------|--------|---------|
| All traffic | All | Self (same SG) | Inter-node communication |
| TCP | 443 | VPC CIDR | SSM access |

### Required Outbound Rules

| Protocol | Port Range | Destination | Purpose |
|----------|------------|-------------|---------|
| All traffic | All | 0.0.0.0/0 | General AWS access |

### EFA-Specific Rules (GPU/Trainium instances)

| Protocol | Port Range | Source/Dest | Purpose |
|----------|------------|-------------|---------|
| All traffic | All | Self (same SG) | EFA traffic |

### Verify Security Group
```bash
aws ec2 describe-security-groups \
  --group-ids <sg-id> \
  --query "SecurityGroups[0].[GroupId,IpPermissions,IpPermissionsEgress]"
```

## 5. S3 Bucket for Lifecycle Scripts

### Bucket Requirements

- [ ] Bucket exists in same region as cluster
- [ ] Bucket accessible from VPC (via S3 endpoint)
- [ ] HyperPod node role has read access

### Verify Bucket Access
```bash
# Check bucket exists
aws s3 ls s3://<bucket-name>/

# Test access from expected role
aws s3 ls s3://<bucket-name>/hyperpod/ --profile <node-role-profile>
```

## 6. Lifecycle Scripts

### Required Scripts

| Script | Purpose | When Executed |
|--------|---------|---------------|
| `on_create.sh` | Initial node setup | Once, at node creation |
| `provisioning_parameters.json` | Configuration parameters | Read at creation |

### Optional Scripts

| Script | Purpose | When Executed |
|--------|---------|---------------|
| `on_start.sh` | Node startup tasks | Each node boot |

### Script Requirements

- [ ] Scripts are executable (`chmod +x`)
- [ ] Scripts use `#!/bin/bash` shebang
- [ ] Scripts exit with code 0 on success
- [ ] Scripts handle errors gracefully

See `lifecycle-scripts.md` for script templates.

## 7. AWS CLI and Tools

### Required Tools

| Tool | Version | Installation |
|------|---------|--------------|
| AWS CLI | v2.x | `pip install awscli` |
| HyperPod CLI | Latest | `pip install hyperpod` |
| kubectl | v1.28+ | Required for EKS only |
| Session Manager Plugin | Latest | For SSM access |

### Verify Installation
```bash
# AWS CLI
aws --version

# HyperPod CLI
hyp --version

# kubectl (EKS only)
kubectl version --client

# Session Manager Plugin
session-manager-plugin --version
```

## 8. EKS-Specific Prerequisites

### Additional Requirements for EKS Orchestration

- [ ] eksctl installed (optional, for manual EKS management)
- [ ] Helm v3.x installed (for addon installation)
- [ ] kubectl configured for cluster access

### Verify EKS Tools
```bash
# eksctl
eksctl version

# helm
helm version
```

## 9. Slurm-Specific Prerequisites

### Additional Requirements for Slurm Orchestration

- [ ] FSx for Lustre setup (recommended for shared storage)
- [ ] LDAP/AD configuration (if using centralized auth)

## Pre-Flight Checklist

Run through this checklist before creating a cluster:

```
[ ] Service quotas requested and approved
[ ] IAM roles created with correct policies
[ ] VPC configured with adequate IP space
[ ] S3 VPC endpoint created
[ ] Security group allows required traffic
[ ] S3 bucket created with lifecycle scripts
[ ] Lifecycle scripts tested and uploaded
[ ] CLI tools installed and configured
[ ] AWS credentials configured
```

## Validation Script

Run the automated validation:
```bash
bash scripts/hyperpod/validate-prerequisites.sh \
  --region us-west-2 \
  --vpc-id vpc-xxxxx \
  --subnet-ids subnet-xxxxx,subnet-yyyyy \
  --bucket s3://my-bucket/hyperpod/
```

## Common Pre-Creation Issues

### Insufficient Quotas
**Symptom**: Cluster creation fails immediately
**Solution**: Request quota increase, wait for approval

### VPC IP Exhaustion
**Symptom**: Nodes fail to launch
**Solution**: Use larger CIDR block or different subnet

### S3 Access Denied
**Symptom**: Lifecycle scripts fail to download
**Solution**: Verify S3 endpoint exists, check IAM permissions

### Security Group Misconfiguration
**Symptom**: Nodes can't communicate
**Solution**: Add self-referencing "All traffic" rule
