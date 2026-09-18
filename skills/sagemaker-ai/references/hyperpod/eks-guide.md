# EKS Orchestrator Guide

Complete guide for HyperPod clusters with Amazon EKS orchestration.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Cluster Creation Workflow](#cluster-creation-workflow)
- [Kubernetes Version Selection](#kubernetes-version-selection)
- [Add-on Compatibility](#add-on-compatibility)
- [Post-Cluster Add-ons](#post-cluster-add-ons)
- [Job Submission](#job-submission)
- [CLI Reference](#cli-reference)

---

## Prerequisites

```bash
# Install HyperPod CLI
pip install sagemaker-hyperpod

# Verify installation
hyp --help

# Also required: kubectl, helm v3
```

## Cluster Creation Workflow

### Option A: Using HyperPod CLI (Recommended)

```bash
# 0. Run pre-flight validation (REQUIRED)
aws service-quotas list-service-quotas --service-code sagemaker --region us-east-1 \
  --query 'Quotas[?contains(QuotaName, `<INSTANCE_TYPE>`) && contains(QuotaName, `cluster`)].[QuotaName,Value]'

# 1. Initialize cluster configuration
hyp init cluster-stack

# 2. Edit config.yaml - CRITICAL: Ensure 2+ AZs for EKS!
# availability_zone_ids:
#   - use1-az6
#   - use1-az4

# 3. Configure cluster parameters
hyp configure --resource-name-prefix my-hyperpod

# 4. Validate configuration
hyp validate

# 5. Create cluster
hyp create --region us-east-1
```

### Option B: Using AWS CLI (Advanced)

Use when you need custom VPC configuration or `OverrideVpcConfig`:

```bash
aws sagemaker create-cluster \
  --cluster-name my-cluster \
  --orchestrator "Eks={ClusterArn=arn:aws:eks:...}" \
  --instance-groups '[{
    "InstanceGroupName": "workers",
    "InstanceType": "ml.trn1.32xlarge",
    "InstanceCount": 2,
    "OverrideVpcConfig": {
      "SecurityGroupIds": ["sg-xxx"],
      "Subnets": ["subnet-single-az"]
    },
    ...
  }]' \
  --vpc-config "SecurityGroupIds=sg-xxx,Subnets=subnet-1,subnet-2"
```

## EKS Prerequisites Setup

Before creating HyperPod cluster on EKS:

### 1. Update EKS Authentication Mode

```bash
aws eks update-cluster-config \
  --name <cluster-name> \
  --access-config authenticationMode=API_AND_CONFIG_MAP \
  --region <region>
```

### 2. Install HyperPod Helm Dependencies

```bash
git clone https://github.com/aws/sagemaker-hyperpod-cli.git
cd sagemaker-hyperpod-cli/helm_chart
helm dependencies update HyperPodHelmChart
helm install hyperpod-dependencies HyperPodHelmChart --namespace kube-system
```

Components installed: Kueue, Kubeflow Training Operator, MPI Operator, device plugins

---

## Kubernetes Version Selection

**ALWAYS check the latest available EKS version before cluster creation:**

```bash
aws eks describe-cluster-versions --region us-east-1 --output table
```

| Status | Meaning | Cost Impact |
|--------|---------|-------------|
| STANDARD_SUPPORT | Actively supported | Normal pricing |
| EXTENDED_SUPPORT | Past standard support | **Extra charges apply** |

**Before setting kubernetes_version in config.yaml:**
```
WebFetch: https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-release-calendar
Prompt: What is the latest Kubernetes version available for EKS that is in standard support?
```

Or via CLI:
```bash
aws eks describe-cluster-versions --region us-east-1 \
  --query 'clusterVersions[?status==`STANDARD_SUPPORT`].clusterVersion' --output text | head -1
```

**Upgrading existing clusters** (one version at a time):
```bash
aws eks update-cluster-version --name CLUSTER_NAME --region REGION --kubernetes-version 1.XX
# Wait for completion, then upgrade add-ons before next version bump
```

---

## Add-on Compatibility

**WARNING**: HyperPod-specific EKS add-ons may NOT support the latest Kubernetes versions. Always verify compatibility before upgrading.

```bash
# Check supported K8s versions for each HyperPod add-on
aws eks describe-addon-versions --addon-name amazon-sagemaker-hyperpod-taskgovernance \
  --query 'addons[0].addonVersions[*].compatibilities[*].clusterVersion' --output text

aws eks describe-addon-versions --addon-name amazon-sagemaker-hyperpod-observability \
  --query 'addons[0].addonVersions[*].compatibilities[*].clusterVersion' --output text

aws eks describe-addon-versions --addon-name amazon-sagemaker-hyperpod-training-operator \
  --query 'addons[0].addonVersions[*].compatibilities[*].clusterVersion' --output text
```

**Add-on Compatibility Matrix:**
> Check current compatibility with `aws eks describe-addon-versions`

| Add-on | Typical Support |
|--------|-----------------|
| hyperpod-training-operator | Recent K8s versions |
| hyperpod-taskgovernance | May lag behind latest |
| hyperpod-observability | May lag behind latest |

**IMPORTANT**: EKS does NOT support downgrading. If you upgrade to a K8s version that HyperPod add-ons don't support, you cannot roll back.

**Recommendation**: Before upgrading K8s versions:
1. Check if you need HyperPod-specific add-ons (task governance, observability)
2. Verify add-on compatibility with target K8s version
3. Stay on a supported version if add-ons are required

---

## Post-Cluster Add-ons

### Available HyperPod Add-ons

| Add-on | Purpose | Required For |
|--------|---------|--------------|
| amazon-sagemaker-hyperpod-training-operator | HyperPodPyTorchJob CRD | `hyp create` job submission |
| amazon-sagemaker-hyperpod-taskgovernance | Resource allocation, quotas | Multi-team clusters |
| amazon-sagemaker-hyperpod-observability | Centralized logging/metrics | Production monitoring |

### Install Training Operator (REQUIRED for `hyp create`)

**Prerequisites:**
1. EKS Pod Identity Agent must be enabled
2. cert-manager must be installed

```bash
# Step 1: Install cert-manager (prerequisite)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.17.1/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=300s

# Step 2: Verify EKS Pod Identity Agent is installed
aws eks describe-addon --cluster-name <EKS_CLUSTER_NAME> --addon-name eks-pod-identity-agent --region <REGION>

# If not installed:
aws eks create-addon --cluster-name <EKS_CLUSTER_NAME> --addon-name eks-pod-identity-agent --region <REGION>

# Step 3: Install Training Operator add-on
aws eks create-addon \
  --cluster-name <EKS_CLUSTER_NAME> \
  --addon-name amazon-sagemaker-hyperpod-training-operator \
  --region <REGION>

# Step 4: Verify installation
kubectl get pods -n aws-hyperpod
kubectl get crd | grep hyperpod
```

### Fix Pod Identity Verification Failure

If Training Operator pod fails with:
```
Unable to verify AWS SageMaker auth, please verify Pod Identity configuration
```

**Solution:**

```bash
# Step 1: Update IAM role trust policy to allow EKS Pod Identity
# Add "pods.eks.amazonaws.com" as trusted principal with sts:AssumeRole and sts:TagSession

# Step 2: Add SageMaker permissions to the role
cat > /tmp/training-operator-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
            "sagemaker:DescribeClusterNode",
            "sagemaker:ListClusterNodes",
            "sagemaker:DescribeCluster"
        ],
        "Resource": "*"
    }]
}
EOF
aws iam put-role-policy --role-name <ROLE_NAME> \
  --policy-name HyperPodTrainingOperatorPolicy \
  --policy-document file:///tmp/training-operator-policy.json

# Step 3: Create Pod Identity association
aws eks create-pod-identity-association \
  --cluster-name <EKS_CLUSTER_NAME> \
  --namespace aws-hyperpod \
  --service-account hp-training-operator-controller-manager \
  --role-arn arn:aws:iam::<ACCOUNT>:role/<ROLE_NAME> \
  --region <REGION>

# Step 4: Restart the Training Operator pod
kubectl delete pod -n aws-hyperpod -l app.kubernetes.io/name=hp-training-operator

# Verify
aws eks list-pod-identity-associations --cluster-name <EKS_CLUSTER_NAME> --region <REGION>
kubectl get pods -n aws-hyperpod  # Should show Running
```

### Install Other Add-ons (Optional)

**Check K8s version compatibility first:**
```bash
aws eks describe-addon-versions --addon-name amazon-sagemaker-hyperpod-taskgovernance \
  --query 'addons[0].addonVersions[0].compatibilities[*].clusterVersion' --output text
```

```bash
# Task Governance (for resource quotas)
aws eks create-addon \
  --cluster-name <EKS_CLUSTER_NAME> \
  --addon-name amazon-sagemaker-hyperpod-taskgovernance \
  --region <REGION>

# Observability (requires Amazon Managed Prometheus workspace)
aws eks create-addon \
  --cluster-name <EKS_CLUSTER_NAME> \
  --addon-name amazon-sagemaker-hyperpod-observability \
  --addon-configuration '{"ampWorkspace":{"prometheusEndpoint":"https://aps-workspaces.<REGION>.amazonaws.com/workspaces/<WORKSPACE_ID>/"}}' \
  --region <REGION>
```

**If K8s version not supported**, use alternatives:
- **CloudWatch Container Insights** for observability
- **Kueue** for resource quotas

---

## Job Submission

### Resource Allocation Options

**HyperPodPyTorchJob** (via `hyp create`) supports two modes:

1. **Full node allocation** (`--node-count`): Requests entire node resources
2. **Partial resources** (`--accelerators`, `--vcpu`, `--memory`): Specify exact requirements
   - **IMPORTANT:** Accelerator requests must equal limits

### Recommended: Config File Approach

```bash
# 1. Initialize job config
mkdir my-job && cd my-job
hyp init hyp-pytorch-job

# 2. Edit config.yaml
```

```yaml
# config.yaml
template: hyp-pytorch-job
version: 1.1
job_name: my-training-job
image: 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training-neuronx:2.1.2-neuronx-py310-sdk2.20.2-ubuntu20.04
namespace: default

# Multi-line command using YAML block scalar
command:
  - python3
  - -c
  - |
    import torch
    print('PyTorch:', torch.__version__)
    # Your training code here

instance_type: ml.trn1.32xlarge

# Partial resources (requests)
accelerators: 1
vcpu: 4
memory: 16

# Limits MUST match requests for accelerators
accelerators_limit: 1
vcpu_limit: 4
memory_limit: 16
```

```bash
# 3. Submit job
hyp create
```

### Using HyperPod CLI Directly

```bash
hyp create hyp-pytorch-job \
  --job-name my-training \
  --image 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training-neuronx:2.1.2 \
  --command '[python, train.py]' \
  --instance-type ml.trn1.32xlarge \
  --node-count 2
```

### Workaround: Kubeflow PyTorchJob

If Training Operator fails, use standard Kubeflow PyTorchJob:

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: my-training-job
spec:
  pytorchReplicaSpecs:
    Master:
      replicas: 1
      template:
        spec:
          containers:
            - name: pytorch
              image: 763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training-neuronx:2.1.2-neuronx-py310-sdk2.20.2-ubuntu20.04
              command: [python3, -c, "import torch; print(torch.__version__)"]
              resources:
                requests:
                  aws.amazon.com/neuron: "1"
                limits:
                  aws.amazon.com/neuron: "1"
          nodeSelector:
            node.kubernetes.io/instance-type: ml.trn1.32xlarge
```

---

## CLI Reference

### Cluster Management
```bash
hyp list-cluster                              # List available clusters
hyp set-cluster-context --cluster-name NAME   # Configure kubectl context
hyp get-cluster-context                       # Show current context
hyp list cluster-stack                        # List CloudFormation stacks
hyp describe cluster-stack STACK_NAME         # Stack details
hyp delete cluster-stack STACK_NAME           # Delete stack
```

### Job Management
```bash
hyp init hyp-pytorch-job                      # Initialize job config
hyp create hyp-pytorch-job [options]          # Create job
hyp get jobs                                  # List jobs
hyp logs JOB_NAME                             # View logs
hyp delete job JOB_NAME                       # Delete job
```

### kubectl Commands
```bash
kubectl apply -f pytorch-job.yaml             # Apply PyTorchJob manifest
kubectl get pytorchjobs                       # List jobs
kubectl logs -f -l app=my-training            # Follow logs
kubectl get nodes                             # List nodes
kubectl get pods -A                           # All pods
```
