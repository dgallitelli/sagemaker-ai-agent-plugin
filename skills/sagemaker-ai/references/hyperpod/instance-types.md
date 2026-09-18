# HyperPod Instance Types

This document details the accelerated instance types available for HyperPod clusters.

## Overview

HyperPod supports NVIDIA GPU and AWS Trainium instances optimized for ML training workloads.

## NVIDIA GPU Instances

### ml.p4d.24xlarge (A100 40GB)

| Specification | Value |
|---------------|-------|
| GPUs | 8x NVIDIA A100 40GB |
| GPU Memory | 320 GB total (8 × 40GB) |
| vCPUs | 96 |
| System Memory | 1152 GB |
| GPU Interconnect | NVSwitch 600 GB/s |
| Network Bandwidth | 400 Gbps |
| EFA Devices | 4 |
| Local Storage | 8 × 1TB NVMe SSD |

**Use Cases**:
- Large language model training
- Computer vision at scale
- General distributed training

**Pricing** (On-Demand, us-west-2): ~$32.77/hour

### ml.p4de.24xlarge (A100 80GB)

| Specification | Value |
|---------------|-------|
| GPUs | 8x NVIDIA A100 80GB |
| GPU Memory | 640 GB total (8 × 80GB) |
| vCPUs | 96 |
| System Memory | 1152 GB |
| GPU Interconnect | NVSwitch 600 GB/s |
| Network Bandwidth | 400 Gbps |
| EFA Devices | 4 |
| Local Storage | 8 × 1TB NVMe SSD |

**Use Cases**:
- Very large models (>40GB per GPU)
- Models requiring large batch sizes
- Memory-intensive training

**Pricing** (On-Demand, us-west-2): ~$40.96/hour

### ml.p5.48xlarge (H100)

| Specification | Value |
|---------------|-------|
| GPUs | 8x NVIDIA H100 80GB |
| GPU Memory | 640 GB total (8 × 80GB) |
| vCPUs | 192 |
| System Memory | 2048 GB |
| GPU Interconnect | NVSwitch 900 GB/s |
| Network Bandwidth | 3200 Gbps |
| EFA Devices | 32 |
| Local Storage | 8 × 3.84TB NVMe SSD |

**Use Cases**:
- Cutting-edge model training
- Maximum performance requirements
- Ultra-large distributed training

**Pricing** (On-Demand, us-west-2): ~$98.32/hour

**Key Advantages over P4d**:
- 3x higher FP8 performance
- 3x higher GPU memory bandwidth
- 8x network bandwidth
- Improved NVLink performance

## AWS Trainium Instances

### ml.trn1.32xlarge

| Specification | Value |
|---------------|-------|
| Accelerators | 16x AWS Trainium |
| Accelerator Memory | 512 GB total (16 × 32GB) |
| vCPUs | 128 |
| System Memory | 512 GB |
| Accelerator Interconnect | NeuronLink 768 GB/s |
| Network Bandwidth | 800 Gbps |
| EFA Devices | 8 |
| Local Storage | 4 × 1.9TB NVMe SSD |

**Use Cases**:
- Cost-effective training for supported models
- PyTorch/TensorFlow training
- Transformer-based models

**Pricing** (On-Demand, us-west-2): ~$21.50/hour

**Framework Support**:
- PyTorch via torch-neuronx
- TensorFlow via tensorflow-neuronx
- JAX support (preview)

### ml.trn1n.32xlarge

| Specification | Value |
|---------------|-------|
| Accelerators | 16x AWS Trainium |
| Accelerator Memory | 512 GB total |
| vCPUs | 128 |
| System Memory | 512 GB |
| Accelerator Interconnect | NeuronLink 768 GB/s |
| Network Bandwidth | 1600 Gbps |
| EFA Devices | 16 |
| Local Storage | 4 × 1.9TB NVMe SSD |

**Use Cases**:
- Large-scale distributed training
- When network bandwidth is the bottleneck
- Multi-node training with high communication

**Pricing** (On-Demand, us-west-2): ~$24.78/hour

**Key Difference from trn1.32xlarge**:
- 2x network bandwidth (1600 vs 800 Gbps)
- 2x EFA devices (16 vs 8)
- ~15% price premium

## Instance Comparison Matrix

| Instance | Accelerator | Count | Memory | Network | EFA | On-Demand $/hr |
|----------|-------------|-------|--------|---------|-----|----------------|
| ml.p4d.24xlarge | A100 40GB | 8 | 320 GB | 400 Gbps | 4 | ~$32.77 |
| ml.p4de.24xlarge | A100 80GB | 8 | 640 GB | 400 Gbps | 4 | ~$40.96 |
| ml.p5.48xlarge | H100 80GB | 8 | 640 GB | 3200 Gbps | 32 | ~$98.32 |
| ml.trn1.32xlarge | Trainium | 16 | 512 GB | 800 Gbps | 8 | ~$21.50 |
| ml.trn1n.32xlarge | Trainium | 16 | 512 GB | 1600 Gbps | 16 | ~$24.78 |

## Performance Benchmarks

### Approximate Training Throughput (LLM)

| Instance | Model Size | Tokens/sec (per node) |
|----------|------------|----------------------|
| ml.p4d.24xlarge | 7B | ~2,500 |
| ml.p4d.24xlarge | 13B | ~1,200 |
| ml.p5.48xlarge | 7B | ~7,500 |
| ml.p5.48xlarge | 13B | ~3,600 |
| ml.trn1.32xlarge | 7B | ~3,000 |
| ml.trn1.32xlarge | 13B | ~1,500 |

*Note: Actual performance varies based on model architecture, batch size, and optimization*

### Cost Efficiency (relative)

| Instance | $/Token (normalized) |
|----------|---------------------|
| ml.trn1.32xlarge | 1.0x (baseline) |
| ml.trn1n.32xlarge | 1.1x |
| ml.p4d.24xlarge | 1.8x |
| ml.p4de.24xlarge | 2.3x |
| ml.p5.48xlarge | 2.0x |

*Trainium offers best cost efficiency for compatible models*

## Selection Guide

### Choose P4d When:
- Running models requiring CUDA-specific features
- Using frameworks not yet optimized for Trainium
- Need proven, well-documented platform
- Running inference alongside training

### Choose P4de When:
- Models exceed 40GB per GPU memory
- Large batch training is critical
- Running very large models (70B+)

### Choose P5 When:
- Maximum performance is priority
- Training cutting-edge large models
- Network bandwidth is bottleneck
- Time-to-train is critical metric

### Choose Trainium When:
- Cost efficiency is priority
- Running PyTorch/TensorFlow transformers
- Model is compatible with Neuron SDK
- Large-scale training (cost adds up)

## EFA Configuration

### EFA Bandwidth by Instance

| Instance | EFA Devices | Total Bandwidth |
|----------|-------------|-----------------|
| ml.p4d.24xlarge | 4 | 400 Gbps |
| ml.p4de.24xlarge | 4 | 400 Gbps |
| ml.p5.48xlarge | 32 | 3200 Gbps |
| ml.trn1.32xlarge | 8 | 800 Gbps |
| ml.trn1n.32xlarge | 16 | 1600 Gbps |

### Optimal NCCL Configuration

```bash
# For P4d/P4de
export NCCL_ALGO=Ring
export NCCL_PROTO=Simple

# For P5
export NCCL_ALGO=Tree
export NCCL_PROTO=Simple
export NCCL_NVLS_ENABLE=1

# For Trainium (uses Neuron CC, not NCCL)
export NEURON_RT_VISIBLE_CORES=0-15
```

## Local Storage

### NVMe SSD Configuration

| Instance | Drives | Total Capacity | Typical Use |
|----------|--------|----------------|-------------|
| ml.p4d.24xlarge | 8 × 1TB | 8 TB | Checkpoints, cache |
| ml.p4de.24xlarge | 8 × 1TB | 8 TB | Checkpoints, cache |
| ml.p5.48xlarge | 8 × 3.84TB | 30.7 TB | Large datasets |
| ml.trn1.32xlarge | 4 × 1.9TB | 7.6 TB | Checkpoints, cache |
| ml.trn1n.32xlarge | 4 × 1.9TB | 7.6 TB | Checkpoints, cache |

### Configuring Local Storage

```bash
# Mount NVMe drives (in lifecycle script)
NVME_DEVICES=$(lsblk -d -o name,type | grep disk | grep nvme | awk '{print $1}')

# Create RAID-0 for maximum throughput
mdadm --create /dev/md0 --level=0 --raid-devices=$(echo $NVME_DEVICES | wc -w) \
    $(echo $NVME_DEVICES | sed 's/\b/\/dev\//g')

mkfs.xfs /dev/md0
mount /dev/md0 /local
```

## Quotas and Availability

### Default Quotas (per account, per region)

| Instance Type | Default Quota | Quota Code |
|---------------|---------------|------------|
| ml.p4d.24xlarge | 0 | L-xxxxx |
| ml.p4de.24xlarge | 0 | L-xxxxx |
| ml.p5.48xlarge | 0 | L-xxxxx |
| ml.trn1.32xlarge | 0 | L-xxxxx |
| ml.trn1n.32xlarge | 0 | L-xxxxx |

### Request Quota Increase

```bash
# List current quotas
aws service-quotas list-service-quotas \
    --service-code sagemaker \
    --query "Quotas[?contains(QuotaName, 'cluster')]"

# Request increase
aws service-quotas request-service-quota-increase \
    --service-code sagemaker \
    --quota-code L-xxxxx \
    --desired-value 16
```

### Regional Availability

| Instance | us-east-1 | us-west-2 | eu-west-1 | ap-northeast-1 |
|----------|-----------|-----------|-----------|----------------|
| ml.p4d.24xlarge | ✓ | ✓ | ✓ | ✓ |
| ml.p4de.24xlarge | ✓ | ✓ | Limited | Limited |
| ml.p5.48xlarge | ✓ | ✓ | ✓ | Limited |
| ml.trn1.32xlarge | ✓ | ✓ | ✓ | ✓ |
| ml.trn1n.32xlarge | ✓ | ✓ | Limited | Limited |

*Check AWS documentation for latest availability*

## Capacity Planning

### Estimating Cluster Size

```
Nodes needed = Total GPU memory required / GPU memory per node

Example: Training 70B model
- Minimum GPU memory: ~140GB (FP16)
- With optimizer states: ~560GB (AdamW FP32)
- p4d nodes needed: 560GB / 320GB = 2 nodes minimum
- p5 nodes needed: 560GB / 640GB = 1 node minimum
```

### Cost Estimation

```
Monthly cost = Nodes × $/hour × Hours/month × Utilization

Example: 4-node P4d cluster, 720 hours/month, 80% utilization
Cost = 4 × $32.77 × 720 × 0.8 = $75,536/month
```
