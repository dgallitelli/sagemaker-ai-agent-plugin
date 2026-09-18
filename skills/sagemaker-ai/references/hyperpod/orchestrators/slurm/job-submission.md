# Slurm Job Submission Guide

This guide covers submitting distributed training jobs on HyperPod with Slurm orchestration.

## Overview

Slurm provides multiple job submission methods:
- **sbatch**: Submit batch jobs (most common)
- **srun**: Run interactive/parallel commands
- **salloc**: Allocate resources interactively

## Basic Job Submission

### Simple SBATCH Script

```bash
#!/bin/bash
#SBATCH --job-name=my-training
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=8
#SBATCH --partition=gpu
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

# Load environment
source /fsx/miniconda3/bin/activate pytorch

# Run training
python train.py --epochs 100
```

### Submit Job

```bash
# Create logs directory
mkdir -p logs

# Submit job
sbatch train.sbatch

# Check status
squeue -u $USER

# View output
tail -f logs/my-training_12345.out
```

## Multi-Node Distributed Training

### PyTorch DDP with torchrun

```bash
#!/bin/bash
#SBATCH --job-name=distributed-training
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=8
#SBATCH --cpus-per-task=96
#SBATCH --partition=gpu
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#SBATCH --exclusive

# Set environment
source /fsx/miniconda3/bin/activate pytorch

# NCCL configuration
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0
export FI_EFA_USE_DEVICE_RDMA=1
export FI_PROVIDER=efa

# Get master node address
export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
export MASTER_PORT=29500

# Calculate world size
export WORLD_SIZE=$((SLURM_NNODES * 8))

echo "Starting distributed training"
echo "Master: $MASTER_ADDR:$MASTER_PORT"
echo "Nodes: $SLURM_NNODES"
echo "World size: $WORLD_SIZE"

# Run with srun
srun --ntasks=$SLURM_NNODES --ntasks-per-node=1 \
    torchrun \
    --nproc_per_node=8 \
    --nnodes=$SLURM_NNODES \
    --node_rank=$SLURM_NODEID \
    --master_addr=$MASTER_ADDR \
    --master_port=$MASTER_PORT \
    train.py \
    --batch-size 64 \
    --epochs 100
```

### DeepSpeed Training

```bash
#!/bin/bash
#SBATCH --job-name=deepspeed-training
#SBATCH --nodes=8
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=8
#SBATCH --partition=gpu
#SBATCH --time=72:00:00
#SBATCH --output=logs/%x_%j.out

source /fsx/miniconda3/bin/activate pytorch

export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
export MASTER_PORT=29500

# Create hostfile for DeepSpeed
scontrol show hostname $SLURM_NODELIST > hostfile.txt
sed -i 's/$/ slots=8/' hostfile.txt

# Run DeepSpeed
deepspeed --hostfile hostfile.txt \
    --master_addr $MASTER_ADDR \
    --master_port $MASTER_PORT \
    train.py \
    --deepspeed ds_config.json
```

### FSDP Training

```bash
#!/bin/bash
#SBATCH --job-name=fsdp-training
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=8
#SBATCH --gpus-per-node=8
#SBATCH --partition=gpu
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x_%j.out

source /fsx/miniconda3/bin/activate pytorch

export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
export MASTER_PORT=29500
export WORLD_SIZE=$SLURM_NTASKS

# FSDP-specific settings
export CUDA_DEVICE_MAX_CONNECTIONS=1

srun torchrun \
    --nproc_per_node=8 \
    --nnodes=$SLURM_NNODES \
    --rdzv_backend=c10d \
    --rdzv_endpoint=$MASTER_ADDR:$MASTER_PORT \
    train_fsdp.py
```

## Interactive Jobs

### Allocate Resources

```bash
# Allocate 2 nodes with GPUs
salloc --nodes=2 --gpus-per-node=8 --partition=gpu --time=4:00:00

# Run commands on allocated nodes
srun nvidia-smi

# Exit allocation
exit
```

### Interactive Shell on GPU Node

```bash
# Get shell on GPU node
srun --nodes=1 --gpus=8 --partition=gpu --time=2:00:00 --pty bash

# Run interactive commands
nvidia-smi
python -c "import torch; print(torch.cuda.device_count())"
```

## Job Arrays

### Hyperparameter Sweep

```bash
#!/bin/bash
#SBATCH --job-name=hp-sweep
#SBATCH --array=0-9
#SBATCH --nodes=1
#SBATCH --gpus=8
#SBATCH --partition=gpu
#SBATCH --time=4:00:00
#SBATCH --output=logs/%x_%A_%a.out

source /fsx/miniconda3/bin/activate pytorch

# Define hyperparameters
LEARNING_RATES=(1e-3 5e-4 1e-4 5e-5 1e-5 5e-3 1e-2 5e-2 1e-1 5e-1)
LR=${LEARNING_RATES[$SLURM_ARRAY_TASK_ID]}

echo "Running with learning rate: $LR"

python train.py --lr $LR --output-dir results/lr_$LR
```

### Submit Array Job

```bash
# Submit all array tasks
sbatch hp_sweep.sbatch

# Submit subset of tasks
sbatch --array=0-4 hp_sweep.sbatch

# Check array status
squeue -u $USER
```

## Job Dependencies

### Sequential Jobs

```bash
# Submit first job
JOB1=$(sbatch --parsable pretrain.sbatch)
echo "Pretrain job: $JOB1"

# Submit dependent job
JOB2=$(sbatch --parsable --dependency=afterok:$JOB1 finetune.sbatch)
echo "Finetune job: $JOB2"

# Submit final evaluation
sbatch --dependency=afterok:$JOB2 evaluate.sbatch
```

### Dependency Types

| Type | Description |
|------|-------------|
| `afterok:jobid` | Start after job completes successfully |
| `afternotok:jobid` | Start after job fails |
| `afterany:jobid` | Start after job completes (any status) |
| `singleton` | Only one job with this name runs at a time |

## Resource Specification

### Common SBATCH Options

```bash
#SBATCH --job-name=NAME          # Job name
#SBATCH --nodes=N                # Number of nodes
#SBATCH --ntasks=N               # Total tasks
#SBATCH --ntasks-per-node=N      # Tasks per node
#SBATCH --cpus-per-task=N        # CPUs per task
#SBATCH --gpus=N                 # Total GPUs
#SBATCH --gpus-per-node=N        # GPUs per node
#SBATCH --gpus-per-task=N        # GPUs per task
#SBATCH --mem=N                  # Memory per node
#SBATCH --mem-per-cpu=N          # Memory per CPU
#SBATCH --time=HH:MM:SS          # Time limit
#SBATCH --partition=NAME         # Partition name
#SBATCH --exclusive              # Exclusive node access
#SBATCH --constraint=FEATURE     # Node feature requirement
```

### GPU-Specific Options

```bash
# Request specific GPU type (if multiple types)
#SBATCH --gres=gpu:h100:8

# Request GPUs with specific memory
#SBATCH --gpus=8
#SBATCH --mem=1000G
```

## Job Monitoring

### Check Queue Status

```bash
# View all jobs
squeue

# View your jobs
squeue -u $USER

# View specific partition
squeue -p gpu

# Detailed job info
squeue -l -u $USER

# Watch queue
watch -n 5 squeue -u $USER
```

### Job Information

```bash
# Get job details
scontrol show job <jobid>

# View job steps
sacct -j <jobid>

# View resource usage
sacct -j <jobid> --format=JobID,Elapsed,MaxRSS,MaxVMSize,State

# View efficiency
seff <jobid>
```

### Cancel Jobs

```bash
# Cancel specific job
scancel <jobid>

# Cancel all your jobs
scancel -u $USER

# Cancel jobs by name
scancel --name=training

# Cancel pending jobs only
scancel -t PENDING -u $USER
```

## Output Management

### Log File Patterns

```bash
#SBATCH --output=logs/%x_%j.out   # stdout: jobname_jobid.out
#SBATCH --error=logs/%x_%j.err    # stderr: jobname_jobid.err

# Combined output
#SBATCH --output=logs/%x_%j.log
#SBATCH --error=logs/%x_%j.log
```

### Log Variables

| Variable | Description |
|----------|-------------|
| `%j` | Job ID |
| `%x` | Job name |
| `%N` | Node name |
| `%a` | Array task ID |
| `%A` | Array job ID |

### Monitor Output

```bash
# Follow output
tail -f logs/training_12345.out

# View last N lines
tail -n 100 logs/training_12345.out

# Search logs
grep "epoch" logs/training_12345.out
```

## Checkpointing

### Checkpoint Script

```bash
#!/bin/bash
#SBATCH --job-name=training-ckpt
#SBATCH --nodes=4
#SBATCH --gpus-per-node=8
#SBATCH --partition=gpu
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --signal=B:USR1@60      # Send USR1 60 seconds before timeout

# Checkpoint handler
checkpoint_handler() {
    echo "Received signal, saving checkpoint..."
    # Signal sent to training process
    kill -USR1 $TRAINING_PID
    wait $TRAINING_PID
    echo "Checkpoint saved, requeuing job"
    scontrol requeue $SLURM_JOB_ID
}

trap checkpoint_handler USR1

source /fsx/miniconda3/bin/activate pytorch

# Run training in background
python train.py --checkpoint-dir /fsx/checkpoints/$SLURM_JOB_ID &
TRAINING_PID=$!
wait $TRAINING_PID
```

### Resume from Checkpoint

```bash
#!/bin/bash
#SBATCH --job-name=training-resume
#SBATCH --nodes=4
#SBATCH --gpus-per-node=8
#SBATCH --partition=gpu
#SBATCH --time=24:00:00

CHECKPOINT_DIR="/fsx/checkpoints"
LATEST_CKPT=$(ls -t $CHECKPOINT_DIR/checkpoint_*.pt | head -1)

if [[ -f "$LATEST_CKPT" ]]; then
    echo "Resuming from $LATEST_CKPT"
    python train.py --resume $LATEST_CKPT
else
    echo "Starting fresh training"
    python train.py
fi
```

## Best Practices

### Job Script Template

```bash
#!/bin/bash
#SBATCH --job-name=PROJECT-EXPERIMENT
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=8
#SBATCH --cpus-per-task=96
#SBATCH --mem=0                  # All memory
#SBATCH --partition=gpu
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#SBATCH --exclusive

set -euo pipefail

# Print job info
echo "Job ID: $SLURM_JOB_ID"
echo "Nodes: $SLURM_NODELIST"
echo "Start time: $(date)"

# Environment setup
source /fsx/miniconda3/bin/activate pytorch
module load cuda/12.1

# NCCL/EFA configuration
export NCCL_DEBUG=WARN
export NCCL_SOCKET_IFNAME=eth0
export FI_EFA_USE_DEVICE_RDMA=1
export FI_PROVIDER=efa

# Distributed setup
export MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
export MASTER_PORT=29500

# Run training
srun torchrun \
    --nproc_per_node=8 \
    --nnodes=$SLURM_NNODES \
    --node_rank=$SLURM_NODEID \
    --master_addr=$MASTER_ADDR \
    --master_port=$MASTER_PORT \
    train.py \
    "$@"

echo "End time: $(date)"
```

### Resource Efficiency

1. **Request only what you need**: Don't over-allocate resources
2. **Use exclusive mode**: For multi-node training, use `--exclusive`
3. **Set reasonable time limits**: Allows backfill scheduling
4. **Monitor GPU utilization**: Use `nvidia-smi` to check efficiency

### Debugging

```bash
# Test with single node first
sbatch --nodes=1 train.sbatch

# Add verbose output
export NCCL_DEBUG=INFO
export TORCH_DISTRIBUTED_DEBUG=DETAIL

# Interactive debugging
srun --nodes=1 --gpus=8 --pty bash
```

## Troubleshooting

### Job Pending Too Long

```bash
# Check why job is pending
squeue -j <jobid> -o "%R"

# Common reasons:
# (Resources)    - Waiting for resources
# (Priority)     - Lower priority than other jobs
# (Dependency)   - Waiting for dependent job
# (QOSMaxJobsPerUserLimit) - User job limit reached
```

### Job Failed Immediately

```bash
# Check job exit code
sacct -j <jobid> --format=JobID,State,ExitCode

# View error logs
cat logs/training_12345.err
```

See [troubleshooting.md](troubleshooting.md) for more solutions.
