# HyperPod with EKS Orchestration

Amazon SageMaker HyperPod with Amazon EKS provides Kubernetes-native orchestration for ML training workloads.

## Overview

EKS orchestration offers:
- **Kubernetes-native job management**: Use familiar kubectl and YAML manifests
- **Container-based workloads**: Deploy training jobs as containers
- **Ecosystem integration**: Leverage Kubernetes tools (Prometheus, Kueue, etc.)
- **GitOps workflows**: Declarative infrastructure and job management
- **Multi-tenant support**: Namespace isolation and RBAC

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EKS Control Plane                        │
│                      (AWS Managed)                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────┐
│                     HyperPod Cluster                            │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  System Nodes   │  │   GPU Workers   │  │   GPU Workers   │ │
│  │  (Controllers)  │  │  (ml.p5.48xl)   │  │  (ml.p5.48xl)   │ │
│  │                 │  │                 │  │                 │ │
│  │ - CoreDNS       │  │ - Training Pods │  │ - Training Pods │ │
│  │ - Metrics       │  │ - NCCL Workers  │  │ - NCCL Workers  │ │
│  │ - Device Plugin │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### HyperPod CLI (hyp)

The `hyp` CLI manages HyperPod EKS clusters:

```bash
# Install
pip install hyperpod

# Common commands
hyp init cluster-stack      # Initialize new cluster
hyp configure              # Configure cluster settings
hyp validate               # Validate configuration
hyp create                 # Create cluster
hyp delete                 # Delete cluster
hyp get kubeconfig         # Get kubectl config
```

### PyTorch Training Operator

Kubernetes operator for distributed PyTorch training:

```yaml
apiVersion: kubeflow.org/v1
kind: PyTorchJob
metadata:
  name: my-training
spec:
  pytorchReplicaSpecs:
    Worker:
      replicas: 2
      template:
        spec:
          containers:
          - name: pytorch
            image: my-training-image
            resources:
              limits:
                nvidia.com/gpu: 8
```

### NVIDIA Device Plugin

Exposes GPUs to Kubernetes pods:

```yaml
resources:
  limits:
    nvidia.com/gpu: 8        # Request 8 GPUs
    vpc.amazonaws.com/efa: 4 # Request 4 EFA devices
```

### Kueue (Optional)

Job queueing system for fair scheduling:

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: ResourceFlavor
metadata:
  name: gpu-p5
spec:
  nodeLabels:
    node.kubernetes.io/instance-type: ml.p5.48xlarge
```

## When to Choose EKS

### Good Fit

- Team has Kubernetes expertise
- Need container-based ML pipelines
- Want GitOps/declarative infrastructure
- Running mixed workloads (training + inference)
- Need fine-grained resource management
- Multi-tenant environments

### Challenges

- Steeper learning curve for non-K8s users
- Higher IP address consumption (~81 IPs/node)
- Additional complexity for simple training jobs

## Quick Start

1. **Prerequisites**: Complete checklist in `references/hyperpod/prerequisites-checklist.md`
2. **Create Cluster**: Follow `cluster-setup.md`
3. **Submit Jobs**: See `job-submission.md`
4. **Troubleshoot**: Reference `troubleshooting.md`

## Documentation Index

| Document | Description |
|----------|-------------|
| [cluster-setup.md](cluster-setup.md) | Step-by-step cluster creation |
| [job-submission.md](job-submission.md) | Training job workflows |
| [troubleshooting.md](troubleshooting.md) | Common issues and solutions |

## Related Resources

- [AWS EKS Documentation](https://docs.aws.amazon.com/eks/)
- [PyTorch Training Operator](https://github.com/kubeflow/training-operator)
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [Kueue](https://kueue.sigs.k8s.io/)
