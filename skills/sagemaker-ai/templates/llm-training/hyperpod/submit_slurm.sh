#!/bin/bash
# HyperPod Slurm Job Submission Script
#
# Prerequisites:
#   1. HyperPod cluster running with Slurm orchestrator
#   2. Recipe config file (recipe_config.yaml) customized
#   3. SSH access to HyperPod head node
#
# Usage:
#   ssh hyperpod-cluster
#   sbatch submit_slurm.sh

#SBATCH --job-name=llm-training
#SBATCH --nodes=1                    # Number of nodes
#SBATCH --ntasks-per-node=4          # Processes per node (= GPUs)
#SBATCH --gres=gpu:4                 # GPUs per node
#SBATCH --cpus-per-task=12           # CPUs per GPU
#SBATCH --time=24:00:00              # Max runtime
#SBATCH --output=logs/%x_%j.out      # Output log
#SBATCH --error=logs/%x_%j.err       # Error log
#SBATCH --exclusive                  # Exclusive node access

# ========================================
# Environment Setup
# ========================================
set -eo pipefail

# Load modules (adjust based on your HyperPod setup)
# module load cuda/12.1
# module load nccl

# Activate Python environment
source /opt/conda/bin/activate pytorch

# Set environment variables
export CUDA_DEVICE_MAX_CONNECTIONS=1
export NCCL_DEBUG=INFO
export NCCL_IB_DISABLE=0
export NCCL_NET_GDR_LEVEL=2

# Hugging Face cache (use shared storage)
export HF_HOME=/fsx/shared/huggingface
export TRANSFORMERS_CACHE=/fsx/shared/huggingface/hub

# ========================================
# Configuration
# ========================================
CONFIG_FILE="${1:-recipe_config.yaml}"
TRAIN_SCRIPT="${2:-/fsx/shared/scripts/train.py}"

# Validate config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Create output directories
mkdir -p logs checkpoints

echo "=============================================="
echo "Job: $SLURM_JOB_NAME (ID: $SLURM_JOB_ID)"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "GPUs per node: $SLURM_GPUS_ON_NODE"
echo "Config: $CONFIG_FILE"
echo "=============================================="

# ========================================
# Launch Training
# ========================================

# Get master address and port
MASTER_ADDR=$(scontrol show hostname $SLURM_NODELIST | head -n1)
MASTER_PORT=${MASTER_PORT:-29500}

# Calculate world size
WORLD_SIZE=$((SLURM_JOB_NUM_NODES * SLURM_NTASKS_PER_NODE))

echo "Master: $MASTER_ADDR:$MASTER_PORT"
echo "World size: $WORLD_SIZE"

# Launch with torchrun
srun --kill-on-bad-exit=1 \
    torchrun \
    --nnodes=$SLURM_JOB_NUM_NODES \
    --nproc_per_node=$SLURM_NTASKS_PER_NODE \
    --rdzv_id=$SLURM_JOB_ID \
    --rdzv_backend=c10d \
    --rdzv_endpoint=$MASTER_ADDR:$MASTER_PORT \
    $TRAIN_SCRIPT \
    --config $CONFIG_FILE

echo "Training complete!"

# ========================================
# Alternative: Use HyperPod Recipes CLI
# ========================================
# If using the official sagemaker-hyperpod-recipes package:
#
# pip install sagemaker-hyperpod-recipes
#
# hyperpod-recipes run \
#     --recipe llama3.1-8b-sft \
#     --config $CONFIG_FILE \
#     --cluster-type slurm
