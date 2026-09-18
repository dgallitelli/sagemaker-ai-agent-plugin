# Slurm Cluster Setup Guide

This guide walks through creating a HyperPod cluster with Slurm orchestration.

## Prerequisites

Before starting, ensure you have completed:

- [ ] Service quotas approved (see `references/hyperpod/prerequisites-checklist.md`)
- [ ] VPC configured with adequate IP space (see `references/hyperpod/networking-patterns.md`)
- [ ] IAM roles created (see `references/hyperpod/iam-policies.md`)
- [ ] Lifecycle scripts prepared (see `references/hyperpod/lifecycle-scripts.md`)

### Required Tools

```bash
# Install AWS CLI v2
pip install awscli --upgrade

# Install Session Manager plugin
# macOS
brew install --cask session-manager-plugin

# Linux
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
sudo dpkg -i session-manager-plugin.deb

# Verify
session-manager-plugin --version
```

## Step 1: Prepare Lifecycle Scripts

### Create provisioning_parameters.json

```json
{
  "version": "1.0",
  "workload_manager": "slurm",
  "controller_group": "controller",
  "worker_groups": [
    {
      "instance_group_name": "gpu-workers",
      "partition_name": "gpu"
    }
  ],
  "fsx_dns_name": "fs-xxxxx.fsx.us-west-2.amazonaws.com",
  "fsx_mountname": "xxxxx",
  "fsx_mount_dir": "/fsx"
}
```

### Create on_create.sh

```bash
#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/hyperpod-on-create.log) 2>&1
echo "Starting on_create.sh at $(date)"

# Parse provisioning parameters
PROVISIONING_PARAMS="/opt/ml/config/provisioning_parameters.json"
export FSX_DNS_NAME=$(jq -r '.fsx_dns_name // empty' "$PROVISIONING_PARAMS")
export FSX_MOUNTNAME=$(jq -r '.fsx_mountname // empty' "$PROVISIONING_PARAMS")
export FSX_MOUNT_DIR=$(jq -r '.fsx_mount_dir // "/fsx"' "$PROVISIONING_PARAMS")

# Install dependencies
yum update -y
yum install -y git htop tmux jq

# Mount FSx if configured
if [[ -n "${FSX_DNS_NAME}" ]]; then
    echo "Mounting FSx Lustre..."
    mkdir -p "$FSX_MOUNT_DIR"
    mount -t lustre -o noatime,flock \
        "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME}" \
        "$FSX_MOUNT_DIR"
    echo "${FSX_DNS_NAME}@tcp:/${FSX_MOUNTNAME} ${FSX_MOUNT_DIR} lustre noatime,flock,_netdev 0 0" >> /etc/fstab
fi

# Configure NCCL environment
cat >> /etc/profile.d/nccl.sh << 'EOF'
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=eth0
export FI_EFA_USE_DEVICE_RDMA=1
export FI_PROVIDER=efa
EOF

echo "on_create.sh completed at $(date)"
exit 0
```

### Upload to S3

```bash
# Create directory structure
mkdir -p lifecycle-scripts

# Copy scripts
cp provisioning_parameters.json lifecycle-scripts/
cp on_create.sh lifecycle-scripts/

# Make executable
chmod +x lifecycle-scripts/*.sh

# Upload to S3
aws s3 sync lifecycle-scripts/ s3://your-bucket/hyperpod/

# Verify
aws s3 ls s3://your-bucket/hyperpod/
```

## Step 2: Create Cluster Configuration

### cluster-config.json

```json
{
  "ClusterName": "my-slurm-cluster",
  "InstanceGroups": [
    {
      "InstanceGroupName": "controller",
      "InstanceType": "ml.m5.xlarge",
      "InstanceCount": 1,
      "LifeCycleConfig": {
        "SourceS3Uri": "s3://your-bucket/hyperpod/",
        "OnCreate": "on_create.sh"
      },
      "ExecutionRole": "arn:aws:iam::123456789012:role/HyperPodExecutionRole",
      "ThreadsPerCore": 1,
      "InstanceStorageConfigs": [
        {
          "EbsVolumeConfig": {
            "VolumeSizeInGB": 500
          }
        }
      ]
    },
    {
      "InstanceGroupName": "gpu-workers",
      "InstanceType": "ml.p5.48xlarge",
      "InstanceCount": 4,
      "LifeCycleConfig": {
        "SourceS3Uri": "s3://your-bucket/hyperpod/",
        "OnCreate": "on_create.sh"
      },
      "ExecutionRole": "arn:aws:iam::123456789012:role/HyperPodExecutionRole",
      "ThreadsPerCore": 1,
      "InstanceStorageConfigs": [
        {
          "EbsVolumeConfig": {
            "VolumeSizeInGB": 1000
          }
        }
      ]
    }
  ],
  "VpcConfig": {
    "SecurityGroupIds": ["sg-xxxxx"],
    "Subnets": ["subnet-xxxxx"]
  }
}
```

## Step 3: Create the Cluster

### Using AWS CLI

```bash
# Create cluster
aws sagemaker create-cluster \
  --cli-input-json file://cluster-config.json \
  --region us-west-2

# Monitor creation status
watch -n 30 "aws sagemaker describe-cluster \
  --cluster-name my-slurm-cluster \
  --region us-west-2 \
  --query 'ClusterStatus'"
```

### Using Console (Alternative)

1. Navigate to SageMaker Console → HyperPod → Clusters
2. Click "Create cluster"
3. Select "Slurm" as orchestrator
4. Configure instance groups
5. Select VPC and subnets
6. Specify S3 lifecycle script location
7. Review and create

## Step 4: Monitor Cluster Creation

### Check Cluster Status

```bash
# Get cluster status
aws sagemaker describe-cluster \
  --cluster-name my-slurm-cluster \
  --query '{Status: ClusterStatus, FailureMessage: FailureMessage}'

# Expected progression:
# Creating → InService (15-30 minutes)
```

### Check Node Status

```bash
# List all nodes
aws sagemaker list-cluster-nodes \
  --cluster-name my-slurm-cluster \
  --query 'ClusterNodeSummaries[*].{Name: InstanceGroupName, Status: InstanceStatus.Status}'

# Describe specific node
aws sagemaker describe-cluster-node \
  --cluster-name my-slurm-cluster \
  --node-id <node-id>
```

### View Creation Logs

```bash
# Check CloudWatch logs
aws logs tail /aws/sagemaker/Clusters/my-slurm-cluster --follow
```

## Step 5: Connect to Cluster

### Via SSM Session Manager

```bash
# Get controller instance ID
CONTROLLER_INSTANCE=$(aws sagemaker list-cluster-nodes \
  --cluster-name my-slurm-cluster \
  --query "ClusterNodeSummaries[?InstanceGroupName=='controller'].InstanceId" \
  --output text)

# Connect to controller
aws ssm start-session --target $CONTROLLER_INSTANCE
```

### Verify Slurm Installation

```bash
# Once connected, verify Slurm
sinfo

# Expected output:
# PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
# gpu*         up   infinite      4   idle ip-10-0-1-[10-13]

# Check node details
scontrol show nodes

# Check partitions
scontrol show partition
```

## Step 6: (Optional) Setup FSx for Lustre

### Create FSx Filesystem

```bash
# Create FSx for Lustre
aws fsx create-file-system \
  --file-system-type LUSTRE \
  --storage-capacity 1200 \
  --subnet-ids subnet-xxxxx \
  --security-group-ids sg-xxxxx \
  --lustre-configuration '{
    "DeploymentType": "PERSISTENT_2",
    "PerUnitStorageThroughput": 250,
    "DataCompressionType": "LZ4"
  }' \
  --tags Key=Name,Value=hyperpod-fsx

# Get DNS name and mount name
aws fsx describe-file-systems \
  --query "FileSystems[?Tags[?Value=='hyperpod-fsx']].[DNSName, LustreConfiguration.MountName]"
```

### Update Lifecycle Scripts

Update `provisioning_parameters.json` with FSx details and re-upload to S3.

## Step 7: Configure User Environment

### Create Shared Directories

```bash
# On controller node (via SSM)
sudo mkdir -p /fsx/users
sudo mkdir -p /fsx/datasets
sudo mkdir -p /fsx/checkpoints
sudo chmod 777 /fsx/users /fsx/datasets /fsx/checkpoints
```

### Install ML Frameworks

```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p /fsx/miniconda3

# Create shared environment
/fsx/miniconda3/bin/conda create -n pytorch python=3.10 -y
/fsx/miniconda3/bin/conda activate pytorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Configure Environment Modules

```bash
# Create modulefiles
sudo mkdir -p /usr/share/Modules/modulefiles/pytorch
sudo cat > /usr/share/Modules/modulefiles/pytorch/2.1 << 'EOF'
#%Module1.0
proc ModulesHelp { } {
    puts stderr "PyTorch 2.1 with CUDA 11.8"
}
module-whatis "PyTorch 2.1"
prepend-path PATH /fsx/miniconda3/envs/pytorch/bin
prepend-path LD_LIBRARY_PATH /fsx/miniconda3/envs/pytorch/lib
EOF
```

## Verification Checklist

After cluster creation, verify:

```bash
# Check Slurm controller
systemctl status slurmctld

# Check all nodes registered
sinfo -N -l

# Check GPU resources
sinfo -o "%N %G"

# Test job submission
srun --nodes=1 --ntasks=1 nvidia-smi

# Check EFA
fi_info -p efa

# Verify FSx mount (if configured)
df -h /fsx
```

## Cluster Management

### Scale Cluster

```bash
# Currently requires updating cluster configuration
# and calling update-cluster API
aws sagemaker update-cluster \
  --cluster-name my-slurm-cluster \
  --instance-groups file://updated-config.json
```

### Update Software

```bash
aws sagemaker update-cluster-software \
  --cluster-name my-slurm-cluster
```

### Delete Cluster

```bash
# Delete cluster (cannot be undone)
aws sagemaker delete-cluster \
  --cluster-name my-slurm-cluster

# Confirm deletion
aws sagemaker describe-cluster \
  --cluster-name my-slurm-cluster
# Should return ResourceNotFound
```

## Common Setup Issues

### Cluster Stuck in Creating

**Check**:
- Service quotas
- IAM role permissions
- S3 lifecycle script access
- VPC/subnet configuration

**Debug**:
```bash
aws sagemaker describe-cluster \
  --cluster-name my-slurm-cluster \
  --query 'FailureMessage'
```

### Lifecycle Script Failed

**Check**:
- Script syntax: `bash -n on_create.sh`
- S3 permissions
- Script logs: `/var/log/hyperpod-on-create.log`

### Slurm Not Starting

**Check on controller**:
```bash
systemctl status slurmctld
journalctl -u slurmctld -n 100
cat /var/log/slurm/slurmctld.log
```

## Next Steps

- [Submit training jobs](job-submission.md)
- [Troubleshooting guide](troubleshooting.md)
