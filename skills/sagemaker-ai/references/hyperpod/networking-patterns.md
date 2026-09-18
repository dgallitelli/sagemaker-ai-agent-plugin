# HyperPod Networking Patterns

This document covers VPC configuration patterns for HyperPod clusters.

## Overview

HyperPod clusters require careful network planning due to:
- High IP consumption per node (especially EKS)
- EFA (Elastic Fabric Adapter) requirements for high-performance networking
- Private subnet requirements for security
- AWS service connectivity for lifecycle scripts and monitoring

## IP Address Requirements

### Per-Node IP Consumption

| Orchestrator | IPs per Node | Notes |
|--------------|--------------|-------|
| Slurm | ~32 | Primary ENI + EFA ENIs |
| EKS | ~81 | Primary + EFA + pod IPs (max pods) |

### Subnet Sizing Guide

| Cluster Size | Slurm Subnet | EKS Subnet | Recommended CIDR |
|--------------|--------------|------------|------------------|
| 4 nodes | /26 (64) | /24 (256) | /24 |
| 8 nodes | /25 (128) | /23 (512) | /23 |
| 16 nodes | /24 (256) | /22 (1024) | /22 |
| 32 nodes | /23 (512) | /21 (2048) | /21 |
| 64 nodes | /22 (1024) | /20 (4096) | /20 |

**Note**: Always round up and leave headroom for growth.

## Recommended VPC Architecture

### Production Pattern: Multi-AZ Private Subnets

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPC (10.0.0.0/16)                       │
│                                                                 │
│  ┌─────────────────────┐       ┌─────────────────────┐         │
│  │   Public Subnet     │       │   Public Subnet     │         │
│  │   10.0.0.0/24       │       │   10.0.1.0/24       │         │
│  │      (AZ-a)         │       │      (AZ-b)         │         │
│  │   ┌───────────┐     │       │   ┌───────────┐     │         │
│  │   │ NAT GW    │     │       │   │ NAT GW    │     │         │
│  │   └───────────┘     │       │   └───────────┘     │         │
│  └─────────────────────┘       └─────────────────────┘         │
│           │                             │                       │
│  ┌────────┴────────────┐       ┌────────┴────────────┐         │
│  │  Private Subnet     │       │  Private Subnet     │         │
│  │  10.0.16.0/20       │       │  10.0.32.0/20       │         │
│  │      (AZ-a)         │       │      (AZ-b)         │         │
│  │                     │       │                     │         │
│  │  ┌───┐ ┌───┐ ┌───┐  │       │  ┌───┐ ┌───┐ ┌───┐  │         │
│  │  │P5 │ │P5 │ │P5 │  │       │  │P5 │ │P5 │ │P5 │  │         │
│  │  └───┘ └───┘ └───┘  │       │  └───┘ └───┘ └───┘  │         │
│  │                     │       │                     │         │
│  └─────────────────────┘       └─────────────────────┘         │
│                                                                 │
│  VPC Endpoints: S3 (Gateway), SSM, EC2, Logs, ECR              │
└─────────────────────────────────────────────────────────────────┘
```

### Development Pattern: Single-AZ

```
┌─────────────────────────────────────────────────────────────────┐
│                       VPC (10.0.0.0/16)                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Public Subnet 10.0.0.0/24              │       │
│  │                      (AZ-a)                          │       │
│  │              ┌─────────────────┐                     │       │
│  │              │    NAT Gateway   │                    │       │
│  │              └─────────────────┘                     │       │
│  └─────────────────────────────────────────────────────┘       │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────────┐       │
│  │            Private Subnet 10.0.16.0/20              │       │
│  │                      (AZ-a)                          │       │
│  │                                                      │       │
│  │        ┌───┐    ┌───┐    ┌───┐    ┌───┐             │       │
│  │        │P5 │    │P5 │    │P5 │    │P5 │             │       │
│  │        └───┘    └───┘    └───┘    └───┘             │       │
│  │                                                      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  VPC Endpoints: S3 (Gateway)                                   │
└─────────────────────────────────────────────────────────────────┘
```

## VPC Creation

### Using AWS CLI

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=hyperpod-vpc}]'

# Enable DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id vpc-xxxxx \
  --enable-dns-hostnames '{"Value": true}'

# Create Internet Gateway
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=hyperpod-igw}]'

aws ec2 attach-internet-gateway \
  --vpc-id vpc-xxxxx \
  --internet-gateway-id igw-xxxxx
```

### Create Subnets

```bash
# Public subnet (AZ-a)
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.0.0/24 \
  --availability-zone us-west-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=hyperpod-public-a}]'

# Private subnet (AZ-a) - large for HyperPod nodes
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.16.0/20 \
  --availability-zone us-west-2a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=hyperpod-private-a}]'
```

### Create NAT Gateway

```bash
# Allocate Elastic IP
aws ec2 allocate-address \
  --domain vpc \
  --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=hyperpod-nat-eip}]'

# Create NAT Gateway in public subnet
aws ec2 create-nat-gateway \
  --subnet-id subnet-public-xxxxx \
  --allocation-id eipalloc-xxxxx \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=hyperpod-nat}]'
```

### Configure Route Tables

```bash
# Create route table for private subnets
aws ec2 create-route-table \
  --vpc-id vpc-xxxxx \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=hyperpod-private-rt}]'

# Add route to NAT Gateway
aws ec2 create-route \
  --route-table-id rtb-xxxxx \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id nat-xxxxx

# Associate with private subnet
aws ec2 associate-route-table \
  --route-table-id rtb-xxxxx \
  --subnet-id subnet-private-xxxxx
```

## VPC Endpoints

### Required: S3 Gateway Endpoint

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxxxx \
  --service-name com.amazonaws.us-west-2.s3 \
  --route-table-ids rtb-xxxxx \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=hyperpod-s3-endpoint}]'
```

### Recommended: Interface Endpoints

For better performance and to reduce NAT Gateway costs:

```bash
# SSM endpoints (for node access)
for service in ssm ssmmessages ec2messages; do
  aws ec2 create-vpc-endpoint \
    --vpc-id vpc-xxxxx \
    --vpc-endpoint-type Interface \
    --service-name com.amazonaws.us-west-2.$service \
    --subnet-ids subnet-xxxxx \
    --security-group-ids sg-xxxxx \
    --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=hyperpod-$service-endpoint}]"
done

# ECR endpoints (for container images)
for service in ecr.api ecr.dkr; do
  aws ec2 create-vpc-endpoint \
    --vpc-id vpc-xxxxx \
    --vpc-endpoint-type Interface \
    --service-name com.amazonaws.us-west-2.$service \
    --subnet-ids subnet-xxxxx \
    --security-group-ids sg-xxxxx
done

# CloudWatch Logs endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-xxxxx \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.us-west-2.logs \
  --subnet-ids subnet-xxxxx \
  --security-group-ids sg-xxxxx
```

## Security Groups

### HyperPod Node Security Group

```bash
# Create security group
aws ec2 create-security-group \
  --group-name hyperpod-nodes-sg \
  --description "Security group for HyperPod cluster nodes" \
  --vpc-id vpc-xxxxx

# Allow all traffic within the security group (required for EFA)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol all \
  --source-group sg-xxxxx

# Allow all outbound traffic
aws ec2 authorize-security-group-egress \
  --group-id sg-xxxxx \
  --protocol all \
  --cidr 0.0.0.0/0
```

### VPC Endpoint Security Group

```bash
# Create security group for VPC endpoints
aws ec2 create-security-group \
  --group-name hyperpod-endpoints-sg \
  --description "Security group for VPC endpoints" \
  --vpc-id vpc-xxxxx

# Allow HTTPS from VPC CIDR
aws ec2 authorize-security-group-ingress \
  --group-id sg-endpoint-xxxxx \
  --protocol tcp \
  --port 443 \
  --cidr 10.0.0.0/16
```

## EFA Configuration

### EFA Requirements

EFA (Elastic Fabric Adapter) is required for high-performance inter-node communication on GPU instances.

**Supported Instance Types**:
- ml.p4d.24xlarge (4 EFA devices)
- ml.p4de.24xlarge (4 EFA devices)
- ml.p5.48xlarge (32 EFA devices)
- ml.trn1.32xlarge (8 EFA devices)
- ml.trn1n.32xlarge (16 EFA devices)

### EFA Security Group Rules

EFA requires the security group to allow all traffic from itself:

```bash
# This is the same rule as above, but critical for EFA
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol all \
  --source-group sg-xxxxx
```

### Verify EFA Support

```bash
# Check if instance type supports EFA
aws ec2 describe-instance-types \
  --instance-types p5.48xlarge \
  --query "InstanceTypes[0].NetworkInfo.EfaSupported"
```

## Placement Groups

### Cluster Placement Groups

HyperPod automatically creates placement groups for optimal network performance:

```bash
# Manual creation (if needed)
aws ec2 create-placement-group \
  --group-name hyperpod-placement \
  --strategy cluster \
  --tag-specifications 'ResourceType=placement-group,Tags=[{Key=Name,Value=hyperpod-pg}]'
```

**Note**: Cluster placement groups require all instances to be in the same AZ.

## Network Performance Optimization

### MTU Configuration

For EFA-enabled instances, jumbo frames are supported:

```bash
# Check current MTU (run on node)
ip link show

# EFA interfaces typically support MTU 8900
```

### NCCL Environment Variables

Configure in lifecycle scripts:

```bash
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1
export FI_EFA_USE_DEVICE_RDMA=1
export FI_PROVIDER=efa
```

## Troubleshooting Network Issues

### Check Subnet IP Availability

```bash
aws ec2 describe-subnets \
  --subnet-ids subnet-xxxxx \
  --query "Subnets[0].AvailableIpAddressCount"
```

### Verify VPC Endpoint Connectivity

```bash
# From a node, test S3 endpoint
aws s3 ls --region us-west-2

# Check endpoint status
aws ec2 describe-vpc-endpoints \
  --vpc-endpoint-ids vpce-xxxxx \
  --query "VpcEndpoints[0].State"
```

### Test EFA Connectivity

```bash
# On node, check EFA devices
fi_info -p efa

# Check EFA interfaces
ibv_devinfo
```

## Cost Optimization

### NAT Gateway Costs

NAT Gateway charges per GB of data processed. Reduce costs by:
1. Using VPC endpoints for AWS services
2. Using S3 Gateway endpoint (free) instead of NAT
3. Placing data in same region as cluster

### VPC Endpoint Costs

- Gateway endpoints (S3, DynamoDB): **Free**
- Interface endpoints: ~$0.01/hour/AZ + data processing

### Recommendations

1. Always use S3 Gateway endpoint
2. Use Interface endpoints for high-traffic services
3. Consider PrivateLink for frequently accessed services
