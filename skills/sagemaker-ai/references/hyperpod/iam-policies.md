# HyperPod IAM Policies

This document provides IAM role and policy configurations required for HyperPod clusters.

## Overview

HyperPod requires two primary IAM roles:

1. **Execution Role**: Used by SageMaker service to manage cluster resources
2. **Node Role**: Attached to EC2 instances in the cluster

## Execution Role

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Execution Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2Management",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:CreateNetworkInterfacePermission",
        "ec2:DeleteNetworkInterface",
        "ec2:DeleteNetworkInterfacePermission",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeDhcpOptions",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeImages",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeLaunchTemplates",
        "ec2:DescribeLaunchTemplateVersions",
        "ec2:DescribePlacementGroups",
        "ec2:CreatePlacementGroup",
        "ec2:DeletePlacementGroup",
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/HyperPod*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ec2.amazonaws.com"
        }
      }
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::*hyperpod*",
        "arn:aws:s3:::*hyperpod*/*",
        "arn:aws:s3:::*sagemaker*",
        "arn:aws:s3:::*sagemaker*/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
    },
    {
      "Sid": "SSMAccess",
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation"
      ],
      "Resource": "*"
    }
  ]
}
```

### Create Execution Role

```bash
# Create the role
aws iam create-role \
  --role-name HyperPodExecutionRole \
  --assume-role-policy-document file://trust-policy.json

# Attach the policy
aws iam put-role-policy \
  --role-name HyperPodExecutionRole \
  --policy-name HyperPodExecutionPolicy \
  --policy-document file://execution-policy.json

# Attach AWS managed policies
aws iam attach-role-policy \
  --role-name HyperPodExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

## Node Role

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Node Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3LifecycleScripts",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME",
        "arn:aws:s3:::YOUR-BUCKET-NAME/*"
      ]
    },
    {
      "Sid": "S3ModelArtifacts",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-DATA-BUCKET",
        "arn:aws:s3:::YOUR-DATA-BUCKET/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "SageMaker"
        }
      }
    },
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SSMAgentAccess",
      "Effect": "Allow",
      "Action": [
        "ssm:UpdateInstanceInformation",
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ],
      "Resource": "*"
    }
  ]
}
```

### Create Node Role

```bash
# Create the role
aws iam create-role \
  --role-name HyperPodNodeRole \
  --assume-role-policy-document file://node-trust-policy.json

# Attach the custom policy
aws iam put-role-policy \
  --role-name HyperPodNodeRole \
  --policy-name HyperPodNodePolicy \
  --policy-document file://node-policy.json

# Attach AWS managed policies
aws iam attach-role-policy \
  --role-name HyperPodNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

# Create instance profile (required for EC2)
aws iam create-instance-profile \
  --instance-profile-name HyperPodNodeProfile

aws iam add-role-to-instance-profile \
  --instance-profile-name HyperPodNodeProfile \
  --role-name HyperPodNodeRole
```

## EKS-Specific Roles

### EKS Cluster Role

For EKS orchestration, you also need an EKS cluster role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "eks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# Create EKS cluster role
aws iam create-role \
  --role-name HyperPodEKSClusterRole \
  --assume-role-policy-document file://eks-trust-policy.json

# Attach managed policy
aws iam attach-role-policy \
  --role-name HyperPodEKSClusterRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSClusterPolicy
```

### EKS Node Group Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# Create EKS node group role
aws iam create-role \
  --role-name HyperPodEKSNodeRole \
  --assume-role-policy-document file://eks-node-trust-policy.json

# Attach managed policies
aws iam attach-role-policy \
  --role-name HyperPodEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy

aws iam attach-role-policy \
  --role-name HyperPodEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

aws iam attach-role-policy \
  --role-name HyperPodEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
```

## FSx for Lustre Access (Optional)

If using FSx for Lustre shared storage, add this policy to the node role:

```json
{
  "Sid": "FSxAccess",
  "Effect": "Allow",
  "Action": [
    "fsx:DescribeFileSystems",
    "fsx:DescribeDataRepositoryAssociations"
  ],
  "Resource": "*"
}
```

## Best Practices

### Principle of Least Privilege

1. **Scope S3 access**: Replace `YOUR-BUCKET-NAME` with actual bucket names
2. **Limit regions**: Add conditions to restrict to specific regions
3. **Use resource tags**: Add tag-based conditions where possible

### Example: Scoped S3 Policy

```json
{
  "Sid": "S3ScopedAccess",
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject"
  ],
  "Resource": "arn:aws:s3:::my-company-hyperpod-*/*",
  "Condition": {
    "StringEquals": {
      "aws:RequestedRegion": "us-west-2"
    }
  }
}
```

### Security Recommendations

1. **Enable CloudTrail**: Monitor IAM role usage
2. **Use IAM Access Analyzer**: Identify overly permissive policies
3. **Regular rotation**: Review and update policies quarterly
4. **Separate environments**: Use different roles for dev/staging/prod

## Troubleshooting IAM Issues

### Common Errors

**AccessDenied on S3**
```bash
# Check role can access bucket
aws s3 ls s3://bucket-name/ --profile node-role-profile
```

**Unable to assume role**
```bash
# Verify trust policy
aws iam get-role --role-name HyperPodExecutionRole \
  --query "Role.AssumeRolePolicyDocument"
```

**Instance profile not found**
```bash
# List instance profiles
aws iam list-instance-profiles-for-role \
  --role-name HyperPodNodeRole
```

## Verification Commands

```bash
# Verify execution role
aws iam get-role --role-name HyperPodExecutionRole
aws iam list-role-policies --role-name HyperPodExecutionRole
aws iam list-attached-role-policies --role-name HyperPodExecutionRole

# Verify node role
aws iam get-role --role-name HyperPodNodeRole
aws iam list-role-policies --role-name HyperPodNodeRole
aws iam get-instance-profile --instance-profile-name HyperPodNodeProfile
```
