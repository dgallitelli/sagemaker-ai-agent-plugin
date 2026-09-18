# EKS Cluster Setup Guide

This guide walks through creating a HyperPod cluster with EKS orchestration.

## Prerequisites

Before starting, ensure you have completed:

- [ ] Service quotas approved (see `references/hyperpod/prerequisites-checklist.md`)
- [ ] VPC configured with adequate IP space (see `references/hyperpod/networking-patterns.md`)
- [ ] IAM roles created (see `references/hyperpod/iam-policies.md`)
- [ ] Lifecycle scripts uploaded to S3 (see `references/hyperpod/lifecycle-scripts.md`)

### Required Tools

```bash
# Install HyperPod CLI
pip install hyperpod

# Verify installation
hyp --version

# Install kubectl (if not already installed)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Install helm (for addons)
brew install helm  # macOS
# or
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## Step 1: Initialize Cluster Stack

```bash
# Create working directory
mkdir -p ~/hyperpod-cluster && cd ~/hyperpod-cluster

# Initialize cluster configuration
hyp init cluster-stack

# This creates:
# - cluster-config.yaml (main configuration)
# - Additional template files
```

## Step 2: Configure Cluster

### Edit cluster-config.yaml

```yaml
# cluster-config.yaml
apiVersion: hyperpod.sagemaker.aws/v1
kind: ClusterConfig
metadata:
  name: my-hyperpod-cluster
spec:
  region: us-west-2
  orchestrator: eks

  # VPC Configuration
  vpc:
    vpcId: vpc-xxxxx
    subnetIds:
      - subnet-xxxxx
      - subnet-yyyyy
    securityGroupIds:
      - sg-xxxxx

  # Instance Groups
  instanceGroups:
    # System nodes (required)
    - name: system
      instanceType: ml.m5.2xlarge
      instanceCount: 2
      lifecycleConfig:
        sourceS3Uri: s3://my-bucket/hyperpod/
        onCreate: on_create.sh
      ebsVolumeConfig:
        volumeSizeInGB: 500
        volumeType: gp3

    # GPU workers
    - name: gpu-workers
      instanceType: ml.p5.48xlarge
      instanceCount: 4
      lifecycleConfig:
        sourceS3Uri: s3://my-bucket/hyperpod/
        onCreate: on_create.sh
      ebsVolumeConfig:
        volumeSizeInGB: 1000
        volumeType: gp3
      placementGroup:
        strategy: cluster

  # IAM Configuration
  iam:
    executionRole: arn:aws:iam::123456789012:role/HyperPodExecutionRole

  # EKS-specific configuration
  eks:
    clusterVersion: "1.29"
    addons:
      - name: vpc-cni
      - name: coredns
      - name: kube-proxy
```

### Configure with CLI (alternative)

```bash
hyp configure \
  --resource-name-prefix my-hyperpod \
  --region us-west-2 \
  --vpc-id vpc-xxxxx \
  --subnet-ids subnet-xxxxx,subnet-yyyyy \
  --security-group-ids sg-xxxxx
```

## Step 3: Validate Configuration

```bash
# Validate before creating
hyp validate

# Expected output:
# ✓ VPC configuration valid
# ✓ Subnet IP capacity sufficient
# ✓ Security groups configured correctly
# ✓ IAM roles accessible
# ✓ S3 lifecycle scripts accessible
# ✓ Service quotas sufficient
#
# Configuration is valid. Ready to create cluster.
```

### Common Validation Errors

| Error | Solution |
|-------|----------|
| "Insufficient IP addresses" | Use larger subnet CIDR |
| "IAM role not found" | Create role per `iam-policies.md` |
| "S3 access denied" | Check S3 VPC endpoint and IAM |
| "Quota exceeded" | Request quota increase |

## Step 4: Create Cluster

```bash
# Create the cluster
hyp create --region us-west-2

# Monitor progress
hyp get cluster-status

# This process takes 15-30 minutes
```

### Cluster Creation Stages

1. **Infrastructure**: VPC resources, security groups
2. **EKS Control Plane**: Kubernetes API server
3. **Node Groups**: EC2 instances launching
4. **Lifecycle Scripts**: Running on_create.sh
5. **Addons**: Installing device plugins

## Step 5: Access the Cluster

```bash
# Get kubeconfig
hyp get kubeconfig > ~/.kube/hyperpod-config

# Set KUBECONFIG
export KUBECONFIG=~/.kube/hyperpod-config

# Verify access
kubectl get nodes

# Expected output:
# NAME                          STATUS   ROLES    AGE   VERSION
# ip-10-0-1-100.ec2.internal   Ready    <none>   5m    v1.29.0
# ip-10-0-1-101.ec2.internal   Ready    <none>   5m    v1.29.0
# ...
```

## Step 6: Install PyTorch Training Operator

```bash
# Add Kubeflow Helm repo
helm repo add kubeflow https://kubeflow.github.io/helm-charts
helm repo update

# Install Training Operator
helm install training-operator kubeflow/training-operator \
  --namespace kubeflow \
  --create-namespace

# Verify installation
kubectl get pods -n kubeflow
```

## Step 7: Install NVIDIA Device Plugin

```bash
# Install NVIDIA device plugin
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

# Verify GPUs are detected
kubectl get nodes -o json | jq '.items[].status.capacity["nvidia.com/gpu"]'
```

## Step 8: Install EFA Device Plugin

```bash
# Create EFA device plugin manifest
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: aws-efa-k8s-device-plugin-daemonset
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: aws-efa-k8s-device-plugin
  template:
    metadata:
      labels:
        name: aws-efa-k8s-device-plugin
    spec:
      hostNetwork: true
      containers:
      - name: aws-efa-k8s-device-plugin
        image: public.ecr.aws/eks/efa-device-plugin:v0.4.0
        securityContext:
          privileged: true
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
EOF

# Verify EFA devices
kubectl get nodes -o json | jq '.items[].status.capacity["vpc.amazonaws.com/efa"]'
```

## Step 9: (Optional) Install Kueue

For job queuing and fair scheduling:

```bash
# Install Kueue
kubectl apply --server-side -f https://github.com/kubernetes-sigs/kueue/releases/download/v0.6.0/manifests.yaml

# Create ClusterQueue for GPU resources
cat <<EOF | kubectl apply -f -
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: gpu-cluster-queue
spec:
  namespaceSelector: {}
  resourceGroups:
  - coveredResources: ["cpu", "memory", "nvidia.com/gpu"]
    flavors:
    - name: gpu-p5
      resources:
      - name: "cpu"
        nominalQuota: 768
      - name: "memory"
        nominalQuota: 8Ti
      - name: "nvidia.com/gpu"
        nominalQuota: 32
EOF

# Create LocalQueue for default namespace
cat <<EOF | kubectl apply -f -
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: default
  name: training-queue
spec:
  clusterQueue: gpu-cluster-queue
EOF
```

## Verification Checklist

After cluster creation, verify:

```bash
# Check all nodes are Ready
kubectl get nodes

# Check GPU resources
kubectl describe nodes | grep -A5 "Allocated resources"

# Check system pods
kubectl get pods -n kube-system

# Check device plugins
kubectl get pods -n kube-system | grep -E "(nvidia|efa)"

# Test GPU access
kubectl run gpu-test --rm -it --restart=Never \
  --image=nvidia/cuda:12.0-base \
  --limits=nvidia.com/gpu=1 \
  -- nvidia-smi
```

## Cluster Management

### Update Cluster

```bash
# Update cluster configuration
hyp update --config cluster-config.yaml

# Scale node group
kubectl scale nodegroup gpu-workers --replicas=8
```

### Delete Cluster

```bash
# Delete cluster and all resources
hyp delete --region us-west-2

# Confirm deletion
hyp get cluster-status
```

## Next Steps

- [Submit training jobs](job-submission.md)
- [Configure monitoring](../../references/prerequisites-checklist.md)
- [Troubleshooting guide](troubleshooting.md)
