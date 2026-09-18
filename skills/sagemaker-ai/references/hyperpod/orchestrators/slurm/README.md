# HyperPod with Slurm Orchestration

Amazon SageMaker HyperPod with Slurm provides traditional HPC workload management for ML training.

## Overview

Slurm (Simple Linux Utility for Resource Management) orchestration offers:
- **Familiar HPC interface**: sbatch, srun, squeue commands
- **Simple job scripts**: Bash-based SBATCH scripts
- **Direct node access**: SSH between nodes for debugging
- **Partition management**: Logical grouping of compute resources
- **Resource reservation**: Dedicated node allocation
- **Array jobs**: Built-in support for hyperparameter sweeps

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HyperPod Cluster                            │
│                                                                 │
│  ┌─────────────────┐                                           │
│  │ Controller Node │ ← Slurm Controller (slurmctld)            │
│  │  (ml.m5.xlarge) │ ← Job scheduling                          │
│  └────────┬────────┘                                           │
│           │                                                     │
│  ┌────────┴────────────────────────────────────────────────┐   │
│  │                    Compute Partition                     │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │ GPU Worker  │  │ GPU Worker  │  │ GPU Worker  │      │   │
│  │  │(ml.p5.48xl) │  │(ml.p5.48xl) │  │(ml.p5.48xl) │      │   │
│  │  │             │  │             │  │             │      │   │
│  │  │ 8x H100 GPU │  │ 8x H100 GPU │  │ 8x H100 GPU │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Shared Storage                        │   │
│  │              (FSx for Lustre - Optional)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### Slurm Commands

| Command | Description |
|---------|-------------|
| `sbatch` | Submit batch job script |
| `srun` | Run interactive/parallel job |
| `squeue` | View job queue |
| `scancel` | Cancel job |
| `sinfo` | View partition/node info |
| `scontrol` | Administrative control |

### Node Types

| Type | Purpose | Typical Instance |
|------|---------|------------------|
| Controller | Job scheduling, cluster management | ml.m5.xlarge |
| Login | User access point (optional) | ml.m5.xlarge |
| Compute | Training workloads | ml.p5.48xlarge |

### Partitions

Logical groupings of compute nodes:

```
gpu        # GPU compute nodes
cpu        # CPU-only nodes (if any)
interactive # For debugging
```

## When to Choose Slurm

### Good Fit

- Team has HPC background
- Familiar with SBATCH job submission
- Need simple, direct cluster access
- Running primarily batch training jobs
- Want lower IP consumption than EKS
- Need traditional HPC scheduling features

### Challenges

- Less container-native than Kubernetes
- Manual environment management
- Limited ecosystem integrations
- Requires filesystem for code/data sharing

## Quick Start

1. **Prerequisites**: Complete checklist in `references/hyperpod/prerequisites-checklist.md`
2. **Prepare Scripts**: Create lifecycle scripts per `references/hyperpod/lifecycle-scripts.md`
3. **Create Cluster**: Follow `cluster-setup.md`
4. **Submit Jobs**: See `job-submission.md`
5. **Troubleshoot**: Reference `troubleshooting.md`

## Documentation Index

| Document | Description |
|----------|-------------|
| [cluster-setup.md](cluster-setup.md) | Step-by-step cluster creation |
| [job-submission.md](job-submission.md) | SBATCH job workflows |
| [troubleshooting.md](troubleshooting.md) | Common issues and solutions |

## Sample Job Script

```bash
#!/bin/bash
#SBATCH --job-name=training
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-node=8
#SBATCH --partition=gpu
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

# Load modules
module load cuda/12.1
module load nccl

# Set environment
export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
export MASTER_PORT=29500

# Run distributed training
srun torchrun \
    --nproc_per_node=8 \
    --nnodes=4 \
    --node_rank=$SLURM_NODEID \
    --master_addr=$MASTER_ADDR \
    --master_port=$MASTER_PORT \
    train.py
```

## Related Resources

- [Slurm Documentation](https://slurm.schedmd.com/documentation.html)
- [AWS HPC Blog](https://aws.amazon.com/blogs/hpc/)
- [FSx for Lustre Documentation](https://docs.aws.amazon.com/fsx/latest/LustreGuide/)
