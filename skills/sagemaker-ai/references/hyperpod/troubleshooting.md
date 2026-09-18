# HyperPod Troubleshooting Guide

Common errors and solutions for both EKS and Slurm orchestrators.

## Table of Contents
- [Diagnostic Commands](#diagnostic-commands)
- [Cluster Creation Errors](#cluster-creation-errors)
- [EKS-Specific Errors](#eks-specific-errors)
- [Node Issues](#node-issues)
- [Job Failures](#job-failures)
- [Networking Issues](#networking-issues)

---

## Diagnostic Commands

```bash
# Check cluster status
aws sagemaker describe-cluster --cluster-name NAME

# List nodes with status
aws sagemaker list-cluster-nodes --cluster-name NAME

# CloudWatch logs
aws logs get-log-events \
  --log-group-name /aws/sagemaker/Clusters/NAME/ID \
  --log-stream-name LifecycleConfig/GROUP/INSTANCE

# EKS-specific
kubectl get nodes
kubectl get pods -A
kubectl describe pod POD_NAME

# Check CloudTrail for API errors
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=sagemaker.amazonaws.com \
  --start-time "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
  --query 'Events[*].[EventName,CloudTrailEvent]'
```

---

## Cluster Creation Errors

### Unsupported Instance Type

**Error**: `HyperPodClusterStack CREATE_FAILED` with unsupported instance type

**Root Cause**: Instance type not supported for HyperPod clusters (e.g., ml.trn1.2xlarge)

**Solution**:
```bash
# Check supported instance types
aws service-quotas list-service-quotas --service-code sagemaker --region us-east-1 \
  --query 'Quotas[?contains(QuotaName, `<INSTANCE_TYPE>`) && contains(QuotaName, `cluster`)]'
```

Use a supported instance type. For Trainium, use `ml.trn1.32xlarge` (not ml.trn1.2xlarge).

### CloudFormation ROLLBACK_COMPLETE

**Error**: Stack rolls back without clear error message

**Solution**: Check CloudTrail for actual API errors:
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=sagemaker.amazonaws.com \
  --start-time "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)"
```

### InsufficientCapacity

**Solution**:
- Check quotas: `aws service-quotas get-service-quota`
- Try different AZ or region
- Consider alternative instance types

### VPCConfigurationError

**Solution**:
- Check subnet CIDR sizing (81 IPs per P5 for EKS, 32 for Slurm)
- Verify security group rules
- Ensure NAT gateway for private subnets

### VPC Quota Exceeded (max 5 VPCs)

**Solution**:
```bash
aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,Tags]'
# Delete unused VPCs or request quota increase
```

### LifecycleScriptFailed

**Solution**:
- Check S3 bucket permissions
- Validate script syntax
- Review CloudWatch logs: `/aws/sagemaker/Clusters/<cluster>/<id>`
- Use sample scripts from `aws-samples/awsome-distributed-training`

---

## EKS-Specific Errors

### InvalidParameterException During EKS Cluster Creation

**Root Cause**: EKS requires subnets in at least 2 Availability Zones

**Solution**: Add a second AZ to config.yaml:
```yaml
availability_zone_ids:
  - use1-az6  # Primary
  - use1-az4  # Secondary for EKS HA
```

### EKS Authentication Mode Not Supported

**Error**: `EKS clusters with CONFIG_MAP authentication mode are not supported`

**Solution**:
```bash
aws eks update-cluster-config \
  --name <cluster-name> \
  --access-config authenticationMode=API_AND_CONFIG_MAP \
  --region <region>
```

### Missing Required Dependencies

**Error**: `Amazon EKS orchestrator cluster is missing required dependencies`

**Solution**: Install HyperPod Helm chart:
```bash
git clone https://github.com/aws/sagemaker-hyperpod-cli.git
cd sagemaker-hyperpod-cli/helm_chart
helm dependencies update HyperPodHelmChart
helm install hyperpod-dependencies HyperPodHelmChart --namespace kube-system
```

### Unable to Retrieve Subnets

**Solution**: Add EC2 VPC permissions to execution role:
- ec2:DescribeSubnets
- ec2:DescribeSecurityGroups
- ec2:CreateNetworkInterface
- ec2:DeleteNetworkInterface

### Training Operator Pod Identity Failure

**Error**: `Unable to verify AWS SageMaker auth, please verify Pod Identity configuration`

**Solution**: See [EKS Guide - Fix Pod Identity](eks-guide.md#fix-pod-identity-verification-failure)

### Add-on Not Supported in K8s Version

**Error**: `Addon amazon-sagemaker-hyperpod-taskgovernance specified is not supported in X.XX kubernetes version`

**Root Cause**: HyperPod add-ons may not support latest K8s versions

**Solution**:
```bash
# Check supported versions
aws eks describe-addon-versions --addon-name <ADDON_NAME> \
  --query 'addons[0].addonVersions[*].compatibilities[*].clusterVersion' --output text
```

Use a supported K8s version or alternative solutions (CloudWatch Container Insights, Kueue).

---

## Node Issues

### EFA Health Checks Failed

**Error**: `EFA health checks did not run successfully`

**Root Cause**: Multi-AZ deployment for EFA-enabled instances

**Solution**: Use `OverrideVpcConfig` with single subnet:
```json
"OverrideVpcConfig": {
  "SecurityGroupIds": ["sg-xxx"],
  "Subnets": ["subnet-single-az"]
}
```

### Nodes Stuck in Pending/ShuttingDown Cycle

**Root Cause**: Usually EFA health check failure (multi-AZ)

**Solution**:
- Use single subnet with `OverrideVpcConfig`
- Check CloudWatch logs for specific error
- Verify security group allows all traffic within itself

### NodeUnhealthy

**Solution**:
- Check node status via CLI
- Review instance metrics
- Consider node replacement:
```bash
aws sagemaker update-cluster --cluster-name NAME --instance-groups '[...]'
```

---

## Job Failures

### Insufficient CPU/Memory

**Error**: `0/1 nodes are available: 1 Insufficient cpu`

**Solution**: Use partial resource allocation instead of full node:
```yaml
accelerators: 1
vcpu: 4
memory: 16
accelerators_limit: 1
vcpu_limit: 4
memory_limit: 16
```

### Accelerator Limits Mismatch

**Error**: `Accelerator request must equal accelerator limit`

**Solution**: Ensure limits match requests in job config:
```yaml
accelerators: 1
accelerators_limit: 1  # MUST match
```

### HyperPod Job Restarts Repeatedly

**Root Cause**: Expected for short test jobs; HyperPod retries failed jobs

**Solution**: Use standard Kubeflow PyTorchJob for quick tests instead of HyperPodPyTorchJob

---

## Networking Issues

### Security Group Configuration

Security group must allow ALL traffic within itself for EFA:

```yaml
# CloudFormation
HyperPodSecurityGroupSelfIngress:
  Type: AWS::EC2::SecurityGroupIngress
  Properties:
    GroupId: !Ref HyperPodSecurityGroup
    IpProtocol: "-1"
    SourceSecurityGroupId: !Ref HyperPodSecurityGroup
```

Or via CLI:
```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol all \
  --port -1 \
  --source-group sg-xxx
```

### CIDR Sizing Requirements

| Orchestrator | IPs per P5 Instance |
|--------------|---------------------|
| Slurm | 32 |
| EKS | 81 (includes pod IPs) |

---

## Best Practices

### Cluster Sizing
- Start small, scale up as needed
- Use spot instances for development (Slurm only)
- Reserve capacity for production workloads

### Resilience
- Enable automatic node replacement
- Configure health check thresholds appropriately
- Test failover procedures regularly

### Cost Optimization
- Right-size instance types for workload
- Use Trainium for compatible models (cost-effective)
- Implement job queuing to maximize utilization

### Security
- Use private subnets for compute nodes
- Enable VPC Flow Logs for debugging
- Regularly rotate credentials and keys
