#!/bin/bash
# lifecycle-script-example.sh
# Complete lifecycle script for HyperPod nodes
#
# This script runs once when a node is created. It handles:
# - System configuration
# - Network/EFA setup
# - FSx mounting
# - ML framework installation
# - Monitoring setup
#
# Upload to S3 as 'on_create.sh'

set -euo pipefail

# ============================================
# Configuration
# ============================================

# Log all output
LOG_FILE="/var/log/hyperpod-on-create.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "HyperPod Lifecycle Script"
echo "Started at: $(date)"
echo "Hostname: $(hostname)"
echo "=========================================="

# Parse provisioning parameters
PROVISIONING_PARAMS="/opt/ml/config/provisioning_parameters.json"
if [[ -f "$PROVISIONING_PARAMS" ]]; then
    echo "Reading provisioning parameters..."
    export WORKLOAD_MANAGER=$(jq -r '.workload_manager // "slurm"' "$PROVISIONING_PARAMS")
    export FSX_DNS_NAME=$(jq -r '.fsx_dns_name // empty' "$PROVISIONING_PARAMS")
    export FSX_MOUNTNAME=$(jq -r '.fsx_mountname // empty' "$PROVISIONING_PARAMS")
    export FSX_MOUNT_DIR=$(jq -r '.fsx_mount_dir // "/fsx"' "$PROVISIONING_PARAMS")
    export CONTROLLER_GROUP=$(jq -r '.controller_group // "controller"' "$PROVISIONING_PARAMS")

    echo "Workload Manager: $WORKLOAD_MANAGER"
    echo "FSx DNS: ${FSX_DNS_NAME:-not configured}"
else
    echo "Warning: Provisioning parameters not found"
    export WORKLOAD_MANAGER="slurm"
fi

# Determine node type from instance metadata
INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type || echo "unknown")
echo "Instance Type: $INSTANCE_TYPE"

# ============================================
# System Updates
# ============================================
echo ""
echo "--- Installing System Packages ---"

yum update -y

yum install -y \
    git \
    htop \
    tmux \
    jq \
    tree \
    wget \
    curl \
    vim \
    python3-pip \
    environment-modules \
    amazon-cloudwatch-agent

# ============================================
# EFA Configuration
# ============================================
echo ""
echo "--- Configuring EFA ---"

# EFA is pre-installed on HyperPod AMIs
# Verify and configure

if fi_info -p efa &>/dev/null; then
    echo "EFA is available"
    fi_info -p efa

    # Set optimal EFA environment
    cat >> /etc/profile.d/efa.sh << 'EOF'
# EFA Configuration
export FI_PROVIDER=efa
export FI_EFA_USE_DEVICE_RDMA=1
export FI_EFA_FORK_SAFE=1
EOF
else
    echo "EFA not available on this instance type"
fi

# ============================================
# NCCL Configuration
# ============================================
echo ""
echo "--- Configuring NCCL ---"

cat >> /etc/profile.d/nccl.sh << 'EOF'
# NCCL Configuration for HyperPod
export NCCL_DEBUG=WARN
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1
export NCCL_PROTO=Simple

# For large-scale training
export NCCL_TREE_THRESHOLD=0
export NCCL_BUFFSIZE=8388608

# Timeout for large models
export NCCL_TIMEOUT=1800
EOF

# ============================================
# FSx Mount
# ============================================
echo ""
echo "--- Configuring FSx Mount ---"

if [[ -n "${FSX_DNS_NAME:-}" && -n "${FSX_MOUNTNAME:-}" ]]; then
    echo "Mounting FSx Lustre filesystem..."

    # Install Lustre client if not present
    if ! lsmod | grep -q lustre; then
        amazon-linux-extras install -y lustre
    fi

    # Create mount point
    mkdir -p "$FSX_MOUNT_DIR"

    # Mount FSx
    mount -t lustre -o noatime,flock \
        "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME}" \
        "$FSX_MOUNT_DIR"

    # Add to fstab for persistence
    echo "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME} ${FSX_MOUNT_DIR} lustre noatime,flock,_netdev 0 0" >> /etc/fstab

    # Create standard directories
    mkdir -p "$FSX_MOUNT_DIR/users"
    mkdir -p "$FSX_MOUNT_DIR/datasets"
    mkdir -p "$FSX_MOUNT_DIR/checkpoints"
    mkdir -p "$FSX_MOUNT_DIR/logs"
    chmod 777 "$FSX_MOUNT_DIR/users" "$FSX_MOUNT_DIR/datasets" "$FSX_MOUNT_DIR/checkpoints" "$FSX_MOUNT_DIR/logs"

    echo "FSx mounted at $FSX_MOUNT_DIR"
    df -h "$FSX_MOUNT_DIR"
else
    echo "FSx not configured, skipping mount"
fi

# ============================================
# Shared Directories
# ============================================
echo ""
echo "--- Creating Shared Directories ---"

mkdir -p /opt/ml/shared
chmod 777 /opt/ml/shared

# Local NVMe storage (if available)
if [[ -e /dev/nvme1n1 ]]; then
    echo "Configuring local NVMe storage..."
    mkdir -p /local
    mkfs.xfs /dev/nvme1n1 -f || true
    mount /dev/nvme1n1 /local || true
    chmod 777 /local
fi

# ============================================
# Python Environment
# ============================================
echo ""
echo "--- Setting Up Python Environment ---"

# Install Miniconda (if not using container images)
if [[ -n "${FSX_MOUNT_DIR:-}" && -d "${FSX_MOUNT_DIR}" ]]; then
    CONDA_DIR="$FSX_MOUNT_DIR/miniconda3"

    if [[ ! -d "$CONDA_DIR" ]]; then
        echo "Installing Miniconda to shared storage..."
        wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
        bash /tmp/miniconda.sh -b -p "$CONDA_DIR"
        rm /tmp/miniconda.sh

        # Initialize conda for all users
        "$CONDA_DIR/bin/conda" init bash
    fi

    # Add to path
    cat >> /etc/profile.d/conda.sh << EOF
export PATH="$CONDA_DIR/bin:\$PATH"
EOF
fi

# Install common ML packages via pip (system Python)
pip3 install --upgrade pip
pip3 install \
    boto3 \
    awscli \
    tensorboard \
    wandb \
    tqdm

# ============================================
# Environment Modules
# ============================================
echo ""
echo "--- Configuring Environment Modules ---"

mkdir -p /usr/share/Modules/modulefiles/cuda

# CUDA module
cat > /usr/share/Modules/modulefiles/cuda/12.1 << 'EOF'
#%Module1.0
proc ModulesHelp { } {
    puts stderr "CUDA 12.1 Toolkit"
}
module-whatis "CUDA 12.1"
prepend-path PATH /usr/local/cuda-12.1/bin
prepend-path LD_LIBRARY_PATH /usr/local/cuda-12.1/lib64
setenv CUDA_HOME /usr/local/cuda-12.1
EOF

# ============================================
# SSH Configuration (for multi-node)
# ============================================
echo ""
echo "--- Configuring SSH ---"

# Allow SSH between nodes (HyperPod manages keys)
cat >> /etc/ssh/sshd_config << 'EOF'
# HyperPod SSH Configuration
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
LogLevel ERROR
EOF

# Restart SSH
systemctl restart sshd

# ============================================
# Monitoring (Optional)
# ============================================
echo ""
echo "--- Configuring Monitoring ---"

# Configure CloudWatch agent (basic config)
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
    "metrics": {
        "namespace": "HyperPod",
        "metrics_collected": {
            "cpu": {
                "measurement": ["usage_active"],
                "metrics_collection_interval": 60
            },
            "mem": {
                "measurement": ["mem_used_percent"],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": ["used_percent"],
                "metrics_collection_interval": 60,
                "resources": ["/", "/fsx"]
            }
        }
    },
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/hyperpod-*.log",
                        "log_group_name": "/hyperpod/nodes",
                        "log_stream_name": "{instance_id}"
                    }
                ]
            }
        }
    }
}
EOF

# Start CloudWatch agent
systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent || true

# ============================================
# Slurm-Specific Configuration
# ============================================
if [[ "$WORKLOAD_MANAGER" == "slurm" ]]; then
    echo ""
    echo "--- Slurm-Specific Configuration ---"

    # Slurm is configured by HyperPod
    # Add any custom configurations here

    # Custom prolog/epilog scripts
    mkdir -p /etc/slurm/scripts

    cat > /etc/slurm/scripts/prolog.sh << 'EOF'
#!/bin/bash
# Pre-job script
logger "SLURM: Starting job $SLURM_JOB_ID on $(hostname)"
EOF

    cat > /etc/slurm/scripts/epilog.sh << 'EOF'
#!/bin/bash
# Post-job cleanup
logger "SLURM: Completed job $SLURM_JOB_ID on $(hostname)"
# Clean up temp files
rm -rf /tmp/slurm-$SLURM_JOB_ID 2>/dev/null || true
rm -rf /dev/shm/slurm-$SLURM_JOB_ID 2>/dev/null || true
EOF

    chmod +x /etc/slurm/scripts/*.sh
fi

# ============================================
# EKS-Specific Configuration
# ============================================
if [[ "$WORKLOAD_MANAGER" == "eks" ]]; then
    echo ""
    echo "--- EKS-Specific Configuration ---"

    # Configure containerd for NVIDIA (if not already)
    if [[ -f /etc/containerd/config.toml ]]; then
        echo "Containerd already configured"
    fi

    # Additional EKS configurations can go here
fi

# ============================================
# GPU Verification
# ============================================
echo ""
echo "--- GPU Verification ---"

if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPUs detected:"
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader

    # Check NVLink (for multi-GPU systems)
    nvidia-smi nvlink -s 2>/dev/null || echo "NVLink status not available"
else
    echo "No NVIDIA GPUs detected (or drivers not installed)"
fi

# Check for Trainium
if command -v neuron-ls &> /dev/null; then
    echo "AWS Trainium detected:"
    neuron-ls
fi

# ============================================
# Final Verification
# ============================================
echo ""
echo "=========================================="
echo "Configuration Summary"
echo "=========================================="
echo "Hostname: $(hostname)"
echo "Instance Type: $INSTANCE_TYPE"
echo "Workload Manager: $WORKLOAD_MANAGER"
echo "FSx Mount: ${FSX_MOUNT_DIR:-not configured}"
echo ""
echo "Network Interfaces:"
ip addr show | grep -E "^[0-9]+:|inet " | head -20
echo ""
echo "Storage:"
df -h | grep -E "^/dev|^Filesystem"
echo ""
echo "Memory:"
free -h
echo ""
echo "=========================================="
echo "Lifecycle script completed at: $(date)"
echo "=========================================="

exit 0
