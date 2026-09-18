# HyperPod Lifecycle Scripts

Lifecycle scripts configure nodes when they join the cluster. This document provides templates and best practices.

## Overview

HyperPod executes lifecycle scripts at specific points in the node lifecycle:

| Script | When Executed | Purpose |
|--------|---------------|---------|
| `on_create.sh` | Once, at node creation | Initial setup, software installation |
| `on_start.sh` | Each node boot | Runtime configuration |
| `provisioning_parameters.json` | Read at creation | Configuration parameters |

## Script Location

Scripts must be stored in S3 and referenced in cluster configuration:

```
s3://your-bucket/hyperpod/
├── on_create.sh
├── on_start.sh (optional)
└── provisioning_parameters.json
```

## provisioning_parameters.json

### Basic Structure

```json
{
  "version": "1.0",
  "workload_manager": "slurm",
  "controller_group": "controller-group",
  "worker_groups": [
    {
      "instance_group_name": "worker-group-1",
      "partition_name": "gpu"
    }
  ],
  "fsx_dns_name": "fs-xxxxx.fsx.us-west-2.amazonaws.com",
  "fsx_mountname": "xxxxx"
}
```

### Slurm Configuration

```json
{
  "version": "1.0",
  "workload_manager": "slurm",
  "controller_group": "controller",
  "login_group": "login",
  "worker_groups": [
    {
      "instance_group_name": "gpu-workers",
      "partition_name": "gpu"
    },
    {
      "instance_group_name": "cpu-workers",
      "partition_name": "cpu"
    }
  ],
  "fsx_dns_name": "fs-xxxxx.fsx.us-west-2.amazonaws.com",
  "fsx_mountname": "xxxxx",
  "fsx_mount_dir": "/fsx"
}
```

### EKS Configuration

```json
{
  "version": "1.0",
  "workload_manager": "eks",
  "eks_cluster_name": "hyperpod-eks-cluster",
  "controller_group": "system",
  "worker_groups": [
    {
      "instance_group_name": "gpu-workers",
      "node_labels": {
        "node-type": "gpu",
        "accelerator": "nvidia"
      }
    }
  ]
}
```

## on_create.sh Template

### Basic Template

```bash
#!/bin/bash
set -euo pipefail

# Log all output
exec > >(tee -a /var/log/hyperpod-on-create.log) 2>&1
echo "Starting on_create.sh at $(date)"

# ============================================
# System Updates
# ============================================
echo "Updating system packages..."
yum update -y

# ============================================
# Install Common Dependencies
# ============================================
echo "Installing dependencies..."
yum install -y \
    git \
    htop \
    tmux \
    jq \
    python3-pip

# ============================================
# Configure EFA
# ============================================
echo "Configuring EFA..."
# EFA is pre-installed on HyperPod AMIs
# Verify installation
fi_info -p efa || echo "EFA not available on this instance type"

# ============================================
# Configure NCCL
# ============================================
echo "Configuring NCCL environment..."
cat >> /etc/environment << 'EOF'
NCCL_DEBUG=INFO
NCCL_SOCKET_IFNAME=eth0
NCCL_IB_DISABLE=1
FI_EFA_USE_DEVICE_RDMA=1
FI_PROVIDER=efa
EOF

# ============================================
# Mount FSx (if configured)
# ============================================
FSX_DNS_NAME="${FSX_DNS_NAME:-}"
FSX_MOUNTNAME="${FSX_MOUNTNAME:-}"
FSX_MOUNT_DIR="${FSX_MOUNT_DIR:-/fsx}"

if [[ -n "$FSX_DNS_NAME" && -n "$FSX_MOUNTNAME" ]]; then
    echo "Mounting FSx Lustre..."
    mkdir -p "$FSX_MOUNT_DIR"
    mount -t lustre -o noatime,flock \
        "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME}" \
        "$FSX_MOUNT_DIR"

    # Add to fstab for persistence
    echo "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME} ${FSX_MOUNT_DIR} lustre noatime,flock,_netdev 0 0" >> /etc/fstab
fi

# ============================================
# Create shared directories
# ============================================
echo "Creating shared directories..."
mkdir -p /opt/ml/shared
chmod 777 /opt/ml/shared

# ============================================
# Configure SSH (for multi-node jobs)
# ============================================
echo "Configuring SSH..."
# HyperPod handles SSH key distribution automatically
# Additional configuration if needed:
cat >> /etc/ssh/sshd_config << 'EOF'
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
EOF

systemctl restart sshd

# ============================================
# Install ML Frameworks (optional)
# ============================================
echo "Installing PyTorch..."
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu118

echo "on_create.sh completed successfully at $(date)"
exit 0
```

### Slurm-Specific on_create.sh

```bash
#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/hyperpod-on-create.log) 2>&1
echo "Starting Slurm on_create.sh at $(date)"

# ============================================
# Parse provisioning parameters
# ============================================
PROVISIONING_PARAMS="/opt/ml/config/provisioning_parameters.json"
if [[ -f "$PROVISIONING_PARAMS" ]]; then
    export FSX_DNS_NAME=$(jq -r '.fsx_dns_name // empty' "$PROVISIONING_PARAMS")
    export FSX_MOUNTNAME=$(jq -r '.fsx_mountname // empty' "$PROVISIONING_PARAMS")
    export FSX_MOUNT_DIR=$(jq -r '.fsx_mount_dir // "/fsx"' "$PROVISIONING_PARAMS")
    export PARTITION_NAME=$(jq -r '.worker_groups[0].partition_name // "compute"' "$PROVISIONING_PARAMS")
fi

# ============================================
# Configure Slurm
# ============================================
echo "Configuring Slurm..."

# Slurm configuration is managed by HyperPod
# Add custom configurations here if needed

# Configure Slurm prolog/epilog scripts if needed
mkdir -p /etc/slurm/scripts

cat > /etc/slurm/scripts/prolog.sh << 'EOF'
#!/bin/bash
# Pre-job setup
echo "Starting job $SLURM_JOB_ID on $(hostname)" >> /var/log/slurm/prolog.log
EOF

cat > /etc/slurm/scripts/epilog.sh << 'EOF'
#!/bin/bash
# Post-job cleanup
echo "Completed job $SLURM_JOB_ID on $(hostname)" >> /var/log/slurm/epilog.log
# Clean up temporary files
rm -rf /tmp/slurm-$SLURM_JOB_ID
EOF

chmod +x /etc/slurm/scripts/*.sh

# ============================================
# Mount FSx Lustre
# ============================================
if [[ -n "${FSX_DNS_NAME:-}" ]]; then
    echo "Mounting FSx Lustre at $FSX_MOUNT_DIR..."
    mkdir -p "$FSX_MOUNT_DIR"
    mount -t lustre -o noatime,flock \
        "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME}" \
        "$FSX_MOUNT_DIR"
    echo "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME} ${FSX_MOUNT_DIR} lustre noatime,flock,_netdev 0 0" >> /etc/fstab
fi

# ============================================
# Configure Environment Modules
# ============================================
echo "Configuring environment modules..."
yum install -y environment-modules

# Create modulefiles
mkdir -p /usr/share/Modules/modulefiles/cuda
cat > /usr/share/Modules/modulefiles/cuda/12.1 << 'EOF'
#%Module1.0
proc ModulesHelp { } {
    puts stderr "CUDA 12.1"
}
module-whatis "CUDA 12.1 Toolkit"
prepend-path PATH /usr/local/cuda-12.1/bin
prepend-path LD_LIBRARY_PATH /usr/local/cuda-12.1/lib64
EOF

# ============================================
# Configure NCCL for multi-node
# ============================================
echo "Configuring NCCL..."
cat >> /etc/profile.d/nccl.sh << 'EOF'
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0
export NCCL_IB_DISABLE=1
export FI_EFA_USE_DEVICE_RDMA=1
export FI_PROVIDER=efa
export NCCL_PROTO=simple
EOF

echo "Slurm on_create.sh completed at $(date)"
exit 0
```

### EKS-Specific on_create.sh

```bash
#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/hyperpod-on-create.log) 2>&1
echo "Starting EKS on_create.sh at $(date)"

# ============================================
# Parse provisioning parameters
# ============================================
PROVISIONING_PARAMS="/opt/ml/config/provisioning_parameters.json"
if [[ -f "$PROVISIONING_PARAMS" ]]; then
    export EKS_CLUSTER_NAME=$(jq -r '.eks_cluster_name // empty' "$PROVISIONING_PARAMS")
fi

# ============================================
# Configure kubelet
# ============================================
echo "Configuring kubelet..."

# kubelet is managed by EKS, but we can add extra args
mkdir -p /etc/kubernetes/kubelet

# Configure kubelet for GPU workloads
cat > /etc/kubernetes/kubelet/extra-args << 'EOF'
KUBELET_EXTRA_ARGS=--max-pods=110 --kube-reserved=cpu=500m,memory=1Gi
EOF

# ============================================
# Install NVIDIA Device Plugin dependencies
# ============================================
echo "Configuring NVIDIA runtime..."

# nvidia-container-runtime is pre-installed
# Configure containerd to use nvidia runtime
cat > /etc/containerd/config.toml << 'EOF'
version = 2
[plugins."io.containerd.grpc.v1.cri".containerd]
  default_runtime_name = "nvidia"
  [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia]
    runtime_type = "io.containerd.runc.v2"
    [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.nvidia.options]
      BinaryName = "/usr/bin/nvidia-container-runtime"
EOF

systemctl restart containerd

# ============================================
# Configure EFA for Kubernetes
# ============================================
echo "Configuring EFA..."

# EFA device plugin will be installed via Kubernetes
# Ensure EFA is accessible
chmod 666 /dev/infiniband/* 2>/dev/null || true

# ============================================
# Configure node labels
# ============================================
# Node labels are applied via Kubernetes, not here
# This section is for documentation

echo "EKS on_create.sh completed at $(date)"
exit 0
```

## on_start.sh Template

Executed on every node boot:

```bash
#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/hyperpod-on-start.log) 2>&1
echo "Starting on_start.sh at $(date)"

# ============================================
# Verify mounts
# ============================================
FSX_MOUNT_DIR="${FSX_MOUNT_DIR:-/fsx}"
if [[ -d "$FSX_MOUNT_DIR" ]] && ! mountpoint -q "$FSX_MOUNT_DIR"; then
    echo "Re-mounting FSx..."
    mount "$FSX_MOUNT_DIR"
fi

# ============================================
# Start monitoring agents
# ============================================
echo "Starting monitoring agents..."
# CloudWatch agent (if installed)
if systemctl is-enabled amazon-cloudwatch-agent 2>/dev/null; then
    systemctl start amazon-cloudwatch-agent
fi

# ============================================
# Verify GPU/Accelerator health
# ============================================
echo "Checking accelerator health..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi || echo "WARNING: nvidia-smi failed"
fi

if command -v neuron-ls &> /dev/null; then
    neuron-ls || echo "WARNING: neuron-ls failed"
fi

# ============================================
# Clean up temporary files
# ============================================
echo "Cleaning temporary files..."
rm -rf /tmp/hyperpod-* 2>/dev/null || true
rm -rf /var/tmp/torch-* 2>/dev/null || true

echo "on_start.sh completed at $(date)"
exit 0
```

## Uploading Scripts to S3

```bash
# Create scripts directory
mkdir -p lifecycle-scripts

# Copy scripts to directory
cp on_create.sh on_start.sh provisioning_parameters.json lifecycle-scripts/

# Make scripts executable
chmod +x lifecycle-scripts/*.sh

# Upload to S3
aws s3 sync lifecycle-scripts/ s3://your-bucket/hyperpod/

# Verify upload
aws s3 ls s3://your-bucket/hyperpod/
```

## Debugging Lifecycle Scripts

### Check Script Execution Logs

```bash
# Connect to node via SSM
aws ssm start-session --target i-xxxxx

# View on_create logs
cat /var/log/hyperpod-on-create.log

# View on_start logs
cat /var/log/hyperpod-on-start.log

# View system logs
journalctl -u hyperpod-lifecycle
```

### Common Issues

**Script fails to download**
- Verify S3 bucket permissions
- Check S3 VPC endpoint exists
- Verify IAM node role has s3:GetObject permission

**Script exits with error**
- Check script syntax: `bash -n script.sh`
- Verify all commands exist on AMI
- Check for missing environment variables

**Mount failures**
- Verify FSx DNS name is correct
- Check security group allows NFS traffic
- Verify FSx is in same VPC

### Testing Scripts Locally

```bash
# Test syntax
bash -n on_create.sh

# Dry run (if script supports it)
DRY_RUN=1 bash on_create.sh

# Test on fresh EC2 instance
# Launch instance with same AMI as HyperPod
# Copy script and run manually
```

## Best Practices

### Script Structure

1. **Always use `set -euo pipefail`**: Fail fast on errors
2. **Log everything**: Use `tee` to capture output
3. **Check prerequisites**: Verify required tools exist
4. **Handle errors gracefully**: Provide meaningful error messages
5. **Make idempotent**: Scripts may run multiple times

### Security

1. **Don't hardcode credentials**: Use IAM roles
2. **Validate inputs**: Sanitize environment variables
3. **Limit permissions**: Only request necessary access
4. **Audit scripts**: Review before deployment

### Performance

1. **Parallelize downloads**: Use `&` and `wait`
2. **Cache packages**: Use yum cache or S3
3. **Minimize network calls**: Batch operations
4. **Use local storage**: `/tmp` is fast

### Maintenance

1. **Version control scripts**: Use git
2. **Document changes**: Keep changelog
3. **Test before deploying**: Use test clusters
4. **Monitor execution**: Set up alerting
