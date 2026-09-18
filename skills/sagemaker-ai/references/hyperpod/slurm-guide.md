# Slurm Orchestrator Guide

Complete guide for HyperPod clusters with Slurm orchestration.

## Table of Contents
- [Slurm vs EKS](#slurm-vs-eks)
- [Prerequisites](#prerequisites)
- [Pre-Creation Checklist](#pre-creation-checklist)
- [Cluster Creation Workflow](#cluster-creation-workflow)
- [Job Submission](#job-submission)
- [AWS CLI Reference](#aws-cli-reference)

---

## Slurm vs EKS

| Aspect | Slurm | EKS |
|--------|-------|-----|
| **AZ Requirement** | Single AZ OK | **2+ AZs Required** |
| **VPC Config** | Optional (uses HyperPod default) | Required |
| **Configuration Files** | `create_cluster.json` + `provisioning_parameters.json` | `config.yaml` |
| **Lifecycle Scripts** | Required (uploaded to S3) | Not required |
| **Job Submission** | SBATCH scripts | PyTorchJob via kubectl/hyp |
| **Access Method** | SSM Session Manager | kubectl |

---

## Prerequisites

- AWS CLI v2
- Session Manager Plugin for SSM access
- Lifecycle scripts uploaded to S3

---

## Pre-Creation Checklist

**ALWAYS perform these validations BEFORE creating a Slurm cluster:**

### 1. Instance Type Quota Check
```bash
aws service-quotas list-service-quotas \
  --service-code sagemaker \
  --region us-east-1 \
  --query 'Quotas[?contains(QuotaName, `<INSTANCE_TYPE>`) && contains(QuotaName, `cluster`)].[QuotaName,Value]'
```

### 2. Validate Configuration Files
```bash
# Clone awsome-distributed-training for validation script
git clone https://github.com/aws-samples/awsome-distributed-training.git
cd awsome-distributed-training/1.architectures/5.sagemaker-hyperpod/

# Run validation BEFORE cluster creation
python3 validate-config.py \
  --cluster-config create_cluster.json \
  --provisioning-parameters provisioning_parameters.json
```

The validation script checks:
- Instance group names match between files
- Subnet configurations are valid
- Security group rules (ingress/egress)
- FSx Lustre DNS name and mount name
- Cross-resource consistency

### 3. Instance Group Name Matching (CRITICAL)

**Most common Slurm gotcha**: Instance group names in `create_cluster.json` MUST match those in `provisioning_parameters.json`:

```
create_cluster.json                    provisioning_parameters.json
Instance Groups:                       Slurm Nodes:
- controller-machine          ------>  instance_group: controller-machine
- login-group                 ------>  instance_group: login-group (optional)
- compute-nodes               ------>  instance_group: compute-nodes
```

### 4. EFA Security Group (for GPU/Trainium instances)

Security group MUST allow all traffic within itself:
```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxx \
  --protocol all \
  --port -1 \
  --source-group sg-xxx
```

---

## Cluster Creation Workflow

### 1. Prepare Lifecycle Scripts

**STRONGLY Recommended**: Use production-ready lifecycle scripts from AWS Samples:
```bash
git clone https://github.com/aws-samples/awsome-distributed-training.git
cd awsome-distributed-training/1.architectures/5.sagemaker-hyperpod/LifecycleScripts/base-config/
```

Key files in base-config:
| File | Purpose |
|------|---------|
| `lifecycle_script.py` | Primary orchestration script |
| `on_create.sh` | Initial setup during cluster creation |
| `provisioning_parameters.json` | Slurm node configuration |
| `start_slurm.sh` | Slurm daemon startup |
| `mount_fsx.sh` | FSx Lustre mounting |
| `setup_mariadb_accounting.sh` | Local Slurm accounting |
| `install_docker.sh` | Docker installation |

**Custom on_create.sh** (only if you understand lifecycle scripts well):

```bash
#!/bin/bash
set -e

# Install Neuron SDK for Trainium
. /etc/os-release
sudo tee /etc/yum.repos.d/neuron.repo > /dev/null <<EOF
[neuron]
name=Neuron YUM Repository
baseurl=https://yum.repos.neuron.amazonaws.com
enabled=1
gpgcheck=1
gpgkey=https://yum.repos.neuron.amazonaws.com/GPG-PUB-KEY-AMAZON-AWS-NEURON.PUB
EOF

sudo yum install -y aws-neuronx-collectives aws-neuronx-runtime-lib aws-neuronx-tools
```

### 2. Configure provisioning_parameters.json

```json
{
  "version": "1.0.0",
  "workload_manager": "slurm",
  "controller_group": "controller-machine",
  "worker_groups": [
    {
      "instance_group_name": "compute-nodes",
      "partition_name": "compute"
    }
  ],
  "fsx_dns_name": "fs-xxx.fsx.us-east-1.amazonaws.com",
  "fsx_mountname": "xxxxx"
}
```

### 3. Upload to S3

```bash
aws s3 cp lifecycle-scripts/ s3://my-bucket/hyperpod/lifecycle-scripts/ --recursive
```

### 4. Create Cluster

```bash
aws sagemaker create-cluster \
  --cluster-name my-slurm-cluster \
  --instance-groups '[{
    "InstanceGroupName": "controller-machine",
    "InstanceType": "ml.m5.xlarge",
    "InstanceCount": 1,
    "LifeCycleConfig": {
      "SourceS3Uri": "s3://my-bucket/hyperpod/lifecycle-scripts/",
      "OnCreate": "on_create.sh"
    },
    "ExecutionRole": "arn:aws:iam::xxx:role/HyperPodRole"
  }, {
    "InstanceGroupName": "compute-nodes",
    "InstanceType": "ml.trn1.32xlarge",
    "InstanceCount": 2,
    "LifeCycleConfig": {
      "SourceS3Uri": "s3://my-bucket/hyperpod/lifecycle-scripts/",
      "OnCreate": "on_create.sh"
    },
    "ExecutionRole": "arn:aws:iam::xxx:role/HyperPodRole"
  }]' \
  --vpc-config "SecurityGroupIds=sg-xxx,Subnets=subnet-xxx"
```

---

## Job Submission

### 1. Connect to Head Node

```bash
# Get instance ID
aws sagemaker list-cluster-nodes --cluster-name my-cluster

# Connect via SSM
aws ssm start-session --target i-xxxxx
```

### 2. Submit SBATCH Job

```bash
#!/bin/bash
#SBATCH --job-name=my-training
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --exclusive

srun python train.py
```

### 3. Monitor

```bash
squeue                    # List jobs
sinfo                     # Node status
scancel JOB_ID            # Cancel job
sacct -j JOB_ID           # Job accounting
```

---

## AWS CLI Reference

```bash
# List clusters
aws sagemaker list-clusters

# Describe cluster
aws sagemaker describe-cluster --cluster-name NAME

# List nodes
aws sagemaker list-cluster-nodes --cluster-name NAME

# Delete cluster
aws sagemaker delete-cluster --cluster-name NAME

# Update software
aws sagemaker update-cluster-software --cluster-name NAME
```

---

## Slurm-Specific Errors

### CloudWatch Logs Not Appearing

By default, logs go to HyperPod platform account. Update CloudWatch agent config:
```bash
# Edit /opt/aws/amazon-cloudwatch-agent/sagemaker_cwagent_config.json
# Update file_path to /var/log/provision/provisioning.log
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s -c \
  file:/opt/aws/amazon-cloudwatch-agent/sagemaker_cwagent_config.json
```

### NCCL Parallel Training Failures

**Root Cause**: Linux `RemoveIPC=yes` cleans up IPC resources on logout.

**Solution**: Create epilog script:
```bash
#!/bin/bash
# /opt/slurm/etc/epilog.sh
for seg in $(ipcs -m | awk -v owner="$SLURM_JOB_USER" '$3 == owner {print $2}'); do
    ipcrm -m "$seg"
done
for file in /dev/shm/nccl-*; do
    [ -e "$file" ] && rm "$file"
done
```

Add to `slurm.conf`: `Epilog="/opt/slurm/etc/epilog.sh"`

### Nodes DOWN/DRAINED After Reboot

```bash
# Use Slurm reboot command (NOT sudo reboot)
scontrol reboot nextstate=resume <node_list>

# For GPU instances, increase boot timeout in slurm.conf
TimeToResume=300
```

### OOM Draining Issues

Enable cgroups in `slurm.conf`:
```
TaskPlugin=task/cgroup
```

Configure `/opt/slurm/etc/cgroup.conf`:
```
CgroupAutomount=yes
ConstrainRAMSpace=yes
MaxRAMPercent=99
```

### Docker Not Installed Across Nodes

```bash
cd /tmp/sagemaker-lifecycle-* && cd src/utils/
srun -N <num_nodes> bash install_docker.sh
```

### Slurmd Not Starting

```bash
ssh <node>
sudo systemctl status slurmd
sudo journalctl -xe  # diagnose
sudo systemctl start slurmd
```

### FSx Lustre Not Mounting

Check `provisioning_parameters.json`:
- Verify `fsx_dns_name` format: `fs-xxx.fsx.us-east-1.amazonaws.com`
- Verify `fsx_mountname` matches FSx configuration

### Instance Group Name Mismatch

Ensure exact name match:
```json
// create_cluster.json
"InstanceGroupName": "compute-nodes"

// provisioning_parameters.json
"instance_group_name": "compute-nodes"  // MUST MATCH EXACTLY
```
